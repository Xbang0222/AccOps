"""自动化操作路由 - Google 登录 / 家庭组管理 (REST + WebSocket)"""
import asyncio
import json
import logging
import queue
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from deps import verify_token, state
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
    run_oauth,
    run_phone_verify,
    CancellationToken,
    CancelledError,
)
from services.group_sync import sync_group_after_action, sync_group_from_discover

from core.constants import (
    ACTION_LOGIN,
    ACTION_FAMILY_CREATE,
    ACTION_FAMILY_INVITE,
    ACTION_FAMILY_ACCEPT,
    ACTION_FAMILY_REMOVE,
    ACTION_FAMILY_LEAVE,
    ACTION_FAMILY_DISCOVER,
    ACTION_FAMILY_BATCH_INVITE,
    ACTION_FAMILY_BATCH_REMOVE,
    ACTION_FAMILY_REPLACE,
    ACTION_FAMILY_ROTATE,
    ACTION_POOL_BATCH_LOGIN,
    ACTION_POOL_REPLACE_ALL,
    ACTION_OAUTH,
    ACTION_PHONE_VERIFY,
    PHASE_REMOVE_OLD,
    PHASE_INVITE_NEW,
    PHASE_AUTO_ACCEPT,
    PHASE_AUTO_LOGIN,
    PHASE_ACCEPT_INVITE,
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
        raise HTTPException(status_code=400, detail="该账号没有浏览器配置, 请先启动浏览器")

    if not browser_manager.is_running(profile.id):
        raise HTTPException(status_code=400, detail="浏览器未启动, 请先启动浏览器")

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


def _create_step_handler(msg_queue: queue.Queue, step_offset: int = 0):
    """创建带步骤偏移的步骤回调。"""
    def on_step(step_data: dict):
        if step_offset and step_data.get("step"):
            step_data = {**step_data, "step": step_data["step"] + step_offset}
        msg_queue.put(step_data)

    return on_step


async def _flush_step_messages(ws: WebSocket, msg_queue: queue.Queue):
    """将队列中的步骤消息转发给前端。"""
    while not msg_queue.empty():
        message = msg_queue.get_nowait()
        if message.get("type") != "result":
            await ws.send_json(message)


async def _poll_cancel_command(ws: WebSocket, cancel_token: CancellationToken) -> bool:
    """轮询前端取消命令；返回 False 表示连接已断开。"""
    try:
        raw_cancel = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
        incoming = json.loads(raw_cancel)
        if incoming.get("action") == "cancel":
            cancel_token.cancel()
            await ws.send_json({"type": "step", "name": "取消操作", "status": "info", "message": "正在取消..."})
        return True
    except asyncio.TimeoutError:
        return True
    except json.JSONDecodeError:
        return True
    except WebSocketDisconnect:
        cancel_token.cancel()
        return False


async def _drain_task_queue(ws: WebSocket, msg_queue: queue.Queue, task, cancel_token: CancellationToken) -> bool:
    """在任务执行期间持续转发步骤，并监听取消信号。"""
    while not task.done():
        await _flush_step_messages(ws, msg_queue)
        if not await _poll_cancel_command(ws, cancel_token):
            return False

    await _flush_step_messages(ws, msg_queue)
    return True


def _get_task_result(task):
    """提取已完成任务的结果与错误消息。"""
    exception = task.exception()
    if exception:
        return None, str(exception)
    return task.result(), ""


async def _run_batch_operation(
    ws: WebSocket,
    msg_queue: queue.Queue,
    items: list[str],
    action_label: str,
    summary_label: str,
    task_factory,
    cancel_token: CancellationToken,
    on_success,
) -> bool:
    """执行批量自动化操作。"""
    total = len(items)
    success_count = 0
    fail_list = []

    for index, item in enumerate(items):
        on_step = _create_step_handler(msg_queue, index * 100)
        on_step({
            "type": "step",
            "name": f"--- {action_label} {item} ({index + 1}/{total}) ---",
            "status": "info",
            "message": item,
        })

        task = asyncio.ensure_future(task_factory(item, on_step))
        if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
            return False

        result, error_message = _get_task_result(task)
        if result and result.success:
            success_count += 1
            on_success(item, result)
        else:
            fail_list.append(f"{item}: {result.message if result else error_message}")

    if fail_list:
        summary = f"{summary_label}: 成功 {success_count}/{total}, 失败: {'; '.join(fail_list)}"
        await ws.send_json({"type": "result", "success": success_count > 0, "message": summary, "duration_ms": 0})
    else:
        await ws.send_json({
            "type": "result",
            "success": True,
            "message": f"{summary_label}: 全部成功 ({total})",
            "duration_ms": 0,
        })

    return True


async def _handle_family_replace(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    profile_id: int,
    account_id: int,
    password: str,
    totp_secret: str,
    old_email: str,
    new_email: str,
) -> bool:
    """执行替换成员流程。"""
    remove_step = _create_step_handler(msg_queue, 0)
    remove_step({"type": "step", "name": PHASE_REMOVE_OLD, "status": "info", "message": old_email})
    task = asyncio.ensure_future(
        run_remove_family_member(profile_id, old_email, password, totp_secret, on_step=remove_step, cancel_token=cancel_token)
    )
    if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
        return False

    remove_result, remove_error = _get_task_result(task)
    if not remove_result or not remove_result.success:
        error_message = f"移除旧成员失败: {remove_result.message if remove_result else remove_error}"
        await ws.send_json({"type": "result", "success": False, "message": error_message, "duration_ms": 0})
        sync_group_after_action(ACTION_FAMILY_REMOVE, account_id, False, error_message, {"member_email": old_email})
        return True

    sync_group_after_action(ACTION_FAMILY_REMOVE, account_id, True, remove_result.message, {"member_email": old_email})
    await ws.send_json({"type": "step", "name": "移除旧成员完成", "status": "ok", "message": f"已移除 {old_email}"})

    invite_step = _create_step_handler(msg_queue, 100)
    invite_step({"type": "step", "name": PHASE_INVITE_NEW, "status": "info", "message": new_email})
    task = asyncio.ensure_future(
        run_send_family_invite(profile_id, new_email, on_step=invite_step, cancel_token=cancel_token)
    )
    if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
        return False

    invite_result, invite_error = _get_task_result(task)
    if not invite_result or not invite_result.success:
        error_message = f"已移除旧成员, 但邀请新成员失败: {invite_result.message if invite_result else invite_error}"
        await ws.send_json({"type": "result", "success": False, "message": error_message, "duration_ms": 0})
        return True

    await ws.send_json({"type": "step", "name": "邀请新成员完成", "status": "ok", "message": f"已邀请 {new_email}"})

    with get_db_session() as db:
        new_account = db.query(Account).filter(Account.email == new_email).first()
        new_profile = None
        if new_account:
            new_profile = db.query(BrowserProfile).filter(BrowserProfile.account_id == new_account.id).first()
        new_password = _decrypt(new_account.password) if new_account else ""
        new_totp = _decrypt(new_account.totp_secret) if new_account else ""
        new_email_db = new_account.email if new_account else ""

    if not new_account or not new_password:
        await ws.send_json({
            "type": "step",
            "name": "自动接受邀请",
            "status": "skip",
            "message": f"{new_email} 不在系统中或信息不完整, 仅完成邀请",
        })
        await ws.send_json({
            "type": "result",
            "success": True,
            "message": f"替换完成: 已移除 {old_email}, 已邀请 {new_email} (需手动接受)",
            "duration_ms": 0,
        })
        return True

    auto_accept_step = _create_step_handler(msg_queue, 200)
    auto_accept_step({
        "type": "step",
        "name": PHASE_AUTO_ACCEPT,
        "status": "info",
        "message": f"{new_email} 在系统中, 将自动接受",
    })
    await _flush_step_messages(ws, msg_queue)

    need_auto_login = False
    if not new_profile or not browser_manager.is_running(new_profile.id):
        auto_accept_step({"type": "step", "name": "启动新成员浏览器", "status": "running", "message": new_email})
        await _flush_step_messages(ws, msg_queue)

        if not new_profile:
            await ws.send_json({
                "type": "step",
                "name": "自动接受邀请",
                "status": "skip",
                "message": f"{new_email} 没有浏览器配置, 仅完成邀请",
            })
            await ws.send_json({
                "type": "result",
                "success": True,
                "message": f"替换完成: 已移除 {old_email}, 已邀请 {new_email} (需手动接受)",
                "duration_ms": 0,
            })
            return True

        try:
            with get_db_session() as db:
                from sqlalchemy.orm import joinedload

                fresh_profile = (
                    db.query(BrowserProfile)
                    .options(joinedload(BrowserProfile.account))
                    .filter(BrowserProfile.id == new_profile.id)
                    .first()
                )
                _ = fresh_profile.account

            await browser_manager.launch(fresh_profile)
            auto_accept_step({"type": "step", "name": "启动新成员浏览器", "status": "ok", "message": "浏览器已启动"})
            await _flush_step_messages(ws, msg_queue)
            need_auto_login = True
        except Exception as exc:
            auto_accept_step({"type": "step", "name": "启动新成员浏览器", "status": "fail", "message": str(exc)})
            await _flush_step_messages(ws, msg_queue)
            await ws.send_json({
                "type": "result",
                "success": True,
                "message": f"替换部分完成: 已移除 {old_email}, 已邀请 {new_email}, 但启动新成员浏览器失败",
                "duration_ms": 0,
            })
            return True

    if need_auto_login:
        login_step = _create_step_handler(msg_queue, 300)
        login_step({"type": "step", "name": PHASE_AUTO_LOGIN, "status": "info", "message": new_email})

        from services.verification import extract_verification_link

        verification_url = extract_verification_link(new_account.notes or "") or ""
        recovery_email = _decrypt(new_account.recovery_email) or ""
        task = asyncio.ensure_future(
            run_auto_login(
                new_profile.id,
                new_email_db,
                new_password,
                new_totp,
                recovery_email,
                verification_url,
                on_step=login_step,
                cancel_token=cancel_token,
            )
        )
        if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
            return False

        login_result, login_error = _get_task_result(task)
        if not login_result or not login_result.success:
            error_message = f"新成员登录失败: {login_result.message if login_result else login_error}"
            await ws.send_json({
                "type": "result",
                "success": True,
                "message": f"替换部分完成: 已移除 {old_email}, 已邀请 {new_email}, 但新成员登录失败",
                "duration_ms": 0,
            })
            return True

    accept_step = _create_step_handler(msg_queue, 400)
    accept_step({"type": "step", "name": PHASE_ACCEPT_INVITE, "status": "info", "message": new_email})
    task = asyncio.ensure_future(
        run_accept_family_invite(new_profile.id, on_step=accept_step, cancel_token=cancel_token)
    )
    if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
        return False

    accept_result, accept_error = _get_task_result(task)
    if accept_result and accept_result.success:
        sync_group_after_action(ACTION_FAMILY_ACCEPT, new_account.id, True, accept_result.message, {"manager_account_id": account_id})
        await ws.send_json({
            "type": "result",
            "success": True,
            "message": f"替换成功: 已移除 {old_email}, 已邀请并接受 {new_email}",
            "duration_ms": 0,
        })
    else:
        await ws.send_json({
            "type": "result",
            "success": True,
            "message": f"替换部分完成: 已移除 {old_email}, 已邀请 {new_email}, 但接受邀请失败: {accept_result.message if accept_result else accept_error}",
            "duration_ms": 0,
        })

    if need_auto_login:
        try:
            await browser_manager.stop(new_profile.id)
            auto_accept_step({"type": "step", "name": "关闭新成员浏览器", "status": "ok", "message": "已关闭"})
            await _flush_step_messages(ws, msg_queue)
        except Exception:
            pass

    return True


async def _handle_family_rotate(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    profile_id: int,
    account_id: int,
    password: str,
    totp_secret: str,
    remove_emails: list[str],
    new_count: int,
) -> bool:
    """执行批量轮换：移除旧子号 → 选取新子号 → 邀请 → 自动接受。"""
    from services.family_api import FamilyAPI
    from services.account import AccountService

    remove_success = 0

    # ── 阶段1: 批量移除旧子号 ──
    if remove_emails:
        await ws.send_json({"type": "step", "name": "--- 阶段1: 移除旧子号 ---", "status": "info", "message": f"共 {len(remove_emails)} 个"})
        remove_success = 0
        remove_fail = []

        # 先获取一次 rapt token (跨操作共享, 只需验证一次)
        await ws.send_json({"type": "step", "name": "密码重验证", "status": "running", "message": "获取 rapt token..."})

        rapt = None
        main_cookies = None
        email_to_uid: dict[str, str] = {}
        try:
            page = browser_manager.get_page(profile_id)
            if page:
                # 先用 cookies 查成员列表, 获取真实 user_id
                main_cookies = browser_manager.get_cookies(profile_id)
                if main_cookies:
                    with FamilyAPI(main_cookies) as api:
                        members_info = api.query_members()
                        for m in members_info.get("members", []):
                            m_email = m.get("email", "").lower()
                            if m_email:
                                email_to_uid[m_email] = m.get("user_id", "")

                # 用第一个真实 user_id 触发密码重验证
                first_uid = next((email_to_uid.get(e.lower(), "") for e in remove_emails if email_to_uid.get(e.lower())), "")
                rapt_path = f"/family/remove/g/{first_uid}" if first_uid else "/family/delete"

                from services.browser import get_rapt_sync
                rapt = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: get_rapt_sync(page, rapt_path, password, totp_secret),
                )
                # 重验证后 cookies 可能已更新
                main_cookies = browser_manager.get_cookies(profile_id)
        except Exception as exc:
            logger.warning(f"rapt 获取异常: {exc}")

        if not rapt:
            # rapt 失败, fallback 到逐个移除 (可能是 pending 成员不需要 rapt)
            await ws.send_json({"type": "step", "name": "密码重验证", "status": "fail", "message": "rapt 获取失败, 尝试逐个移除"})
            for i, email in enumerate(remove_emails):
                if cancel_token.is_cancelled:
                    break
                step = _create_step_handler(msg_queue, i * 50)
                step({"type": "step", "name": f"移除 {email}", "status": "running", "message": f"({i+1}/{len(remove_emails)})"})

                task = asyncio.ensure_future(
                    run_remove_family_member(profile_id, email, password, totp_secret, on_step=step, cancel_token=cancel_token)
                )
                if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
                    return False

                result, error = _get_task_result(task)
                if result and result.success:
                    remove_success += 1
                    sync_group_after_action(ACTION_FAMILY_REMOVE, account_id, True, result.message, {"member_email": email})
                else:
                    remove_fail.append(email)
        else:
            # rapt 成功, 用纯 RPC 批量移除
            await ws.send_json({"type": "step", "name": "密码重验证", "status": "ok", "message": "rapt 获取成功"})

            # 复用之前查到的 email_to_uid (已在 rapt 获取阶段查过)
            try:
                with FamilyAPI(main_cookies) as api:
                    for i, email in enumerate(remove_emails):
                        if cancel_token.is_cancelled:
                            break
                        await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "running", "message": f"({i+1}/{len(remove_emails)})"})

                        uid = email_to_uid.get(email.lower(), "")
                        if not uid:
                            remove_fail.append(f"{email}: 未找到成员")
                            await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "fail", "message": "未找到成员"})
                            continue

                        try:
                            ok = api.remove_member(uid, rapt)
                            if ok:
                                remove_success += 1
                                sync_group_after_action(ACTION_FAMILY_REMOVE, account_id, True, f"已移除: {email}", {"member_email": email})
                                await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "ok", "message": "已移除"})
                            else:
                                remove_fail.append(email)
                                await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "fail", "message": "RPC 调用失败"})
                        except Exception as exc:
                            remove_fail.append(f"{email}: {exc}")
                            await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "fail", "message": str(exc)[:80]})
            except Exception as exc:
                await ws.send_json({"type": "step", "name": "批量移除", "status": "fail", "message": f"异常: {str(exc)[:80]}"})

        await ws.send_json({"type": "step", "name": "阶段1完成", "status": "ok", "message": f"移除 {remove_success}/{len(remove_emails)}"})

    # ── 阶段2: 从号池选取新子号 ──
    await ws.send_json({"type": "step", "name": "--- 阶段2: 选取新子号 ---", "status": "info", "message": f"需要 {new_count} 个"})

    # 获取主号所属的 group_id 作为号池
    pool_gid = None
    with get_db_session() as db:
        main_account = db.query(Account).filter(Account.id == account_id).first()
        if main_account and main_account.family_group_id:
            pool_gid = main_account.family_group_id

    with get_db_session() as db:
        svc = AccountService(db)
        # 优先从号池选，号池没有再从全局选
        available = svc.get_available(limit=new_count, pool_group_id=pool_gid) if pool_gid else []
        if len(available) < new_count:
            # 号池不够，补充全局可用号
            remaining = new_count - len(available)
            existing_ids = {a["id"] for a in available}
            global_available = svc.get_available(limit=remaining)
            for a in global_available:
                if a["id"] not in existing_ids:
                    available.append(a)
                    if len(available) >= new_count:
                        break

    if not available:
        await ws.send_json({"type": "result", "success": False, "message": "没有可用的子号", "duration_ms": 0})
        return True

    selected_emails = [a["email"] for a in available]
    actual_count = len(selected_emails)
    if actual_count < new_count:
        await ws.send_json({"type": "step", "name": "可用数量不足", "status": "info", "message": f"需要 {new_count}, 可用 {actual_count}"})

    await ws.send_json({"type": "step", "name": "阶段2完成", "status": "ok", "message": f"已选取 {actual_count} 个子号"})

    # ── 阶段3: 用主号 cookies 批量发送邀请 ──
    await ws.send_json({"type": "step", "name": "--- 阶段3: 批量邀请 ---", "status": "info", "message": f"共 {actual_count} 个"})

    invite_success = []
    invite_fail = []

    for i, email in enumerate(selected_emails):
        if cancel_token.is_cancelled:
            break
        step = _create_step_handler(msg_queue, 1000 + i * 50)
        step({"type": "step", "name": f"邀请 {email}", "status": "running", "message": f"({i+1}/{actual_count})"})

        task = asyncio.ensure_future(
            run_send_family_invite(profile_id, email, on_step=step, cancel_token=cancel_token)
        )
        if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
            return False

        result, error = _get_task_result(task)
        if result and result.success:
            invite_success.append(email)
            sync_group_after_action(ACTION_FAMILY_INVITE, account_id, True, result.message, {"invite_email": email})
        else:
            invite_fail.append(f"{email}: {result.message if result else error}")

    await ws.send_json({"type": "step", "name": "阶段3完成", "status": "ok", "message": f"邀请成功 {len(invite_success)}/{actual_count}"})

    if not invite_success:
        await ws.send_json({"type": "result", "success": False, "message": f"邀请全部失败: {'; '.join(invite_fail)}", "duration_ms": 0})
        return True

    # ── 阶段3.5: 批量登录子号 (确保 cookies 有效) ──
    await ws.send_json({"type": "step", "name": "--- 阶段3.5: 登录子号 ---", "status": "info", "message": f"为 {len(invite_success)} 个子号刷新 cookies"})

    login_success = 0
    login_fail = []
    for i, email in enumerate(invite_success):
        if cancel_token.is_cancelled:
            break

        # 检查现有 cookies 是否有效
        with get_db_session() as db:
            sub = db.query(Account).filter(Account.email.ilike(email)).first()
            if not sub:
                login_fail.append(f"{email}: 账号不存在")
                continue
            sub_id = sub.id
            sub_password = _decrypt(sub.password)
            sub_totp = _decrypt(sub.totp_secret) or ""
            sub_recovery = _decrypt(sub.recovery_email) or ""
            cookies_json = sub.cookies_json or ""

        # 尝试用现有 cookies 验证
        if cookies_json:
            try:
                import json as json_mod
                test_cookies = json_mod.loads(cookies_json)
                with FamilyAPI(test_cookies) as api:
                    pass  # __init__ 里 refresh_tokens 成功 = cookies 有效
                login_success += 1
                await ws.send_json({"type": "step", "name": f"验证 {email}", "status": "ok", "message": "cookies 有效"})
                continue
            except Exception:
                pass  # cookies 无效, 需要重新登录

        # cookies 无效, 启动浏览器登录
        await ws.send_json({"type": "step", "name": f"登录 {email}", "status": "running", "message": f"({i+1}/{len(invite_success)})"})

        sub_profile_id = None
        with get_db_session() as db:
            bp = db.query(BrowserProfile).filter(BrowserProfile.account_id == sub_id).first()
            if bp:
                sub_profile_id = bp.id

        if not sub_profile_id:
            try:
                with get_db_session() as db:
                    bp = BrowserProfile(name=email, account_id=sub_id)
                    db.add(bp)
                    db.commit()
                    db.refresh(bp)
                    sub_profile_id = bp.id
            except Exception as exc:
                login_fail.append(f"{email}: 创建配置失败 {exc}")
                continue

        # 启动浏览器
        try:
            if not browser_manager.is_running(sub_profile_id):
                with get_db_session() as db:
                    from sqlalchemy.orm import joinedload
                    fresh_bp = (
                        db.query(BrowserProfile)
                        .options(joinedload(BrowserProfile.account))
                        .filter(BrowserProfile.id == sub_profile_id)
                        .first()
                    )
                    _ = fresh_bp.account
                    await browser_manager.launch(fresh_bp)
        except Exception as exc:
            login_fail.append(f"{email}: 启动浏览器失败 {exc}")
            continue

        # 登录
        try:
            from services.verification import extract_verification_link
            with get_db_session() as db:
                sub_acct = db.query(Account).filter(Account.id == sub_id).first()
                sub_notes = sub_acct.notes if sub_acct else ""
            verification_url = extract_verification_link(sub_notes) or ""

            result = await run_auto_login(
                sub_profile_id, email, sub_password, sub_totp,
                sub_recovery, verification_url,
                on_step=_create_step_handler(msg_queue, 2000 + i * 100),
                cancel_token=cancel_token,
            )
            # 转发步骤消息
            await _flush_step_messages(ws, msg_queue)

            if result and result.success:
                login_success += 1
                _save_cookies(sub_id, sub_profile_id)
                await ws.send_json({"type": "step", "name": f"登录 {email}", "status": "ok", "message": "已保存 cookies"})
            else:
                login_fail.append(f"{email}: {result.message if result else '登录失败'}")
                await ws.send_json({"type": "step", "name": f"登录 {email}", "status": "fail", "message": result.message if result else "登录失败"})
        except Exception as exc:
            login_fail.append(f"{email}: {exc}")
        finally:
            try:
                await browser_manager.stop(sub_profile_id)
            except Exception:
                pass

    await ws.send_json({"type": "step", "name": "阶段3.5完成", "status": "ok", "message": f"登录成功 {login_success}/{len(invite_success)}"})

    # ── 阶段4: 用子号 cookies 自动接受邀请 ──
    await ws.send_json({"type": "step", "name": "--- 阶段4: 自动接受邀请 ---", "status": "info", "message": f"共 {len(invite_success)} 个"})

    accept_success = 0
    accept_fail = []

    for i, email in enumerate(invite_success):
        if cancel_token.is_cancelled:
            break

        await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "running", "message": f"({i+1}/{len(invite_success)})"})

        # 从数据库获取子号 cookies
        cookies_json = ""
        sub_account_id = None
        with get_db_session() as db:
            sub = db.query(Account).filter(Account.email.ilike(email)).first()
            if sub:
                cookies_json = sub.cookies_json or ""
                sub_account_id = sub.id

        if not cookies_json:
            accept_fail.append(f"{email}: 无 cookies (需先登录)")
            await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "fail", "message": "无 cookies"})
            continue

        # 用 cookies 调用 RPC 接受邀请
        try:
            import json as json_mod
            cookies = json_mod.loads(cookies_json)
            with FamilyAPI(cookies) as api:
                result = api.accept_invite()
            if result.get("success"):
                accept_success += 1
                await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "ok", "message": "已加入"})
                if sub_account_id:
                    sync_group_after_action(ACTION_FAMILY_ACCEPT, sub_account_id, True, "已接受邀请", {"manager_account_id": account_id})
            else:
                error_msg = result.get("error", "接受失败")
                accept_fail.append(f"{email}: {error_msg}")
                await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "fail", "message": error_msg})
        except Exception as exc:
            accept_fail.append(f"{email}: {exc}")
            await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "fail", "message": str(exc)[:100]})

    # ── 阶段5: 同步验证（用主号 cookies discover 确认实际成员） ──
    await ws.send_json({"type": "step", "name": "--- 阶段5: 同步验证 ---", "status": "info", "message": "用主号确认实际成员状态"})

    verified_count = 0
    try:
        main_cookies_json = ""
        with get_db_session() as db:
            main = db.query(Account).filter(Account.id == account_id).first()
            if main:
                main_cookies_json = main.cookies_json or ""

        if main_cookies_json:
            import json as json_mod
            main_cookies = json_mod.loads(main_cookies_json)
            with FamilyAPI(main_cookies) as api:
                members_result = api.query_members()

            if members_result.get("success"):
                actual_emails = {
                    m.get("email", "").lower()
                    for m in members_result.get("members", [])
                    if m.get("email")
                }

                # 对比邀请列表和实际成员
                for email in invite_success:
                    if email.lower() in actual_emails:
                        if email not in [e.split(":")[0] for e in accept_fail if ":" in e] or True:
                            verified_count += 1
                        # 确保同步分组关系
                        with get_db_session() as db:
                            sub = db.query(Account).filter(Account.email.ilike(email)).first()
                            if sub:
                                sync_group_after_action(ACTION_FAMILY_ACCEPT, sub.id, True, "已验证加入", {"manager_account_id": account_id})

                await ws.send_json({"type": "step", "name": "同步验证", "status": "ok", "message": f"实际加入 {verified_count}/{len(invite_success)}"})

                # 用验证结果覆盖 accept 的不可靠结果
                accept_success = verified_count
                accept_fail = [f"{e}" for e in invite_success if e.lower() not in actual_emails]
            else:
                await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": "查询成员失败，以接受结果为准"})
        else:
            await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": "主号无 cookies，以接受结果为准"})
    except Exception as exc:
        await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": f"验证异常: {str(exc)[:80]}"})

    # ── 最终报告 ──
    parts = []
    if remove_emails:
        parts.append(f"移除 {remove_success}/{len(remove_emails)}")
    parts.append(f"邀请 {len(invite_success)}/{actual_count}")
    parts.append(f"接受 {accept_success}/{len(invite_success)}")
    summary = f"轮换完成: {', '.join(parts)}"
    if accept_fail:
        summary += f" | 失败: {'; '.join(accept_fail)}"

    await ws.send_json({"type": "result", "success": accept_success > 0 or verified_count > 0, "message": summary, "duration_ms": 0})
    return True


