"""浏览器管理服务 - 使用 DrissionPage 实现登录与 rapt 获取

职责:
  1. 管理浏览器实例生命周期 (启动/停止)
  2. 登录 Google 账号 → 提取 cookies
  3. 导航到敏感页面 → 密码/TOTP 重验证 → 获取 rapt token
"""

import json
import logging
import os
import shutil
import signal
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from DrissionPage import ChromiumOptions, WebPage

from core.constants import (
    BROWSER_PORT_MAX,
    BROWSER_PORT_MIN,
    SEL_EMAIL_INPUT,
    SEL_EMAIL_NEXT,
    SEL_SKIP,
    SEL_SKIP_LATER_CN,
    SEL_SKIP_LATER_CN2,
    SEL_SKIP_NOT_NOW,
)
from services.auth_steps import enter_password, enter_totp
from services.page_wait import (
    safe_click,
    safe_ele,
    safe_input,
    safe_navigate,
    safe_url,
    wait_page_stable,
)

logger = logging.getLogger(__name__)

# 浏览器用户数据根目录
PROFILES_DIR = Path(__file__).resolve().parent.parent / ".browser_profiles"


@dataclass
class BrowserInstance:
    """运行中的浏览器实例"""
    profile_id: int
    page: object = field(default=None, repr=False)
    data_dir: str = ""
    cookies: dict = field(default_factory=dict)


