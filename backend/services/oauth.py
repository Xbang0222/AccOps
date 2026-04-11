"""Google OAuth 自动化服务 - 使用已登录浏览器自动完成 OAuth 授权

流程:
  1. 构建 OAuth 授权 URL (antigravity 的 client_id + scopes)
  2. 用已登录的 DrissionPage 浏览器打开 URL → 自动同意授权
  3. 处理可能的 2FA 验证 / 密码重验证
  4. 从回调 URL 中提取 authorization code
  5. 用 code 换取 access_token + refresh_token
  6. 获取 project_id (via loadCodeAssist)
  7. 生成认证 JSON
"""

import json
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.constants import (
    SEL_PASSWORD_INPUT,
    SEL_TOTP_INPUT,
    SEL_PHONE_NUMBER_INPUT,
    SEL_PHONE_CODE_INPUT,
    SEL_PHONE_VERIFY_NEXT,
    SMS_WAIT_TIMEOUT,
    SMS_POLL_INTERVAL,
)
from services.oauth_support import (
    build_auth_url,
    check_for_code,
    check_for_error,
    exchange_code_for_tokens,
    fetch_project_id,
    handle_password,
    handle_totp,
    is_password_page,
    is_totp_page,
    probe_api,
    try_click_consent_buttons,
)
from services.page_wait import (
    safe_navigate,
    safe_ele,
    safe_click,
    safe_input,
    wait_page_stable,
)

logger = logging.getLogger(__name__)
# ── 浏览器自动 OAuth (核心) ─────────────────────────────