async def _handle_pool_replace_all(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    profile_id: int,
    account_id: int,
    password: str,
    totp_secret: str,
) -> bool:
    """一键换号：自动查出所有子号 → 全部移除 → 从号池选同等数量新号 → 邀请 → 接受。"""

    # 如果浏览器未运行, 自动启动
    auto_launched_browser = False
    if not profile_id or not browser_manager.is_running(profile_id):
        await ws.send_json({"type": "step", "name": "启动浏览器", "status": "running", "message": "自动启动主号浏览器..."})
        try:
            with get_db_session() as db:
                from sqlalchemy.orm import joinedload
                bp = (
                    db.query(BrowserProfile)
                    .options(joinedload(BrowserProfile.account))
                    .filter(BrowserProfile.account_id == account_id)
                    .first()
                )
                if not bp:
                    # 自动创建浏览器配置
                    acct = db.query(Account).filter(Account.id == account_id).first()
                    bp = BrowserProfile(name=acct.email if acct else str(account_id), account_id=account_id)
                    db.add(bp)
                    db.commit()
                    db.refresh(bp)
                    bp = (
                        db.query(BrowserProfile)
                        .options(joinedload(BrowserProfile.account))
                        .filter(BrowserProfile.id == bp.id)
                        .first()
                    )
                profile_id = bp.id
                _ = bp.account
                await browser_manager.launch(bp)
                auto_launched_browser = True
            await ws.send_json({"type": "step", "name": "启动浏览器", "status": "ok", "message": "浏览器已启动"})
        except Exception as exc:
            await ws.send_json({"type": "result", "success": False, "message": f"启动浏览器失败: {exc}", "duration_ms": 0})
            return True

    # 查出当前家庭组所有子号
    with get_db_session() as db:
        main_account = db.query(Account).filter(Account.id == account_id).first()
        if not main_account or not main_account.family_group_id:
            await ws.send_json({"type": "result", "success": False, "message": "该账号没有关联的家庭组", "duration_ms": 0})
            return True

        group_id = main_account.family_group_id
        main_email = main_account.email.lower()

        # 查同组所有子号（排除主号自己）
        sub_accounts = (
            db.query(Account)
            .filter(Account.family_group_id == group_id, Account.id != account_id)
            .all()
        )
        remove_emails = [a.email for a in sub_accounts]

    if not remove_emails:
        await ws.send_json({"type": "result", "success": False, "message": "当前家庭组没有子号可替换", "duration_ms": 0})
        return True

    new_count = len(remove_emails)
    await ws.send_json({
        "type": "step", "name": "一键换号",
        "status": "info",
        "message": f"将移除 {new_count} 个子号并替换: {', '.join(remove_emails)}",
    })

    # 复用已有的轮换逻辑
    return await _handle_family_rotate(
        ws=ws,
        msg_queue=msg_queue,
        cancel_token=cancel_token,
        profile_id=profile_id,
        account_id=account_id,
        password=password,
        totp_secret=totp_secret,
        remove_emails=remove_emails,
        new_count=new_count,
    )


