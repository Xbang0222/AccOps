"""共享的 Google 认证步骤 - 密码输入 / TOTP 验证

browser.py (login_sync, handle_reauth_sync) 和 oauth.py (_handle_password, _handle_totp)
中的密码/TOTP 输入逻辑高度重复, 提取到此模块统一维护。
"""

import logging
import time

import pyotp

from core.constants import (
    SEL_PASSWORD_INPUT,
    SEL_PASSWORD_NEXT,
    SEL_TOTP_INPUT,
    SEL_TOTP_NEXT,
)

logger = logging.getLogger(__name__)


def enter_password(page, password: str, timeout: int = 5) -> bool:
    """在页面中输入密码并点击下一步。

    Args:
        page: DrissionPage 页面对象
        password: 密码
        timeout: 等待输入框的超时秒数

    Returns:
        True 如果找到输入框并完成输入, False 如果找不到输入框
    """
    pwd_input = (
        page.ele(SEL_PASSWORD_INPUT, timeout=timeout)
        or page.ele('input[type="password"]', timeout=min(timeout, 3))
    )
    if not pwd_input:
        return False

    pwd_input.input(password)
    time.sleep(0.5)
    next_btn = (
        page.ele(SEL_PASSWORD_NEXT, timeout=3)
        or page.ele("text:Next", timeout=2)
        or page.ele("text:下一步", timeout=2)
    )
    if next_btn:
        next_btn.click()
        time.sleep(3)
    return True


def enter_totp(page, totp_secret: str, timeout: int = 5) -> bool:
    """在页面中输入 TOTP 验证码并点击下一步。

    处理 challenge/selection 页面 (选择 Authenticator) 和直接输入页面。

    Args:
        page: DrissionPage 页面对象
        totp_secret: TOTP 密钥
        timeout: 等待输入框的超时秒数

    Returns:
        True 如果成功输入验证码, False 如果找不到输入框或缺少密钥
    """
    if not totp_secret:
        return False

    code = pyotp.TOTP(totp_secret.replace(' ', '')).now()

    # 如果在 challenge/selection 页面, 先选择 Authenticator
    if "challenge/selection" in page.url:
        opt = (
            page.ele("text:Authenticator", timeout=3)
            or page.ele("text:Google Authenticator", timeout=2)
            or page.ele("text:验证器", timeout=2)
        )
        if opt:
            opt.click()
            time.sleep(2)

    totp_input = (
        page.ele(SEL_TOTP_INPUT, timeout=timeout)
        or page.ele('input[type="tel"]', timeout=min(timeout, 5))
    )
    if not totp_input:
        return False

    totp_input.input(code)
    time.sleep(0.5)
    btn = (
        page.ele(SEL_TOTP_NEXT, timeout=3)
        or page.ele("text:Next", timeout=2)
        or page.ele("text:下一步", timeout=2)
    )
    if btn:
        btn.click()
        time.sleep(3)
    return True
