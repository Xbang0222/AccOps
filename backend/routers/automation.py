"""自动化操作路由 - Google 登录 / 家庭组管理 (REST 端点 + 共享工具函数)"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from deps import verify_token
from models.database import get_db, get_db_session, update_account_fields
from models.orm import Account, BrowserProfile, Group
from services.browser import browser_manager
from services.automation import (
    run_auto_login,
    run_create_family_group,
    run_send_family_invite,
    run_accept_family_invite,
    run_remove_family_member,
    run_leave_family_group,
    discover_family_by_cookies,
)
from services.group_sync import sync_group_after_action, sync_group_from_discover

from core.constants import (
    ACTION_FAMILY_CREATE,
    ACTION_FAMILY_ACCEPT,
    ACTION_FAMILY_REMOVE,
    ACTION_FAMILY_LEAVE,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/automation",
    tags=["自动化"],
    dependencies=[Depends(verify_token)],
)


# ---- 请求模型 ----

class AutoLoginRequest(BaseModel):
    account_id: int


class FamilyInviteRequest(BaseModel):
    account_id: int
    invite_email: str


class FamilyMemberRequest(BaseModel):
    account_id: int
    member_email: str


class AccountActionRequest(BaseModel):
    account_id: int


# ---- 工具函数 ----

def _get_profile_id(account_id: int, db: Session) -> int:
    """根据 account_id 获取对应 browser_profile, 要求浏览器已启动"""
    profile = (
        db.query(BrowserProfile)
        .filter(BrowserProfile.account_id == account_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号没有浏览器配置, 请先启动浏览器")

    if not browser_manager.is_running(profile.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="浏览器未启动, 请先启动浏览器")

    return profile.id


def _decrypt(value: str) -> str:
    """获取数据库字段值 (不再加密, 直接返回)"""
    return value or ""


def _save_cookies(account_id: int, profile_id: int):
    """从运行中的浏览器提取 cookies 并保存到数据库"""
    try:
        cookies = browser_manager.get_cookies(profile_id)
        if not cookies:
            return
        update_account_fields(account_id, cookies_json=json.dumps(cookies))
        logger.info(f"[cookies] 已保存 {len(cookies)} 个 cookies → account #{account_id}")
    except Exception as e:
        logger.warning(f"[cookies] 保存失败: {e}")


def _save_oauth_credential(account_id: int, credential: dict):
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
            account.updated_at = datetime.now(timezone.utc)
        logger.info(f"[oauth] 已保存 OAuth 凭证 → account #{account_id}")
    except Exception as e:
        logger.warning(f"[oauth] 保存 OAuth 凭证失败: {e}")


def _sync_account_state_after_login(
    account_id: int,
    profile_id: int,
    email: str,
    password: str,
    totp_secret: str = "",
    recovery_email: str = "",
):
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
        _save_subscription_status(account_id, result.subscription_status, result.subscription_expiry)
    except Exception as e:
        logger.warning(f"[login-sync] account #{account_id} 状态同步异常: {e}")


def _handle_login_success(
    account_id: int,
    profile_id: int,
    email: str,
    password: str,
    totp_secret: str = "",
    recovery_email: str = "",
):
    """登录成功后的统一收尾：保存 cookies 并同步账号状态。"""
    _save_cookies(account_id, profile_id)
    _sync_account_state_after_login(
        account_id,
        profile_id,
        email,
        password,
        totp_secret,
        recovery_email,
    )


def _save_subscription_status(account_id: int, subscription_status: str, subscription_expiry: str = ""):
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
                account.updated_at = datetime.now(timezone.utc)
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
                            m.updated_at = datetime.now(timezone.utc)
                    if members:
                        logger.info(f"[subscription] Ultra 已传播给 {len(members)} 个子号")
    except Exception as e:
        logger.warning(f"[subscription] 保存失败: {e}")


# ---- 自动登录 ----

@router.post("/login")
async def auto_login(req: AutoLoginRequest, db: Session = Depends(get_db)):
    """自动登录 Google 账号"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)

    # 从 notes 中提取验证链接
    from services.verification import extract_verification_link
    verification_url = extract_verification_link(account.notes or "") or ""

    result = await run_auto_login(
        profile_id=profile_id,
        email=account.email,
        password=_decrypt(account.password),
        totp_secret=_decrypt(account.totp_secret) or "",
        recovery_email=_decrypt(account.recovery_email) or "",
        verification_url=verification_url,
    )
    # 登录成功后保存 cookies
    if result.success:
        _handle_login_success(
            req.account_id,
            profile_id,
            account.email,
            _decrypt(account.password),
            _decrypt(account.totp_secret) or "",
            _decrypt(account.recovery_email) or "",
        )
    return result.to_dict()


