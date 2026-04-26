"""家庭组发现 (discover) — 4 级回退：DB cookies → 浏览器 cookies → 自动登录 → 报错。"""
from __future__ import annotations

import json as _json
import logging

from core.constants import FAMILY_ROLE_ADMIN
from services.automation.core._shared import build_member_list, get_profile_id_from_page
from services.automation.core.login import auto_login_and_get_cookies
from services.automation.types import FamilyDiscoverResult
from services.browser import browser_manager
from services.family_api import FamilyAPI, TokenError

logger = logging.getLogger(__name__)


def discover_family_group_sync(page, on_step=None, cancel_token=None) -> FamilyDiscoverResult:
    """发现家庭组关系 (纯 RPC, 通过 page 提取 cookies)"""
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            members_info = api.query_members()

            if not members_info["has_family"]:
                return FamilyDiscoverResult(success=True, has_group=False, message="无家庭组")

            role = "manager" if members_info["is_admin"] else "member"
            members = build_member_list(members_info, admin_role_const=FAMILY_ROLE_ADMIN)

            return FamilyDiscoverResult(
                success=True,
                has_group=True,
                role=role,
                members=members,
                member_count=members_info["member_count"],
                message=f"家庭组: {role}, {members_info['member_count']} 成员",
            )
    except Exception as e:
        return FamilyDiscoverResult(success=False, message=str(e))


def _discover_from_cookies(cookies: dict) -> FamilyDiscoverResult:
    """纯 cookies 发现家庭组 + 查询订阅状态 (不需要浏览器)"""
    try:
        with FamilyAPI(cookies) as api:
            members_info = api.query_members()

            sub_status = ""
            sub_expiry = ""
            try:
                sub_info = api.query_subscription()
                sub_status = sub_info.get("status", "free")
                sub_expiry = sub_info.get("renew_date", "")
            except Exception as e:
                logger.warning(f"[discover] 查询订阅状态失败: {e}")

            if not members_info["has_family"]:
                return FamilyDiscoverResult(
                    success=True, has_group=False, message="无家庭组",
                    subscription_status=sub_status,
                    subscription_expiry=sub_expiry,
                )

            role = "manager" if members_info["is_admin"] else "member"
            members = build_member_list(members_info, admin_role_const=FAMILY_ROLE_ADMIN)

            return FamilyDiscoverResult(
                success=True,
                has_group=True,
                role=role,
                members=members,
                member_count=members_info["member_count"],
                message=f"家庭组: {role}, {members_info['member_count']} 成员",
                subscription_status=sub_status,
                subscription_expiry=sub_expiry,
            )
    except TokenError:
        return FamilyDiscoverResult(
            success=False,
            message="Cookies 已过期，请重新登录账号",
            cookies_expired=True,
        )
    except Exception as e:
        error_msg = str(e)
        if any(kw in error_msg.lower() for kw in ("401", "403", "redirect", "login", "sign in")):
            return FamilyDiscoverResult(
                success=False,
                message="Cookies 已过期，请重新登录账号",
                cookies_expired=True,
            )
        return FamilyDiscoverResult(success=False, message=f"查询失败: {error_msg}")


def _save_cookies_to_db(account_id: int, cookies: dict) -> None:
    """保存 cookies 到数据库"""
    try:
        from services.account import update_account_fields
        update_account_fields(account_id, cookies_json=_json.dumps(cookies))
        logger.info(f"[discover] cookies 已更新 → account #{account_id}")
    except Exception as e:
        logger.warning(f"[discover] 更新 cookies 失败: {e}")


def discover_family_by_cookies(
    account_id: int,
    saved_cookies_json: str,
    browser_profile_id: int | None = None,
    email: str = "",
    password: str = "",
    totp_secret: str = "",
    recovery_email: str = "",
) -> FamilyDiscoverResult:
    """智能发现家庭组: 保存的 cookies → 浏览器 cookies → 自动登录刷新 → 报错"""
    cookies: dict = {}
    if saved_cookies_json:
        try:
            cookies = _json.loads(saved_cookies_json)
        except (ValueError, TypeError):
            pass

    # 1. 尝试用保存的 cookies
    if cookies:
        result = _discover_from_cookies(cookies)
        if result.success:
            return result
        if not result.cookies_expired:
            return result
        logger.info(f"[discover] account #{account_id} 保存的 cookies 已过期, 尝试刷新")
    else:
        logger.info(f"[discover] account #{account_id} 没有保存的 cookies, 尝试获取")

    # 2. 尝试从运行中的浏览器获取新 cookies
    if browser_profile_id and browser_manager.is_running(browser_profile_id):
        fresh_cookies = browser_manager.get_cookies(browser_profile_id)
        if fresh_cookies:
            logger.info(f"[discover] 从运行中的浏览器获取到 {len(fresh_cookies)} 个 cookies")
            result = _discover_from_cookies(fresh_cookies)
            if result.success:
                _save_cookies_to_db(account_id, fresh_cookies)
                return result
            if not result.cookies_expired:
                return result
            logger.info("[discover] 浏览器 cookies 也已过期, 尝试自动登录")

    # 3. 自动登录刷新 cookies
    if browser_profile_id and email and password:
        logger.info(f"[discover] account #{account_id} 尝试自动登录获取新 cookies")
        fresh_cookies = auto_login_and_get_cookies(
            browser_profile_id, email, password, totp_secret, recovery_email
        )
        if fresh_cookies:
            result = _discover_from_cookies(fresh_cookies)
            if result.success:
                _save_cookies_to_db(account_id, fresh_cookies)
                return result
            return result
        else:
            return FamilyDiscoverResult(
                success=False,
                message="自动登录失败，无法获取最新 cookies",
                cookies_expired=True,
            )

    # 4. 没有可用的 cookies
    return FamilyDiscoverResult(
        success=False,
        message="未找到可用的登录信息，请先登录账号" if not cookies else "Cookies 已过期，请重新登录账号刷新",
        cookies_expired=True,
    )
