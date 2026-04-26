"""异步包装器 — 把 sync 函数挂到 executor 上，给 FastAPI router/WebSocket 使用。"""
from __future__ import annotations

import asyncio

from services.automation.core.family_ops import (
    accept_family_invite_sync,
    create_family_group_sync,
    leave_family_group_sync,
    remove_family_member_sync,
    send_family_invite_sync,
)
from services.automation.core.login import auto_login_sync
from services.automation.types import AutomationResult, FamilyDiscoverResult
from services.browser import browser_manager


async def _run_sync(fn, *args, **kwargs):
    """Run a synchronous function in the default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _get_page_or_fail(profile_id: int, result_cls=AutomationResult):
    """Get page from browser_manager, or return a failure result."""
    page = browser_manager.get_page(profile_id)
    if not page:
        if result_cls is AutomationResult:
            return None, AutomationResult(success=False, message="浏览器未启动", step="init")
        else:
            return None, FamilyDiscoverResult(success=False, message="浏览器未启动")
    return page, None


async def run_auto_login(profile_id: int, email: str, password: str,
                         totp_secret: str = "", recovery_email: str = "",
                         verification_url: str = "", on_step=None,
                         cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(
        auto_login_sync, page, email, password, totp_secret,
        recovery_email, verification_url, on_step, cancel_token=cancel_token,
    )


async def run_create_family_group(profile_id: int, on_step=None,
                                  cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(create_family_group_sync, page, on_step,
                           cancel_token=cancel_token)


async def run_send_family_invite(profile_id: int, invite_email: str,
                                 on_step=None, cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(send_family_invite_sync, page, invite_email, on_step,
                           cancel_token=cancel_token)


async def run_accept_family_invite(profile_id: int, on_step=None,
                                   cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(accept_family_invite_sync, page, on_step,
                           cancel_token=cancel_token)


async def run_remove_family_member(profile_id: int, member_email: str,
                                   password: str = "", totp_secret: str = "",
                                   on_step=None, cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(
        remove_family_member_sync, page, member_email, password, totp_secret, on_step,
    )


async def run_leave_family_group(profile_id: int, password: str = "",
                                 totp_secret: str = "", on_step=None,
                                 cancel_token=None) -> AutomationResult:
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    return await _run_sync(leave_family_group_sync, page, password, totp_secret, on_step)


async def run_oauth(profile_id: int, on_step=None, password: str = "", totp_secret: str = "",
                    cancel_token=None) -> AutomationResult:
    """在已登录浏览器中自动完成 OAuth 授权"""
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    from services.oauth import oauth_sync
    return await _run_sync(oauth_sync, page, on_step, password, totp_secret,
                           cancel_token=cancel_token)


async def run_phone_verify(profile_id: int, validation_url: str, on_step=None,
                           cancel_token=None) -> AutomationResult:
    """在已登录浏览器中自动完成手机号验证。"""
    page, err = _get_page_or_fail(profile_id)
    if err:
        return err
    from services.oauth import auto_phone_verify_sync
    result = await _run_sync(
        auto_phone_verify_sync, page, validation_url, on_step, cancel_token=cancel_token,
    )
    return AutomationResult(
        success=result.get("success", False),
        message=result.get("message", ""),
        step="phone_verify",
        extra=result,
    )
