"""自动化操作 - 共享工具函数 (从 routers/automation.py 提取)"""
import json
import logging
from datetime import UTC, datetime

from models.database import get_db_session
from models.orm import Account, Group
from services.account import update_account_fields
from services.automation import discover_family_by_cookies
from services.browser import browser_manager

logger = logging.getLogger(__name__)


def decrypt_field(value: str) -> str:
    """获取数据库字段值 (不再加密, 直接返回)"""
    return value or ""


def save_browser_cookies(account_id: int, profile_id: int) -> None:
    """从运行中的浏览器提取 cookies 并保存到数据库"""
    try:
        cookies = browser_manager.get_cookies(profile_id)
        if not cookies:
            return
        update_account_fields(account_id, cookies_json=json.dumps(cookies))
        logger.info(f"[cookies] 已保存 {len(cookies)} 个 cookies → account #{account_id}")
    except Exception as e:
        logger.warning(f"[cookies] 保存失败: {e}")


def save_oauth_credential(account_id: int, credential: dict) -> None:
    """保存 OAuth 认证 JSON 到数据库"""
    try:
        with get_db_session() as db:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return
            # 如果凭证中没有 email, 用账号的 email
            if "email" not in credential:
                credential["email"] = account.email
            account.oauth_credential_json = json.dumps(credential)
            account.updated_at = datetime.now(UTC)
        logger.info(f"[oauth] 已保存 OAuth 凭证 → account #{account_id}")
    except Exception as e:
        logger.warning(f"[oauth] 保存 OAuth 凭证失败: {e}")


def sync_account_state_after_login(
    account_id: int,
    profile_id: int,
    email: str,
    password: str,
    totp_secret: str = "",
    recovery_email: str = "",
) -> None:
    """登录成功后立即同步账号状态（订阅、地区），但不修改已有的分组关系。"""
    try:
        cookies = browser_manager.get_cookies(profile_id)
        if not cookies:
            logger.warning(f"[login-sync] account #{account_id} 未获取到 cookies，跳过状态同步")
            return

        result = discover_family_by_cookies(
            account_id,
            json.dumps(cookies),
            profile_id,
            email,
            password,
            totp_secret,
            recovery_email,
        )
        if not result.success:
            logger.warning(f"[login-sync] account #{account_id} 状态同步失败: {result.message}")
            return

        # 仅同步订阅状态，不触发分组同步（避免覆盖用户手动设置的分组关系）
        # 分组同步应通过用户主动执行 discover 操作触发
        save_subscription_status(account_id, result.subscription_status, result.subscription_expiry)
    except Exception as e:
        logger.warning(f"[login-sync] account #{account_id} 状态同步异常: {e}")


def handle_login_success(
    account_id: int,
    profile_id: int,
    email: str,
    password: str,
    totp_secret: str = "",
    recovery_email: str = "",
) -> None:
    """登录成功后的统一收尾：保存 cookies 并同步账号状态。"""
    save_browser_cookies(account_id, profile_id)
    sync_account_state_after_login(
        account_id,
        profile_id,
        email,
        password,
        totp_secret,
        recovery_email,
    )


def save_subscription_status(account_id: int, subscription_status: str, subscription_expiry: str = "") -> None:
    """保存订阅状态到数据库，主号 Ultra 自动传播给同组所有子号"""
    if not subscription_status:
        return
    try:
        with get_db_session() as db:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return
            changed = False
            if account.subscription_status != subscription_status:
                account.subscription_status = subscription_status
                changed = True
            if subscription_expiry and account.subscription_expiry != subscription_expiry:
                account.subscription_expiry = subscription_expiry
                changed = True
            if changed:
                account.updated_at = datetime.now(UTC)
                logger.info(f"[subscription] account #{account_id} → {subscription_status} {subscription_expiry}")

            # 主号 Ultra → 传播给同组所有子号
            if subscription_status == "ultra" and account.family_group_id:
                group = db.query(Group).filter(Group.id == account.family_group_id).first()
                if group and group.main_account_id == account.id:
                    members = (
                        db.query(Account)
                        .filter(Account.family_group_id == group.id, Account.id != account.id)
                        .all()
                    )
                    for m in members:
                        m_changed = False
                        if m.subscription_status != subscription_status:
                            m.subscription_status = subscription_status
                            m_changed = True
                        if subscription_expiry and m.subscription_expiry != subscription_expiry:
                            m.subscription_expiry = subscription_expiry
                            m_changed = True
                        if m_changed:
                            m.updated_at = datetime.now(UTC)
                    if members:
                        logger.info(f"[subscription] Ultra 已传播给 {len(members)} 个子号")
    except Exception as e:
        logger.warning(f"[subscription] 保存失败: {e}")
