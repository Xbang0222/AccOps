"""自动化操作路由 - Google 登录 / 家庭组管理 (REST 端点)"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.constants import (
    ACTION_FAMILY_ACCEPT,
    ACTION_FAMILY_CREATE,
    ACTION_FAMILY_LEAVE,
    ACTION_FAMILY_REMOVE,
)
from deps import verify_token
from models.database import get_db
from models.orm import Account, BrowserProfile
from services.automation import (
    discover_family_by_cookies,
    run_accept_family_invite,
    run_auto_login,
    run_create_family_group,
    run_leave_family_group,
    run_remove_family_member,
    run_send_family_invite,
)
from services.automation.persistence import (
    decrypt_field,
    handle_login_success,
    save_browser_cookies,
    save_subscription_status,
)
from services.browser import browser_manager
from services.group_sync import sync_group_after_action, sync_group_from_discover

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
        password=decrypt_field(account.password),
        totp_secret=decrypt_field(account.totp_secret) or "",
        recovery_email=decrypt_field(account.recovery_email) or "",
        verification_url=verification_url,
    )
    # 登录成功后保存 cookies
    if result.success:
        handle_login_success(
            req.account_id,
            profile_id,
            account.email,
            decrypt_field(account.password),
            decrypt_field(account.totp_secret) or "",
            decrypt_field(account.recovery_email) or "",
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
        save_browser_cookies(req.account_id, profile_id)
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
        save_browser_cookies(req.account_id, profile_id)
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
        save_browser_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_ACCEPT, req.account_id, result.success, result.message)
    return result.to_dict()


@router.post("/family/remove-member")
async def remove_family_member(req: FamilyMemberRequest, db: Session = Depends(get_db)):
    """移除家庭组成员 (需要管理员权限, 可能需要密码 + 2FA 重验证)"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    password = decrypt_field(account.password)
    totp_secret = decrypt_field(account.totp_secret) or ""
    result = await run_remove_family_member(profile_id, req.member_email, password=password, totp_secret=totp_secret)
    if result.success:
        save_browser_cookies(req.account_id, profile_id)
    sync_group_after_action(ACTION_FAMILY_REMOVE, req.account_id, result.success, result.message, {"member_email": req.member_email})
    return result.to_dict()


@router.post("/family/leave")
async def leave_family_group(req: AccountActionRequest, db: Session = Depends(get_db)):
    """退出/删除家庭组 (管理员删除需要密码 + 2FA 重验证)"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    profile_id = _get_profile_id(req.account_id, db)
    password = decrypt_field(account.password)
    totp_secret = decrypt_field(account.totp_secret) or ""
    result = await run_leave_family_group(profile_id, password=password, totp_secret=totp_secret)
    if result.success:
        save_browser_cookies(req.account_id, profile_id)
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
    password = decrypt_field(account.password)
    totp_secret = decrypt_field(account.totp_secret) or ""
    recovery_email = decrypt_field(account.recovery_email) or ""

    loop = asyncio.get_running_loop()
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
        save_subscription_status(req.account_id, result.subscription_status, result.subscription_expiry)

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