class BrowserManager:
    """管理所有 DrissionPage 浏览器实例"""

    def __init__(self):
        self._instances: dict[int, BrowserInstance] = {}
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_data_dir(profile_id: int, account_email: str = "") -> Path:
        """获取 profile 对应的 user-data-dir"""
        mapping_file = PROFILES_DIR / ".mapping.json"
        mapping = {}
        if mapping_file.exists():
            try:
                mapping = json.loads(mapping_file.read_text())
            except Exception:
                mapping = {}

        key = str(profile_id)
        need_new = key not in mapping

        # 已有 mapping 但账号不匹配时，说明 profile 被重新关联了，需要新建目录
        if not need_new and account_email:
            email_prefix = account_email.split("@")[0].lower()
            existing_dir = mapping[key].lower()
            if email_prefix not in existing_dir:
                logger.info(f"[browser] profile {profile_id} 账号已变更, 重新分配目录 ({mapping[key]} -> {account_email})")
                need_new = True

        if need_new:
            prefix = account_email.split("@")[0] if account_email else f"profile{profile_id}"
            prefix = "".join(c if c.isalnum() or c in "._-" else "_" for c in prefix)
            short_id = uuid.uuid4().hex[:8]
            mapping[key] = f"{prefix}_{short_id}"
            mapping_file.write_text(json.dumps(mapping, indent=2))

        data_dir = PROFILES_DIR / mapping[key]
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def _process_alive(pid: int | None) -> bool:
        """检测 PID 对应的进程是否存活 (POSIX: signal 0 探测)

        已知边界: 仅校验 PID 当前对应一个活进程, 无法区分是否为原浏览器进程。
        极端场景 (浏览器死亡 + OS 将相同 PID 复用给其他进程) 下会误判为存活。
        实际触发概率极低, 当前实现接受该边界条件。后续如需更严格校验,
        可引入 psutil.Process(pid).create_time() 比对启动时刻。
        """
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # 进程存在但无权发送信号, 视为存活
            return True
        except OSError:
            return False

    @staticmethod
    def _instance_pid(instance: BrowserInstance | None) -> int | None:
        """安全提取 instance 对应的浏览器进程 PID, 不可访问返回 None"""
        if not instance or not instance.page:
            return None
        try:
            return instance.page.process_id
        except Exception:
            return None

    @classmethod
    def _check_alive(cls, instance: BrowserInstance | None) -> bool:
        """探活某个 instance 对应的浏览器进程"""
        return cls._process_alive(cls._instance_pid(instance))

    @staticmethod
    def _terminate_pid(pid: int | None) -> bool:
        """向 PID 发送 SIGTERM 强制退出, 成功返回 True"""
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def prune_dead_instances(self) -> list[int]:
        """剔除所有进程已退出的僵尸 instance, 返回被清理的 profile_id 列表

        典型触发场景: 用户在桌面手动关闭浏览器窗口 / Cmd+Q 强制退出后,
        后端 `_instances` 字典里仍残留记录, 导致 is_running 误报。

        注意: 进程已死后不再调用 page.quit() —— DrissionPage 内部会通过 CDP
        socket 通信, 进程不在了会卡到 socket 超时。直接丢弃 instance 引用,
        让 GC 回收即可。
        """
        dead: list[int] = [
            profile_id
            for profile_id in list(self._instances.keys())
            if not self._check_alive(self._instances.get(profile_id))
        ]

        for profile_id in dead:
            self._instances.pop(profile_id, None)
            logger.info(f"[browser] 清理僵尸 instance: profile_id={profile_id}")

        return dead

    def force_clear_all(self) -> dict:
        """强制清空所有 instance 记录 (备用兜底方案)

        使用场景: 用户在桌面手动关闭多个浏览器后, 探活逻辑因 PID 复用等边界
        问题未能识别为僵尸, 此时一键清空所有运行中记录。

        对存活进程: 直接 SIGTERM 强制退出 (不调 page.quit() 避免 CDP 卡死),
        然后清空记录。失败也继续清空记录 —— "force" 语义保证后端状态归零。
        """
        cleared_alive: list[int] = []
        cleared_dead: list[int] = []
        killed_pids: list[int] = []

        for profile_id in list(self._instances.keys()):
            instance = self._instances.pop(profile_id, None)
            pid = self._instance_pid(instance)

            if self._process_alive(pid):
                cleared_alive.append(profile_id)
                if pid is not None and self._terminate_pid(pid):
                    killed_pids.append(pid)
            else:
                cleared_dead.append(profile_id)

        logger.info(
            f"[browser] force_clear_all: 清空 {len(cleared_alive)} 个存活 instance "
            f"(SIGTERM {len(killed_pids)} 个 PID), {len(cleared_dead)} 个僵尸 instance"
        )
        return {
            "cleared_alive": cleared_alive,
            "cleared_dead": cleared_dead,
            "killed_pids": killed_pids,
            "total": len(cleared_alive) + len(cleared_dead),
        }

    def is_running(self, profile_id: int) -> bool:
        instance = self._instances.get(profile_id)
        if instance is None:
            return False
        if self._check_alive(instance):
            return True
        # 僵尸 instance 自动清理
        self._instances.pop(profile_id, None)
        logger.info(f"[browser] is_running 探测到僵尸 instance, 已清理: profile_id={profile_id}")
        return False

    def get_running_ids(self) -> list[int]:
        self.prune_dead_instances()
        return list(self._instances.keys())

    def find_profile_id_by_page(self, page) -> int | None:
        """根据 DrissionPage 实例反查 profile_id, 找不到返回 None。"""
        for pid, inst in self._instances.items():
            if inst.page is page:
                return pid
        return None

    @staticmethod
    def _is_headless_mode() -> bool:
        from services.runtime_config import get_bool
        return get_bool("headless_mode")

    async def launch(self, profile, *, headless: bool | None = None) -> BrowserInstance:
        """启动 DrissionPage 浏览器实例

        Args:
            profile: BrowserProfile ORM 对象或 profile_id
            headless: 强制指定无头模式, None 则读取数据库设置
        """
        from models.orm import BrowserProfile
        profile_id = profile.id if isinstance(profile, BrowserProfile) else profile
        account_email = ""
        if hasattr(profile, "account") and profile.account:
            account_email = profile.account.email

        if self.is_running(profile_id):
            raise RuntimeError(f"Profile {profile_id} 已在运行中")

        data_dir = self._get_data_dir(profile_id, account_email)
        use_headless = headless if headless is not None else self._is_headless_mode()

        co = ChromiumOptions()
        # 每个实例使用独立随机端口，避免接管已有浏览器
        import random
        port = random.randint(BROWSER_PORT_MIN, BROWSER_PORT_MAX)
        co.set_address(f"127.0.0.1:{port}")
        co.set_argument("--lang", "en-US")
        co.set_user_data_path(str(data_dir))
        if use_headless:
            co.headless()

        # 代理
        if hasattr(profile, "proxy_type") and profile.proxy_type and profile.proxy_host:
            proxy_url = f"{profile.proxy_type}://{profile.proxy_host}:{profile.proxy_port}"
            co.set_argument(f"--proxy-server={proxy_url}")

        page = WebPage(chromium_options=co)

        instance = BrowserInstance(
            profile_id=profile_id,
            page=page,
            data_dir=str(data_dir),
        )
        self._instances[profile_id] = instance
        logger.info(f"Browser launched: profile_id={profile_id}")
        return instance

    async def stop(self, profile_id: int) -> None:
        """停止浏览器实例"""
        instance = self._instances.pop(profile_id, None)
        if not instance:
            raise RuntimeError(f"Profile {profile_id} 未在运行")

        try:
            if instance.page:
                instance.page.quit()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        logger.info(f"Browser stopped: profile_id={profile_id}")

    async def stop_all(self) -> None:
        for profile_id in list(self._instances.keys()):
            try:
                await self.stop(profile_id)
            except Exception as e:
                logger.warning(f"Error stopping profile {profile_id}: {e}")

    def get_status(self, profile_id: int) -> dict:
        """查询浏览器运行状态

        副作用: 走 is_running 探活, 命中僵尸 instance 时会顺带清理记录。
        从用户视角无害 (清理本应清理的脏数据), 但严格 REST 风格下 GET 应幂等。
        """
        if not self.is_running(profile_id):
            return {"status": "stopped", "profile_id": profile_id}
        return {"status": "running", "profile_id": profile_id}

    def get_instance(self, profile_id: int) -> BrowserInstance | None:
        return self._instances.get(profile_id)

    def get_page(self, profile_id: int):
        instance = self._instances.get(profile_id)
        return instance.page if instance else None

    def get_cookies(self, profile_id: int) -> dict[str, str]:
        """从浏览器实例提取 Google 域的 cookies

        优先使用 myaccount.google.com 域的 cookie 值 (FamilyAPI 需要),
        其次 accounts.google.com, 再次 .google.com。
        同名 cookie 高优先级域覆盖低优先级域。
        """
        instance = self._instances.get(profile_id)
        if not instance or not instance.page:
            return {}

        def _domain_priority(domain: str) -> int:
            if "myaccount.google" in domain:
                return 3
            if "accounts.google" in domain:
                return 2
            if domain.endswith(".google.com") or domain == ".google.com":
                return 1
            return 0

        cookies = {}
        priorities = {}
        for c in instance.page.cookies(all_domains=True):
            if isinstance(c, dict):
                name, value, domain = c.get("name") or "", c.get("value") or "", c.get("domain") or ""
            else:
                name, value, domain = str(c.name), str(c.value), str(getattr(c, "domain", ""))

            if "google" not in domain:
                continue

            p = _domain_priority(domain)
            if p >= priorities.get(name, -1):
                cookies[name] = value
                priorities[name] = p

        return cookies

    async def run_in_browser_thread(self, profile_id: int, fn, *args):
        """DrissionPage 不需要线程隔离, 直接执行"""
        return fn(*args)

    def delete_profile_data(self, profile_id: int) -> None:
        """删除 profile 对应的浏览器数据目录"""
        if self.is_running(profile_id):
            raise RuntimeError(f"Profile {profile_id} 正在运行, 请先停止")

        mapping_file = PROFILES_DIR / ".mapping.json"
        mapping = {}
        if mapping_file.exists():
            try:
                mapping = json.loads(mapping_file.read_text())
            except Exception:
                mapping = {}

        key = str(profile_id)
        dir_name = mapping.get(key)
        if dir_name:
            data_dir = PROFILES_DIR / dir_name
            if data_dir.exists():
                shutil.rmtree(data_dir)
                logger.info(f"Profile data deleted: {data_dir}")
            del mapping[key]
            mapping_file.write_text(json.dumps(mapping, indent=2))

    # ── 存储分析与清理 ────────────────────────────────────

    # 黑名单: 明确可安全删除的文件和目录，不影响浏览器启动和登录态
    CLEANABLE_TOP_DIRS: list[str] = [
        "optimization_guide_model_store",
        "component_crx_cache",
        "extensions_crx_cache",
        "WasmTtsEngine",
        "Safe Browsing",
        "GraphiteDawnCache",
        "ShaderCache",
        "GrShaderCache",
        "DawnGraphiteCache",
        "SSLErrorAssistant",
        "ZxcvbnData",
        "CertificateRevocation",
        "PKIMetadata",
        "OriginTrials",
        "OptimizationHints",
        "SafetyTips",
        "TrustTokenKeyCommitments",
        "PrivacySandboxAttestationsPreloaded",
        "RecoveryImproved",
        "segmentation_platform",
        "Subresource Filter",
        "ActorSafetyLists",
        "WidevineCdm",
        "Crowd Deny",
        "MEIPreload",
        "FileTypePolicies",
        "CaptchaProviders",
        "AmountExtractionHeuristicRegexes",
        "FirstPartySetsPreloaded",
        "OnDeviceHeadSuggestModel",
        "Variations",
        "BrowserMetrics",
        "GPUPersistentCache",
        "NativeMessagingHosts",
    ]
    CLEANABLE_TOP_FILES: list[str] = [
        "BrowserMetrics-spare.pma",
        "first_party_sets.db",
        "first_party_sets.db-journal",
        "ChromeFeatureState",
        "VariationsSeedV2",
        "VariationsSafeSeedV2",
        ".DS_Store",
    ]
    CLEANABLE_DEFAULT_DIRS: list[str] = [
        "Cache",
        "Code Cache",
        "Service Worker",
        "GPUCache",
        "DawnWebGPUCache",
        "DawnGraphiteCache",
        "GrShaderCache",
        "ShaderCache",
        "blob_storage",
        "File System",
        "Storage",
        "Sessions",
        "Web Applications",
        "Shared Dictionary",
        "shared_proto_db",
        "AutofillAiModelCache",
        "Segmentation Platform",
        "PersistentOriginTrials",
        "Feature Engagement Tracker",
        "Download Service",
        "Extensions",
        "Extension State",
        "Extension Rules",
        "Extension Scripts",
        "WebStorage",
        "IndexedDB",
        "Sync Data",
        "Search Logos",
        "GCM Store",
        "Site Characteristics Database",
        "Collaboration",
        "DataSharing",
        "Accounts",
        "image_cache",
        "optimization_guide_hint_cache_store",
        "VideoDecodeStats",
    ]
    CLEANABLE_DEFAULT_FILES: list[str] = [
        "History", "History-journal",
        "Favicons", "Favicons-journal",
        "Web Data", "Web Data-journal",
        "Account Web Data", "Account Web Data-journal",
        "Affiliation Database", "Affiliation Database-journal",
        "Network Action Predictor", "Network Action Predictor-journal",
        "Reporting and NEL", "Reporting and NEL-journal",
        "Trust Tokens", "Trust Tokens-journal",
        "DIPS",
        "BrowsingTopicsSiteData", "BrowsingTopicsSiteData-journal",
        "BrowsingTopicsState",
        "Top Sites", "Top Sites-journal",
        "Shortcuts", "Shortcuts-journal",
        "ServerCertificate",
        "Safe Browsing Cookies", "Safe Browsing Cookies-journal",
        "heavy_ad_intervention_opt_out.db",
        "MediaDeviceSalts",
        "SharedStorage",
        "BookmarkMergedSurfaceOrdering",
        "ClientCertificates",
        "commerce_subscription_db",
        "discount_infos_db",
        "discounts_db",
        "chrome_cart_db",
        "engine_allowlist.bf",
        "parcel_tracking_db",
        "BudgetDatabase",
        ".DS_Store",
    ]

    @staticmethod
    def _dir_size_bytes(path: Path) -> int:
        """递归计算目录大小（字节）"""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def _iter_cleanable_dirs(self, profile_dir: Path):
        """枚举一个 profile 下所有可清理的目录"""
        for name in self.CLEANABLE_TOP_DIRS:
            d = profile_dir / name
            if d.exists():
                yield d
        default_dir = profile_dir / "Default"
        if default_dir.exists():
            for name in self.CLEANABLE_DEFAULT_DIRS:
                d = default_dir / name
                if d.exists():
                    yield d

    def _iter_cleanable_files(self, profile_dir: Path):
        """枚举一个 profile 下所有可清理的文件"""
        for name in self.CLEANABLE_TOP_FILES:
            f = profile_dir / name
            if f.exists():
                yield f
        default_dir = profile_dir / "Default"
        if default_dir.exists():
            for name in self.CLEANABLE_DEFAULT_FILES:
                f = default_dir / name
                if f.exists():
                    yield f

    def get_storage_stats(self) -> dict:
        """获取浏览器 profile 存储统计"""
        if not PROFILES_DIR.exists():
            return {"total_bytes": 0, "profile_count": 0, "cleanable_bytes": 0, "profiles": []}

        mapping_file = PROFILES_DIR / ".mapping.json"
        mapping: dict = {}
        if mapping_file.exists():
            try:
                mapping = json.loads(mapping_file.read_text())
            except Exception:
                pass

        # 反转 mapping: dir_name -> profile_id
        dir_to_pid = {v: k for k, v in mapping.items()}

        total_bytes = 0
        cleanable_bytes = 0
        profiles_info: list[dict] = []

        for child in sorted(PROFILES_DIR.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            size = self._dir_size_bytes(child)
            total_bytes += size

            # 计算可清理缓存大小（目录 + 文件）
            cache_size = sum(self._dir_size_bytes(d) for d in self._iter_cleanable_dirs(child))
            cache_size += sum(f.stat().st_size for f in self._iter_cleanable_files(child))
            cleanable_bytes += cache_size

            pid = dir_to_pid.get(child.name)
            profiles_info.append({
                "dir_name": child.name,
                "profile_id": int(pid) if pid else None,
                "total_bytes": size,
                "cache_bytes": cache_size,
            })

        # 按大小降序
        profiles_info.sort(key=lambda p: p["total_bytes"], reverse=True)

        return {
            "total_bytes": total_bytes,
            "profile_count": len(profiles_info),
            "cleanable_bytes": cleanable_bytes,
            "profiles": profiles_info,
        }

    def clean_all_caches(self) -> dict:
        """清理所有 profile 的 Chromium 缓存子目录（保留 cookies/登录态）"""
        # 先剔除僵尸 instance, 避免桌面手动关闭的浏览器仍占着 "运行中" 名额
        pruned_dead = self.prune_dead_instances()
        running_ids = set(self._instances.keys())
        mapping_file = PROFILES_DIR / ".mapping.json"
        mapping: dict = {}
        if mapping_file.exists():
            try:
                mapping = json.loads(mapping_file.read_text())
            except Exception:
                pass

        # 运行中的 profile 对应的目录名
        running_dirs: set = set()
        for pid in running_ids:
            dir_name = mapping.get(str(pid))
            if dir_name:
                running_dirs.add(dir_name)

        freed_bytes = 0
        cleaned_count = 0
        skipped_running = 0

        for child in PROFILES_DIR.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue

            if child.name in running_dirs:
                skipped_running += 1
                continue

            for subdir in self._iter_cleanable_dirs(child):
                size = self._dir_size_bytes(subdir)
                try:
                    shutil.rmtree(subdir)
                    freed_bytes += size
                except OSError as e:
                    logger.warning(f"清理 {subdir} 失败: {e}")

            for f in self._iter_cleanable_files(child):
                try:
                    size = f.stat().st_size
                    f.unlink()
                    freed_bytes += size
                except OSError as e:
                    logger.warning(f"清理 {f} 失败: {e}")

            cleaned_count += 1

        logger.info(f"缓存清理完成: 清理 {cleaned_count} 个 profile, 释放 {freed_bytes / 1024 / 1024:.1f} MB")

        return {
            "cleaned_count": cleaned_count,
            "freed_bytes": freed_bytes,
            "skipped_running": skipped_running,
            "pruned_dead": len(pruned_dead),
        }


# 全局单例
browser_manager = BrowserManager()


# ── 登录与 rapt 获取 ─────────────────────────────────────


def login_sync(page, email: str, password: str, totp_secret: str = "",
               recovery_email: str = "", cancel_token=None) -> bool:
    """DrissionPage 同步登录 Google 账号

    Returns: True = 登录成功
    """
    # 先检测是否已登录 (user-data-dir 保留了上次会话)
    if cancel_token:
        cancel_token.check()
    safe_navigate(page, "https://myaccount.google.com/", min_wait=2.0)
    url = safe_url(page)
    # 已登录会停在 myaccount.google.com, 未登录会重定向到 google.com/account/about 或 accounts.google.com
    if "myaccount.google.com" in url and "account/about" not in url and "signin" not in url:
        # 确认是目标账号 (页面上应该有邮箱)
        try:
            page_text = page.html or ""
        except Exception:
            logger.debug("page.html 读取失败, 作为空字符串处理", exc_info=True)
            page_text = ""
        if email.lower() in page_text.lower():
            logger.info(f"账号已登录 (session 有效), email={email}")
            return True
        else:
            logger.info(f"浏览器已登录其他账号, 继续登录 {email}")

    if cancel_token:
        cancel_token.check()
    safe_navigate(page, "https://accounts.google.com/signin", min_wait=1.5)

    # 已登录检测: 如果直接跳转到 myaccount 说明已登录
    if "myaccount.google.com" in safe_url(page):
        logger.info(f"账号已登录 (跳转到 myaccount), email={email}")
        return True

    # 邮箱
    email_input = safe_ele(page, SEL_EMAIL_INPUT, timeout=10)
    if not email_input:
        use_another = safe_ele(page, "text:Use another account", timeout=3)
        if use_another:
            safe_click(use_another, page=page)
            wait_page_stable(page, timeout=8)
            email_input = safe_ele(page, SEL_EMAIL_INPUT, timeout=10)
    if not email_input:
        logger.error(f"找不到邮箱输入框, URL: {safe_url(page)}")
        return False

    safe_input(email_input, email, page=page)
    time.sleep(0.5)
    email_next = safe_ele(page, SEL_EMAIL_NEXT, timeout=5)
    if email_next:
        safe_click(email_next, page=page)
    else:
        logger.warning(f"找不到邮箱下一步按钮, URL: {safe_url(page)}")
    wait_page_stable(page, timeout=10)

    # 密码
    if cancel_token:
        cancel_token.check()
    time.sleep(1)
    if not enter_password(page, password, timeout=15):
        logger.error("找不到密码输入框")
        return False

    # TOTP
    if "challenge" in safe_url(page) and totp_secret:
        enter_totp(page, totp_secret, timeout=10)

    wait_page_stable(page, timeout=8)

    # 处理登录后的中间页 (passkey 引导、恢复选项提示等)
    for _ in range(3):
        if cancel_token:
            cancel_token.check()
        url = safe_url(page)
        if "speedbump" in url or "passkeyenrollment" in url or "signinoptions" in url:
            # 点击 "以后再说" / "Not now" / "Skip" 跳过
            skip_btn = (
                safe_ele(page, SEL_SKIP_LATER_CN, timeout=2)
                or safe_ele(page, SEL_SKIP_NOT_NOW, timeout=2)
                or safe_ele(page, SEL_SKIP, timeout=2)
                or safe_ele(page, SEL_SKIP_LATER_CN2, timeout=1)
            )
            if skip_btn:
                safe_click(skip_btn, page=page)
                logger.info(f"跳过中间页: {url}")
                wait_page_stable(page, timeout=8)
                continue
        break

    # 登录成功判断: 多种成功后的 URL 模式
    url = safe_url(page)
    ok = (
        "myaccount" in url
        or "speedbump" in url  # passkey 引导页 (跳过按钮可能未点到, 但登录已完成)
        or "accounts.google.com/Default" in url
        or url.rstrip("/") + "/" == "accounts.google.com/"
        or ("signin" not in url and "challenge" not in url and "accounts.google.com" in url)
        or "google.com" in url and "signin" not in url and "challenge" not in url
    )
    # 额外检查: 如果页面上有头像/用户菜单, 说明已登录
    if not ok:
        avatar = safe_ele(page, "@aria-label=Google Account", timeout=2) or safe_ele(page, "img.gb_q", timeout=1)
        if avatar:
            ok = True
    logger.info(f"登录 {email}: {'OK' if ok else 'FAIL'}, URL: {url}")
    return ok


def handle_reauth_sync(page, password: str, totp_secret: str = "") -> str | None:
    """处理密码+TOTP 重验证, 返回 rapt token

    Returns: rapt token string, or None if no reauth needed
    """
    url = safe_url(page)
    if "challenge" not in url and "signin" not in url:
        # 检查 URL 中是否已有 rapt
        if "rapt=" in url:
            import re
            m = re.search(r'rapt=([^&]+)', url)
            return m.group(1) if m else None
        return None

    logger.info("密码重验证...")

    # 密码
    enter_password(page, password, timeout=5)

    # TOTP
    if "challenge" in safe_url(page) and totp_secret:
        enter_totp(page, totp_secret, timeout=5)

    # 提取 rapt
    import re
    url = safe_url(page)
    m = re.search(r'rapt=([^&]+)', url)
    rapt = m.group(1) if m else None
    logger.info(f"rapt: {'获取成功' if rapt else '未获取到'}")
    return rapt


def get_rapt_sync(page, target_path: str, password: str, totp_secret: str = "") -> str | None:
    """导航到需要 rapt 的页面, 完成重验证, 返回 rapt token"""
    safe_navigate(page, f"https://myaccount.google.com{target_path}", min_wait=2.0)
    return handle_reauth_sync(page, password, totp_secret)