def oauth_sync(page, on_step=None, password: str = "", totp_secret: str = "",
               cancel_token=None):
    """用已登录的浏览器自动完成 OAuth 授权流程

    Args:
        page: DrissionPage 的 WebPage 实例 (已登录 Google)
        on_step: 步骤回调函数
        password: 账号密码 (用于密码重验证)
        totp_secret: TOTP 密钥 (用于 2FA 验证)

    Returns:
        AutomationResult
    """
    from services.automation import StepTracker, AutomationResult, CancelledError

    tracker = StepTracker("oauth", on_step)

    try:
        # Step 0: 年龄认证检测
        from services.age_verification import check_and_verify_age
        tracker.step("年龄认证检测", "info")
        age_result = check_and_verify_age(page, on_step)
        if age_result.get("status") == "verified":
            tracker.step("年龄认证", "ok", age_result.get("message", "已通过"))
        elif not age_result.get("success"):
            tracker.step("年龄认证", "fail", age_result.get("message", ""))
            return tracker.result(False, age_result.get("message", "年龄认证失败"), step="age_verify")
        else:
            tracker.step("年龄认证", "skip", age_result.get("message", ""))

        # Step 1: 构建 OAuth URL
        state = secrets.token_urlsafe(32)
        auth_url = build_auth_url(state)
        tracker.step("构建 OAuth URL", "ok")

        # Step 2: 浏览器打开 OAuth URL
        tracker.step("打开授权页面", "info", "导航到 Google OAuth...")
        safe_navigate(page, auth_url, min_wait=2.0)

        # Step 3: 处理授权页面循环
        # 可能遇到: 选择账号 → 密码验证 → 2FA 验证 → 同意授权 → 回调
        tracker.step("处理授权", "info", "检查授权页面...")
        max_wait = 60  # 增加等待时间, 因为可能需要 2FA
        code = None
        password_handled = False
        totp_handled = False

        for tick in range(max_wait):
            if cancel_token:
                cancel_token.check()
            current_url = page.url

            # 1) 检查是否已经回调 (拿到 code)
            code = check_for_code(current_url)
            if code:
                break

            # 2) 检查是否有 error
            error = check_for_error(current_url)
            if error:
                return tracker.result(False, f"授权被拒绝: {error}", step="auth")

            # 3) 如果页面要求选择账号, 点击当前账号
            if "accountchooser" in current_url or "selectaccount" in current_url:
                account_clicked = False
                # 策略1: data-identifier 属性 (Google v2)
                account_btn = safe_ele(page, "@data-identifier", timeout=1)
                if account_btn:
                    account_clicked = safe_click(account_btn, page=page)
                # 策略2: data-email 属性 (Google v3)
                if not account_clicked:
                    account_btn = safe_ele(page, "@data-email", timeout=0.5)
                    if account_btn:
                        account_clicked = safe_click(account_btn, page=page)
                # 策略3: 账号列表项 (li[role] 或包含邮箱的可点击元素)
                if not account_clicked:
                    account_btn = (
                        safe_ele(page, 'li[data-authuser]', timeout=0.5)
                        or safe_ele(page, 'div[data-authuser]', timeout=0.5)
                        or safe_ele(page, 'text:@gmail.com', timeout=0.5)
                    )
                    if account_btn:
                        account_clicked = safe_click(account_btn, page=page)
                if account_clicked:
                    tracker.step("选择账号", "ok")
                    wait_page_stable(page, timeout=8)
                    continue

            # 4) 密码重验证页面
            if not password_handled and is_password_page(page):
                if not password:
                    return tracker.result(False, "需要密码重验证但账号无密码", step="password")
                if handle_password(page, password, tracker):
                    password_handled = True
                    continue
                else:
                    return tracker.result(False, "密码验证失败", step="password")

            # 5) 2FA/TOTP 验证页面
            if not totp_handled and is_totp_page(page):
                if handle_totp(page, totp_secret, tracker):
                    totp_handled = True
                    continue
                else:
                    return tracker.result(False, "2FA 验证失败", step="totp")

            # 6) 尝试点击 OAuth 同意按钮
            if try_click_consent_buttons(page):
                tracker.step("点击授权按钮", "ok")
                wait_page_stable(page, timeout=8)
                continue

            # 7) 检查是否有 "Check your phone" 类型的等待提示 (Google Prompt)
            if "challenge" in current_url and not is_password_page(page) and not is_totp_page(page):
                if tick % 5 == 0:
                    tracker.step("等待验证", "info", f"请在手机上确认或等待... ({tick}s)")

            time.sleep(1)

        if not code:
            # 最后一次检查 URL
            final_url = page.url
            code = check_for_code(final_url)
            if not code:
                return tracker.result(False, f"授权超时, 未获取到 code. URL: {final_url[:100]}", step="auth")

        tracker.step("获取授权码", "ok", f"code: {code[:20]}...")

        # Step 4: 交换 token
        tracker.step("交换 Token", "info", "用 code 换取 access_token...")
        token_resp = exchange_code_for_tokens(code)
        access_token = token_resp.get("access_token", "")
        refresh_token = token_resp.get("refresh_token", "")
        expires_in = token_resp.get("expires_in", 3599)

        if not access_token:
            return tracker.result(False, "Token 交换返回空 access_token", step="token")
        tracker.step("Token 获取成功", "ok")

        # Step 5: 获取 project_id
        tracker.step("获取 Project ID", "info", "调用 loadCodeAssist...")
        project_id = ""
        try:
            project_id = fetch_project_id(access_token)
            if project_id:
                tracker.step("Project ID", "ok", project_id)
            else:
                tracker.step("Project ID", "skip", "未获取到, 不影响使用")
        except Exception as e:
            tracker.step("Project ID", "skip", f"获取失败: {e}")

        # Step 6: 构建认证 JSON
        now = datetime.now(timezone.utc)
        credential = {
            "type": "antigravity",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "timestamp": int(now.timestamp() * 1000),
            "expired": (now + timedelta(seconds=expires_in)).isoformat(),
        }
        if project_id:
            credential["project_id"] = project_id

        tracker.step("认证文件生成", "ok")

        # Step 7: 探测 API 可用性
        tracker.step("API 探测", "info", "发送测试请求...")
        try:
            api_ok, api_msg, validation_url = probe_api(access_token, project_id)
            if api_ok:
                tracker.step("API 探测", "ok", "API 可用")
            else:
                tracker.step("API 探测", "fail", api_msg)
                if validation_url:
                    tracker.step("验证链接", "info", validation_url)
                    credential["validation_url"] = validation_url

                    # Step 8: 自动手机号验证
                    tracker.step("自动接码验证", "info", "开始自动验证...")
                    verify_result = auto_phone_verify_sync(page, validation_url, on_step, cancel_token=cancel_token)
                    verify_ok = verify_result.success if hasattr(verify_result, "success") else verify_result.get("success", False)
                    verify_msg = verify_result.message if hasattr(verify_result, "message") else verify_result.get("message", "")
                    if verify_ok:
                        tracker.step("自动接码验证", "ok", verify_msg)
                        credential.pop("validation_url", None)
                        # 保存最终页面信息
                        credential["verify_final_url"] = page.url
                        try:
                            page.get_screenshot(".verification_final.png")
                        except Exception:
                            pass
                    else:
                        tracker.step("自动接码验证", "fail", verify_msg or "验证失败")
        except Exception as e:
            tracker.step("API 探测", "skip", f"探测异常: {e}")

        return tracker.result(True, "OAuth 认证成功", extra={"credential": credential})

    except Exception as e:
        return tracker.result(False, f"OAuth 异常: {e}", step="error")