async def _handle_pool_batch_login(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    group_id: int,
) -> bool:
    """批量登录号池中没有 cookies 的账号：启动浏览器 → 登录 → 保存 cookies → 关闭浏览器。"""
    # 查找号池中没有 cookies 的账号
    accounts_to_login = []
    with get_db_session() as db:
        rows = (
            db.query(Account)
            .filter(
                Account.pool_group_id == group_id,
                Account.family_group_id.is_(None),
                (Account.cookies_json.is_(None)) | (Account.cookies_json == ""),
            )
            .order_by(Account.email)
            .all()
        )
        for row in rows:
            accounts_to_login.append({
                "id": row.id,
                "email": row.email,
                "password": _decrypt(row.password),
                "totp_secret": _decrypt(row.totp_secret),
                "recovery_email": _decrypt(row.recovery_email),
                "notes": row.notes or "",
            })

    if not accounts_to_login:
        await ws.send_json({"type": "result", "success": True, "message": "号池中所有账号都已有 cookies，无需登录", "duration_ms": 0})
        return True

    total = len(accounts_to_login)
    await ws.send_json({"type": "step", "name": "批量登录", "status": "info", "message": f"共 {total} 个账号需要并发登录"})

    success_count = 0
    fail_list: list[str] = []

    # --- 单个账号的完整登录流程 (启动浏览器 → 登录 → 保存 cookies → 关闭) ---
    async def _login_one(i: int, acct: dict) -> bool:
        """返回 True 表示成功"""
        email = acct["email"]
        step = _create_step_handler(msg_queue, i * 100)
        step({"type": "step", "name": f"登录 {email}", "status": "running", "message": f"({i+1}/{total})"})

        if cancel_token.is_cancelled:
            return False

        # 获取或创建浏览器配置
        profile_id = None
        with get_db_session() as db:
            profile = db.query(BrowserProfile).filter(BrowserProfile.account_id == acct["id"]).first()
            if profile:
                profile_id = profile.id

        if not profile_id:
            try:
                with get_db_session() as db:
                    bp = BrowserProfile(name=email, account_id=acct["id"])
                    db.add(bp)
                    db.commit()
                    db.refresh(bp)
                    profile_id = bp.id
            except Exception as exc:
                fail_list.append(f"{email}: 创建浏览器配置失败 {exc}")
                return False

        # 启动浏览器
        try:
            if not browser_manager.is_running(profile_id):
                with get_db_session() as db:
                    from sqlalchemy.orm import joinedload
                    fresh_profile = (
                        db.query(BrowserProfile)
                        .options(joinedload(BrowserProfile.account))
                        .filter(BrowserProfile.id == profile_id)
                        .first()
                    )
                    _ = fresh_profile.account
                    await browser_manager.launch(fresh_profile)
        except Exception as exc:
            fail_list.append(f"{email}: 启动浏览器失败 {exc}")
            return False

        # 登录
        try:
            from services.verification import extract_verification_link
            verification_url = extract_verification_link(acct["notes"]) or ""

            result = await run_auto_login(
                profile_id, email, acct["password"], acct["totp_secret"],
                acct["recovery_email"], verification_url,
                on_step=step, cancel_token=cancel_token,
            )
            if result and result.success:
                _save_cookies(acct["id"], profile_id)
                step({"type": "step", "name": f"登录 {email}", "status": "ok", "message": "已保存 cookies"})
                return True
            else:
                fail_list.append(f"{email}: {result.message if result else '未知错误'}")
                return False
        except Exception as exc:
            fail_list.append(f"{email}: {exc}")
            return False
        finally:
            # 关闭浏览器
            try:
                await browser_manager.stop(profile_id)
            except Exception:
                pass

    # --- 并发启动所有登录任务 (限制最多 3 个浏览器同时运行) ---
    MAX_CONCURRENT_BROWSERS = 7
    sem = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)

    async def _login_with_limit(i: int, acct: dict) -> bool:
        async with sem:
            return await _login_one(i, acct)

    tasks = [
        asyncio.ensure_future(_login_with_limit(i, acct))
        for i, acct in enumerate(accounts_to_login)
    ]

    # 持续转发步骤消息直到所有任务完成
    all_done_task = asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
    while not all_done_task.done():
        await _flush_step_messages(ws, msg_queue)
        if not await _poll_cancel_command(ws, cancel_token):
            # WebSocket 断开，取消所有任务
            for t in tasks:
                t.cancel()
            return False
    await _flush_step_messages(ws, msg_queue)

    # 汇总结果
    results = all_done_task.result()
    for r in results:
        if r is True:
            success_count += 1

    summary = f"批量登录完成: 成功 {success_count}/{total}"
    if fail_list:
        summary += f" | 失败: {'; '.join(fail_list)}"
    await ws.send_json({"type": "result", "success": success_count > 0, "message": summary, "duration_ms": 0})
    return True


