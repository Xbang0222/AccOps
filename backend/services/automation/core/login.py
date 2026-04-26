"""登录相关的 sync 操作（DrissionPage 浏览器交互）。"""
from __future__ import annotations

import logging

from services.automation.types import AutomationResult, StepTracker
from services.browser import browser_manager, login_sync

logger = logging.getLogger(__name__)


def auto_login_sync(page, email: str, password: str, totp_secret: str = "",
                    recovery_email: str = "", verification_url: str = "",
                    on_step=None, cancel_token=None) -> AutomationResult:
    """自动登录 Google 账号"""
    tracker = StepTracker("login", on_step)

    tracker.step("打开登录页", "info", "accounts.google.com")
    if cancel_token:
        cancel_token.check()
    ok = login_sync(page, email, password, totp_secret, recovery_email, cancel_token=cancel_token)

    if ok:
        return tracker.result(True, f"登录成功: {email}")
    else:
        return tracker.result(False, f"登录失败: {email}", step="login")


def auto_login_and_get_cookies(
    browser_profile_id: int,
    email: str,
    password: str,
    totp_secret: str = "",
    recovery_email: str = "",
) -> dict | None:
    """自动启动浏览器 → 登录 → 获取 cookies → 关闭浏览器

    注意: 强制关闭 headless 模式, Google 会检测并拦截 headless 登录。
    """
    import asyncio as _aio

    already_running = browser_manager.is_running(browser_profile_id)

    if not already_running:
        try:
            from models.database import get_db_session
            from models.orm import BrowserProfile
            with get_db_session() as db:
                profile = db.query(BrowserProfile).filter(BrowserProfile.id == browser_profile_id).first()
                if not profile:
                    logger.warning(f"[auto-login] 找不到浏览器配置 profile_id={browser_profile_id}")
                    return None

            try:
                loop = _aio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                # 在运行中的 event loop 里, 用线程启动
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: _aio.run(browser_manager.launch(profile, headless=False)))
                    future.result(timeout=30)
            else:
                _aio.run(browser_manager.launch(profile, headless=False))

            logger.info(f"[auto-login] 浏览器已启动 profile_id={browser_profile_id}")
        except Exception as e:
            logger.error(f"[auto-login] 启动浏览器失败: {e}")
            return None

    page = browser_manager.get_page(browser_profile_id)
    if not page:
        logger.error(f"[auto-login] 获取 page 失败 profile_id={browser_profile_id}")
        return None

    try:
        ok = login_sync(page, email, password, totp_secret, recovery_email)
        if not ok:
            logger.warning(f"[auto-login] 登录失败 email={email}")
            return None

        logger.info(f"[auto-login] 登录成功 email={email}")
        cookies = browser_manager.get_cookies(browser_profile_id)
        if not cookies:
            logger.warning("[auto-login] 登录成功但获取 cookies 为空")
            return None

        logger.info(f"[auto-login] 获取到 {len(cookies)} 个 cookies")
        return cookies
    except Exception as e:
        logger.error(f"[auto-login] 登录异常: {e}")
        return None
    finally:
        if not already_running:
            try:
                if browser_manager.is_running(browser_profile_id):
                    try:
                        loop = _aio.get_running_loop()
                    except RuntimeError:
                        loop = None

                    if loop is not None:
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(lambda: _aio.run(browser_manager.stop(browser_profile_id)))
                            future.result(timeout=15)
                    else:
                        _aio.run(browser_manager.stop(browser_profile_id))
                    logger.info(f"[auto-login] 浏览器已关闭 profile_id={browser_profile_id}")
            except Exception as e:
                logger.warning(f"[auto-login] 关闭浏览器失败: {e}")