# ── 自动手机号验证 ─────────────────────────────────────

def auto_phone_verify_sync(page, validation_url: str, on_step=None, cancel_token=None) -> dict:
    """用已登录浏览器自动完成 Google 手机号验证

    流程:
    1. 打开 validation_url → 选择 "Verify your phone number"
    2. 从接码平台购买号码
    3. 输入手机号 → 点 Next
    4. 轮询等待验证码
    5. 输入验证码 → 完成

    Args:
        page: DrissionPage WebPage 实例 (已登录)
        validation_url: Google 验证链接
        on_step: 步骤回调

    Returns:
        {"success": bool, "message": str}
    """
    from services.automation import StepTracker
    from models.database import get_db_session
    from models.orm import Config, SmsProvider
    from services.sms_api import create_provider

    tracker = StepTracker("phone_verify", on_step)

    try:
        # Step 1: 获取接码提供商
        tracker.step("获取接码配置", "info")
        with get_db_session() as db:
            # 读取默认提供商
            row = db.query(Config).filter(Config.key == "default_sms_provider_id").first()
            provider = None
            if row:
                provider = db.query(SmsProvider).filter(SmsProvider.id == int(row.value)).first()
            if not provider:
                provider = db.query(SmsProvider).first()
            if not provider or not provider.api_key:
                return tracker.result(False, "未配置接码提供商", step="sms_config")

            sms_api = create_provider(provider.provider_type, provider.api_key)
            service = provider.default_service or "go"
            country = provider.default_country or 2
            tracker.step("接码配置", "ok", f"{provider.name} | 服务={service} 国家={country}")

        # Step 2: 打开验证页面
        if cancel_token:
            cancel_token.check()
        tracker.step("打开验证页面", "info")
        safe_navigate(page, validation_url, min_wait=3.0)

        # Step 3: 选择 "Verify your phone number"
        if "uplevelingstep/selection" in page.url:
            tracker.step("选择验证方式", "info", "选择手机号验证")
            phone_option = None
            for sel in ["text:Verify your phone number", "text:验证您的电话号码", "text:phone number"]:
                phone_option = safe_ele(page, sel, timeout=3)
                if phone_option:
                    break
            if not phone_option:
                return tracker.result(False, "未找到手机验证选项", step="select_method")
            safe_click(phone_option, page=page)
            wait_page_stable(page, timeout=10)
            tracker.step("选择验证方式", "ok")

        # Step 4: 购买号码
        if cancel_token:
            cancel_token.check()
        tracker.step("购买号码", "info", f"服务={service} 国家={country}")
        ok, number_data = sms_api.get_number(service=service, country=country)
        if not ok:
            return tracker.result(False, f"购买号码失败: {number_data}", step="buy_number")

        activation_id = number_data["activation_id"]
        phone_number = number_data["phone_number"]
        tracker.step("号码已购买", "ok", phone_number)

        # Step 5: 输入手机号
        tracker.step("输入手机号", "info", phone_number)

        # 查找手机号输入框
        phone_input = safe_ele(page, SEL_PHONE_NUMBER_INPUT, timeout=5) or safe_ele(page, "input[type='tel']", timeout=3)
        if not phone_input:
            sms_api.cancel(activation_id)
            return tracker.result(False, "找不到手机号输入框", step="phone_input")

        # 输入带+号的完整号码, Google 会自动切换国家
        phone_with_plus = f"+{phone_number}" if not phone_number.startswith("+") else phone_number
        safe_input(phone_input, phone_with_plus, page=page, clear_first=True)
        time.sleep(1)

        # 点 Next
        next_btn = (
            safe_ele(page, "text:Next", timeout=3)
            or safe_ele(page, "text:下一步", timeout=2)
            or safe_ele(page, "#next", timeout=2)
            or safe_ele(page, "text:Send", timeout=2)
        )
        if next_btn:
            safe_click(next_btn, page=page)
            wait_page_stable(page, timeout=10)
        tracker.step("已发送验证码", "ok")

        # 检查是否有错误 (号码无效等)
        error_ele = (
            safe_ele(page, "text:This phone number cannot be used", timeout=2)
            or safe_ele(page, "text:didn't recognize", timeout=1)
            or safe_ele(page, "text:无法使用此电话号码", timeout=1)
        )
        if error_ele:
            sms_api.cancel(activation_id)
            return tracker.result(False, f"号码被拒绝: {phone_number}", step="phone_rejected")

        # Step 6: 等待验证码
        if cancel_token:
            cancel_token.check()
        tracker.step("等待验证码", "info", f"轮询中 (activation={activation_id})")
        code_ok, code, sms_text = sms_api.wait_for_code(activation_id, timeout=SMS_WAIT_TIMEOUT, interval=SMS_POLL_INTERVAL)
        if not code_ok:
            sms_api.cancel(activation_id)
            return tracker.result(False, f"未收到验证码: {sms_text}", step="wait_code")
        tracker.step("收到验证码", "ok", code)

        # Step 7: 输入验证码
        if cancel_token:
            cancel_token.check()
        tracker.step("输入验证码", "info", code)

        # 查找验证码输入框 (Google 用 #idvAnyPhonePin)
        code_input = (
            safe_ele(page, SEL_PHONE_CODE_INPUT, timeout=5)
            or safe_ele(page, "#code", timeout=3)
            or safe_ele(page, "input[type='tel']", timeout=3)
        )
        if not code_input:
            sms_api.finish(activation_id)
            return tracker.result(False, "找不到验证码输入框", step="code_input")

        # 输入框预填了 "G-", 只需输入纯数字验证码
        safe_input(code_input, code, page=page, clear_first=True)
        time.sleep(1)

        # 点确认 (Google 用 #idvanyphoneverifyNext)
        verify_btn = (
            safe_ele(page, SEL_PHONE_VERIFY_NEXT, timeout=3)
            or safe_ele(page, "text:Next", timeout=2)
            or safe_ele(page, "text:Verify", timeout=2)
            or safe_ele(page, "text:下一步", timeout=2)
        )
        if verify_btn:
            safe_click(verify_btn, page=page)
            wait_page_stable(page, timeout=10)

        # Step 8: 完成激活
        sms_api.finish(activation_id)
        tracker.step("验证完成", "ok")

        # 检查是否成功 (页面跳转到成功页)
        current_url = page.url
        if "auth_success" in current_url or "gemini-code-assist" in current_url or "myaccount" in current_url:
            return tracker.result(True, "手机号验证成功")

        # 可能还在验证页面, 检查是否有错误
        error_ele2 = safe_ele(page, "text:Wrong code", timeout=2) or safe_ele(page, "text:验证码错误", timeout=1)
        if error_ele2:
            return tracker.result(False, "验证码错误", step="wrong_code")

        # 不确定是否成功, 返回当前 URL
        return tracker.result(True, f"验证流程已完成, URL: {current_url[:80]}")

    except Exception as e:
        return tracker.result(False, f"自动验证异常: {e}", step="error")
