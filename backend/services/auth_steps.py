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
from services.page_wait import (
    safe_ele,
    safe_click,
    safe_input,
    safe_url,
    wait_page_stable,
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
        safe_ele(page, SEL_PASSWORD_INPUT, timeout=timeout)
        or safe_ele(page, 'input[type="password"]', timeout=min(timeout, 3))
    )
    if not pwd_input:
        return False

    safe_input(pwd_input, password, page=page)
    time.sleep(0.5)
    next_btn = (
        safe_ele(page, SEL_PASSWORD_NEXT, timeout=3)
        or safe_ele(page, "text:Next", timeout=2)
        or safe_ele(page, "text:下一步", timeout=2)
    )
    if next_btn:
        safe_click(next_btn, page=page)
        wait_page_stable(page, timeout=10)
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
    if "challenge/selection" in safe_url(page):
        opt = (
            safe_ele(page, "text:Authenticator", timeout=3)
            or safe_ele(page, "text:Google Authenticator", timeout=2)
            or safe_ele(page, "text:验证器", timeout=2)
        )
        if opt:
            safe_click(opt, page=page)
            wait_page_stable(page, timeout=8)

    totp_input = (
        safe_ele(page, SEL_TOTP_INPUT, timeout=timeout)
        or safe_ele(page, 'input[type="tel"]', timeout=min(timeout, 5))
    )
    if not totp_input:
        return False

    safe_input(totp_input, code, page=page)
    time.sleep(0.5)
    btn = (
        safe_ele(page, SEL_TOTP_NEXT, timeout=3)
        or safe_ele(page, "text:Next", timeout=2)
        or safe_ele(page, "text:下一步", timeout=2)
    )
    if btn:
        safe_click(btn, page=page)
        wait_page_stable(page, timeout=10)
    return True