# ---- 自动登录 ----

@router.post("/login")
async def auto_login(req: AutoLoginRequest, db: Session = Depends(get_db)):
    """自动登录 Google 账号"""
    account = db.query(Account).get(req.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")

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
        raise HTTPException(status_code=404, detail="账号不存在")
    if not account.oauth_credential_json:
        raise HTTPException(status_code=404, detail="该账号暂无 OAuth 凭证")
    return json.loads(account.oauth_credential_json)


@router.get("/oauth/credential/{account_id}/download")
async def download_oauth_credential(account_id: int, db: Session = Depends(get_db)):
    """下载 OAuth 认证 JSON 文件"""
    account = db.query(Account).get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if not account.oauth_credential_json:
        raise HTTPException(status_code=404, detail="该账号暂无 OAuth 凭证")

    email = account.email or "unknown"
    filename = f"antigravity-{email}.json"
    content = account.oauth_credential_json
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# WebSocket 实时操作 endpoint
# ============================================================

# 单独创建不带 auth 依赖的 ws router (WebSocket 通过 query param 认证)
ws_router = APIRouter(tags=["自动化"])


@ws_router.websocket("/ws/automation")
async def automation_websocket(ws: WebSocket):
    """
    WebSocket 实时自动化操作

    客户端发送:
      {"action": "login", "account_id": 1}
      {"action": "family-create", "account_id": 1}
      {"action": "family-invite", "account_id": 1, "invite_email": "xxx@gmail.com"}
      {"action": "family-accept", "account_id": 1}
      {"action": "family-remove", "account_id": 1, "member_email": "xxx@gmail.com"}
      {"action": "family-leave", "account_id": 1}

    服务端实时推送:
      {"type": "step", "step": 1, "name": "打开登录页", "status": "running", ...}
      {"type": "step", "step": 1, "name": "打开登录页", "status": "ok", "message": "...", ...}
      {"type": "result", "success": true, "message": "登录成功", "duration_ms": 12345}
    """
    # 认证: 从 query param 获取 token
    token = ws.query_params.get("token", "")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    from deps import verify_ws_token
    if not verify_ws_token(token):
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    logger.info("WebSocket automation client connected")

    cancel_token = CancellationToken()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            action = data.get("action", "")
            account_id = data.get("account_id")

            if not account_id:
                await ws.send_json({"type": "error", "message": "缺少 account_id"})
                continue

            # 获取账号和 profile
            with get_db_session() as db:
                account = db.query(Account).filter(Account.id == account_id).first()
                if not account:
                    await ws.send_json({"type": "error", "message": "账号不存在"})
                    continue

                # 查找该账号的浏览器配置, 优先找正在运行的
                profiles = (
                    db.query(BrowserProfile)
                    .filter(BrowserProfile.account_id == account_id)
                    .all()
                )
                profile = None
                for p in profiles:
                    if browser_manager.is_running(p.id):
                        profile = p
                        break
                if not profile and profiles:
                    # 没有运行中的, 取最新创建的
                    profile = profiles[-1]
                # family-discover / pool-replace-all / pool-batch-login 不强制要求浏览器运行
                # login 也豁免 (启动浏览器后自动登录, 避免竞态)
                if action in (ACTION_FAMILY_DISCOVER, ACTION_POOL_REPLACE_ALL, ACTION_POOL_BATCH_LOGIN, "login"):
                    profile_id = profile.id if profile else None
                elif not profile or not browser_manager.is_running(profile.id):
                    await ws.send_json({"type": "error", "message": f"浏览器未启动 (action={action})"})
                    continue
                else:
                    profile_id = profile.id
                email = account.email
                password = _decrypt(account.password)
                totp_secret = _decrypt(account.totp_secret) or ""
                recovery_email = _decrypt(account.recovery_email) or ""
                # 从 notes 中提取验证链接
                from services.verification import extract_verification_link
                verification_url = extract_verification_link(account.notes or "") or ""

            # 用 queue 实现线程安全的步骤推送
            msg_queue: queue.Queue = queue.Queue()
            cancel_token = CancellationToken()
            on_step = _create_step_handler(msg_queue)

            # 启动自动化任务
            task = None
            if action == ACTION_LOGIN:
                task = asyncio.ensure_future(
                    run_auto_login(profile_id, email, password, totp_secret, recovery_email, verification_url, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_CREATE:
                task = asyncio.ensure_future(
                    run_create_family_group(profile_id, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_INVITE:
                invite_email = data.get("invite_email", "")
                if not invite_email:
                    await ws.send_json({"type": "error", "message": "缺少 invite_email"})
                    continue
                task = asyncio.ensure_future(
                    run_send_family_invite(profile_id, invite_email, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_BATCH_INVITE:
                invite_emails_raw = data.get("invite_emails", "")
                invite_emails = [e.strip() for e in invite_emails_raw.split(",") if e.strip()]
                if not invite_emails:
                    await ws.send_json({"type": "error", "message": "缺少邀请邮箱"})
                    continue
                if not await _run_batch_operation(
                    ws=ws,
                    msg_queue=msg_queue,
                    items=invite_emails,
                    action_label="邀请",
                    summary_label="批量邀请完成",
                    task_factory=lambda invite_email, step_handler: run_send_family_invite(
                        profile_id,
                        invite_email,
                        on_step=step_handler,
                        cancel_token=cancel_token,
                    ),
                    cancel_token=cancel_token,
                    on_success=lambda invite_email, result: sync_group_after_action(
                        ACTION_FAMILY_INVITE,
                        account_id,
                        True,
                        result.message,
                        {"invite_email": invite_email},
                    ),
                ):
                    return
                continue
            elif action == ACTION_FAMILY_ACCEPT:
                task = asyncio.ensure_future(
                    run_accept_family_invite(profile_id, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_REMOVE:
                member_email = data.get("member_email", "")
                if not member_email:
                    await ws.send_json({"type": "error", "message": "缺少 member_email"})
                    continue
                task = asyncio.ensure_future(
                    run_remove_family_member(profile_id, member_email, password, totp_secret, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_BATCH_REMOVE:
                member_emails_raw = data.get("member_emails", "")
                member_emails = [e.strip() for e in member_emails_raw.split(",") if e.strip()]
                if not member_emails:
                    await ws.send_json({"type": "error", "message": "缺少成员邮箱"})
                    continue
                if not await _run_batch_operation(
                    ws=ws,
                    msg_queue=msg_queue,
                    items=member_emails,
                    action_label="移除",
                    summary_label="批量移除完成",
                    task_factory=lambda member_email, step_handler: run_remove_family_member(
                        profile_id,
                        member_email,
                        password,
                        totp_secret,
                        on_step=step_handler,
                        cancel_token=cancel_token,
                    ),
                    cancel_token=cancel_token,
                    on_success=lambda member_email, result: sync_group_after_action(
                        ACTION_FAMILY_REMOVE,
                        account_id,
                        True,
                        result.message,
                        {"member_email": member_email},
                    ),
                ):
                    return
                continue
            elif action == ACTION_FAMILY_LEAVE:
                task = asyncio.ensure_future(
                    run_leave_family_group(profile_id, password, totp_secret, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_DISCOVER:
                # 发现家庭组关系 → cookies 过期自动登录刷新
                with get_db_session() as db_d:
                    acc_d = db_d.query(Account).filter(Account.id == account_id).first()
                    saved_cookies = acc_d.cookies_json if acc_d else ""

                loop = asyncio.get_event_loop()
                dr = await loop.run_in_executor(
                    None,
                    discover_family_by_cookies,
                    account_id,
                    saved_cookies or "",
                    profile_id,
                    email,
                    password,
                    totp_secret,
                    recovery_email,
                )

                if dr and dr.success:
                    sync_group_from_discover(account_id, dr)
                    _save_subscription_status(account_id, dr.subscription_status, dr.subscription_expiry)
                await ws.send_json({
                    "type": "result",
                    "success": dr.success if dr else False,
                    "message": dr.message if dr else "未知错误",
                    "duration_ms": 0,
                })
                continue
            elif action == ACTION_OAUTH:
                task = asyncio.ensure_future(
                    run_oauth(profile_id, on_step=on_step, password=password, totp_secret=totp_secret, cancel_token=cancel_token)
                )
            elif action == ACTION_PHONE_VERIFY:
                validation_url = data.get("validation_url", "")
                if not validation_url:
                    await ws.send_json({"type": "error", "message": "缺少 validation_url"})
                    continue
                task = asyncio.ensure_future(
                    run_phone_verify(profile_id, validation_url, on_step=on_step, cancel_token=cancel_token)
                )
            elif action == ACTION_FAMILY_REPLACE:
                old_email = data.get("old_email", "")
                new_email = data.get("new_email", "")
                if not old_email or not new_email:
                    await ws.send_json({"type": "error", "message": "缺少 old_email 或 new_email"})
                    continue
                if not await _handle_family_replace(
                    ws=ws,
                    msg_queue=msg_queue,
                    cancel_token=cancel_token,
                    profile_id=profile_id,
                    account_id=account_id,
                    password=password,
                    totp_secret=totp_secret,
                    old_email=old_email,
                    new_email=new_email,
                ):
                    return
                continue
            elif action == ACTION_FAMILY_ROTATE:
                rotate_remove = [e.strip() for e in data.get("remove_emails", "").split(",") if e.strip()]
                rotate_count = int(data.get("new_count", "0") or "0")
                if rotate_count <= 0:
                    await ws.send_json({"type": "error", "message": "新子号数量必须大于 0"})
                    continue
                if not await _handle_family_rotate(
                    ws=ws,
                    msg_queue=msg_queue,
                    cancel_token=cancel_token,
                    profile_id=profile_id,
                    account_id=account_id,
                    password=password,
                    totp_secret=totp_secret,
                    remove_emails=rotate_remove,
                    new_count=rotate_count,
                ):
                    return
                continue
            elif action == ACTION_POOL_REPLACE_ALL:
                if not await _handle_pool_replace_all(
                    ws=ws,
                    msg_queue=msg_queue,
                    cancel_token=cancel_token,
                    profile_id=profile_id,
                    account_id=account_id,
                    password=password,
                    totp_secret=totp_secret,
                ):
                    return
                continue
            elif action == ACTION_POOL_BATCH_LOGIN:
                pool_gid = None
                with get_db_session() as db:
                    main_acct = db.query(Account).filter(Account.id == account_id).first()
                    if main_acct and main_acct.family_group_id:
                        pool_gid = main_acct.family_group_id
                if not pool_gid:
                    await ws.send_json({"type": "error", "message": "该账号没有关联的分组"})
                    continue
                if not await _handle_pool_batch_login(
                    ws=ws,
                    msg_queue=msg_queue,
                    cancel_token=cancel_token,
                    group_id=pool_gid,
                ):
                    return
                continue
            else:
                await ws.send_json({"type": "error", "message": f"未知操作: {action}"})
                continue

            # 实时转发步骤消息，同时监听前端取消命令
            if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
                return

            # 检查任务异常
            result, error_message = _get_task_result(task)
            if not result:
                exc = task.exception()
                if isinstance(exc, CancelledError):
                    await ws.send_json({
                        "type": "result",
                        "success": False,
                        "message": "操作已取消",
                        "duration_ms": 0,
                    })
                else:
                    await ws.send_json({
                        "type": "result",
                        "success": False,
                        "message": f"操作异常: {error_message}",
                        "duration_ms": 0,
                    })
            else:
                # 操作完成后自动同步分组
                if result and result.success:
                    if action == ACTION_LOGIN:
                        _handle_login_success(
                            account_id,
                            profile_id,
                            email,
                            password,
                            totp_secret,
                            recovery_email,
                        )
                    else:
                        _save_cookies(account_id, profile_id)
                    # OAuth 成功后保存凭证
                    if action == ACTION_OAUTH and hasattr(result, 'extra') and result.extra and result.extra.get("credential"):
                        _save_oauth_credential(account_id, result.extra["credential"])
                if result and action in (ACTION_FAMILY_CREATE, ACTION_FAMILY_ACCEPT, ACTION_FAMILY_REMOVE, ACTION_FAMILY_LEAVE):
                    extra_data = {}
                    if action == ACTION_FAMILY_REMOVE:
                        extra_data["member_email"] = data.get("member_email", "")
                    elif action == ACTION_FAMILY_ACCEPT:
                        extra_data["manager_account_id"] = data.get("manager_account_id")
                    sync_group_after_action(
                        action=action,
                        account_id=account_id,
                        success=result.success,
                        result_msg=result.message,
                        extra=extra_data,
                    )
                await ws.send_json({
                    "type": "result",
                    "success": result.success,
                    "message": result.message,
                    "duration_ms": 0,
                })

    except WebSocketDisconnect:
        logger.info("WebSocket automation client disconnected")
        try:
            cancel_token.cancel()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.close(code=1011)
        except Exception:
            pass