# ---- 家庭组操作 ----

@router.post("/family/create")
async def create_family_group(req: AccountActionRequest, db: Session = Depends(get_db)):
    """创建家庭组"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    result = await run_create_family_group(profile_id)
    if result.success:
        _save_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_CREATE, req.account_id, result.success, result.message)
    return result.to_dict()


@router.post("/family/invite")
async def send_family_invite(req: FamilyInviteRequest, db: Session = Depends(get_db)):
    """发送家庭组邀请"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    result = await run_send_family_invite(profile_id, req.invite_email)
    if result.success:
        _save_cookies(req.account_id, profile_id)
    return result.to_dict()


@router.post("/family/accept")
async def accept_family_invite(req: AccountActionRequest, db: Session = Depends(get_db)):
    """接受家庭组邀请"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    result = await run_accept_family_invite(profile_id)
    if result.success:
        _save_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_ACCEPT, req.account_id, result.success, result.message)
    return result.to_dict()


@router.post("/family/remove-member")
async def remove_family_member(req: FamilyMemberRequest, db: Session = Depends(get_db)):
    """移除家庭组成员 (需要管理员权限, 可能需要密码 + 2FA 重验证)"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    password = _decrypt(account.password)
    totp_secret = _decrypt(account.totp_secret) or ""
    result = await run_remove_family_member(profile_id, req.member_email, password=password, totp_secret=totp_secret)
    if result.success:
        _save_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_REMOVE, req.account_id, result.success, result.message, {"member_email": req.member_email})
    return result.to_dict()


@router.post("/family/leave")
async def leave_family_group(req: AccountActionRequest, db: Session = Depends(get_db)):
    """退出/删除家庭组 (管理员删除需要密码 + 2FA 重验证)"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    password = _decrypt(account.password)
    totp_secret = _decrypt(account.totp_secret) or ""
    result = await run_leave_family_group(profile_id, password=password, totp_secret=totp_secret)
    if result.success:
        _save_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_LEAVE, req.account_id, result.success, result.message)
    return result.to_dict()


# ---- 家庭组同步 (纯 HTTP, 不需要浏览器) ----

@router.post("/family/discover")
async def discover_family(req: AccountActionRequest, db: Session = Depends(get_db)):
    """同步家庭组状态 (优先用保存的 cookies, cookies 过期自动登录刷新)"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    # 获取浏览器 profile_id (可选, 用于 cookies 过期时的回退)
    profile = (
        db.query(BrowserProfile)
        .filter(BrowserProfile.account_id == req.account_id)
        .first()
    )
    browser_profile_id = profile.id if profile else None

    # 解密凭证 (用于 cookies 过期时自动登录)
    email = account.email
    password = _decrypt(account.password)
    totp_secret = _decrypt(account.totp_secret) or ""
    recovery_email = _decrypt(account.recovery_email) or ""

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        discover_family_by_cookies,
        req.account_id,
        account.cookies_json or "",
        browser_profile_id,
        email,
        password,
        totp_secret,
        recovery_email,
    )

    # 同步分组关系
    if result.success:
        sync_group_from_discover(req.account_id, result)
        # 保存订阅状态
        _save_subscription_status(req.account_id, result.subscription_status, result.subscription_expiry)

    return result.to_dict()


# ---- OAuth 凭证 API ----

@router.get("/oauth/credential/{account_id}")
async def get_oauth_credential(account_id: int, db: Session = Depends(get_db)):
    """获取账号的 OAuth 认证 JSON"""
    account = db.query(Account).get(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not account.oauth_credential_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该账号暂无 OAuth 凭证")
    return json.loads(account.oauth_credential_json)


@router.get("/oauth/credential/{account_id}/download")
async def download_oauth_credential(account_id: int, db: Session = Depends(get_db)):
    """下载 OAuth 认证 JSON 文件"""
    account = db.query(Account).get(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not account.oauth_credential_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该账号暂无 OAuth 凭证")

    email = account.email or "unknown"
    filename = f"antigravity-{email}.json"
    content = account.oauth_credential_json
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
