"""自动化操作 - 换号流程编排（移除旧子号 → 选取新子号 → 邀请 → 接受 → discover 同步）

100% 业务编排，不含 HTTP 路由。从 routers/automation_swap.py 搬迁。
"""
import asyncio
import json
import queue

from fastapi import WebSocket

from core.constants import (
    ACTION_FAMILY_ACCEPT,
    ACTION_FAMILY_INVITE,
    ACTION_FAMILY_REMOVE,
    PHASE_ACCEPT_INVITE,
    PHASE_DISCOVER_SYNC,
    PHASE_INVITE_NEW,
    PHASE_LOGIN_SUB,
    PHASE_REMOVE_OLD,
)
from models.database import get_db_session
from models.orm import Account, BrowserProfile
from services.automation.core.discover import discover_family_by_cookies
from services.automation.persistence import (
    decrypt_field,
    save_browser_cookies,
    save_subscription_status,
)
from services.automation.runners import (
    run_auto_login,
    run_remove_family_member,
    run_send_family_invite,
)
from services.automation.types import CancellationToken
from services.automation.ws_helpers import (
    _create_step_handler,
    _drain_task_queue,
    _flush_step_messages,
    _get_task_result,
)
from services.browser import browser_manager
from services.group_sync import sync_group_after_action, sync_group_from_discover


def _swap_ensure_browser_profile(account_id: int):
    """同步: 查找或创建浏览器配置。"""
    from sqlalchemy.orm import joinedload
    with get_db_session() as db:
        bp = (
            db.query(BrowserProfile)
            .options(joinedload(BrowserProfile.account))
            .filter(BrowserProfile.account_id == account_id)
            .first()
        )
        if not bp:
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
        _ = bp.account  # eager load
        return bp


def _swap_resolve_remove_emails(account_id: int) -> tuple[list[str], int | None]:
    """同步: 查出所有子号邮箱。返回 (emails, group_id)。"""
    with get_db_session() as db:
        main_account = db.query(Account).filter(Account.id == account_id).first()
        if not main_account or not main_account.family_group_id:
            return [], None
        group_id = main_account.family_group_id
        sub_accounts = (
            db.query(Account)
            .filter(Account.family_group_id == group_id, Account.id != account_id)
            .all()
        )
        return [a.email for a in sub_accounts], group_id


def _swap_batch_load_sub_accounts(emails: list[str]) -> dict[str, dict]:
    """同步: 批量加载子号信息，返回 {email_lower: info_dict}。"""
    result: dict[str, dict] = {}
    with get_db_session() as db:
        subs = db.query(Account).filter(Account.email.in_(emails)).all()
        sub_ids = [sub.id for sub in subs]
        profiles = db.query(BrowserProfile).filter(BrowserProfile.account_id.in_(sub_ids)).all() if sub_ids else []
        profile_by_account = {bp.account_id: bp for bp in profiles}
        for sub in subs:
            bp = profile_by_account.get(sub.id)
            result[sub.email.lower()] = {
                "id": sub.id,
                "password": decrypt_field(sub.password),
                "totp_secret": decrypt_field(sub.totp_secret) or "",
                "recovery_email": decrypt_field(sub.recovery_email) or "",
                "cookies_json": sub.cookies_json or "",
                "notes": sub.notes or "",
                "profile_id": bp.id if bp else None,
            }
    return result


def _swap_load_main_for_discover(account_id: int) -> dict:
    """同步: 加载主号信息用于 discover。"""
    with get_db_session() as db:
        main = db.query(Account).filter(Account.id == account_id).first()
        if not main:
            return {}
        return {
            "cookies_json": main.cookies_json or "",
            "email": main.email,
            "password": decrypt_field(main.password),
            "totp_secret": decrypt_field(main.totp_secret) or "",
            "recovery_email": decrypt_field(main.recovery_email) or "",
        }


def _swap_ensure_sub_profile(email: str, sub_id: int) -> int | None:
    """同步: 确保子号有浏览器配置，返回 profile_id。"""
    try:
        with get_db_session() as db:
            bp = db.query(BrowserProfile).filter(BrowserProfile.account_id == sub_id).first()
            if bp:
                return bp.id
            bp = BrowserProfile(name=email, account_id=sub_id)
            db.add(bp)
            db.commit()
            db.refresh(bp)
            return bp.id
    except Exception:
        return None


async def _swap_phase_remove(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    profile_id: int,
    account_id: int,
    password: str,
    totp_secret: str,
    remove_emails: list[str],
) -> int:
    """阶段1: 逐个移除旧子号。返回移除成功数；-1 表示用户取消。"""
    await ws.send_json({"type": "step", "name": PHASE_REMOVE_OLD, "status": "info", "message": f"共 {len(remove_emails)} 个"})
    remove_success = 0

    for i, email in enumerate(remove_emails):
        if cancel_token.is_cancelled:
            return -1
        step = _create_step_handler(msg_queue, i * 50)
        step({"type": "step", "name": f"移除 {email}", "status": "running", "message": f"({i+1}/{len(remove_emails)})"})

        task = asyncio.ensure_future(
            run_remove_family_member(profile_id, email, password, totp_secret, on_step=step, cancel_token=cancel_token)
        )
        if not await _drain_task_queue(ws, msg_queue, task, cancel_token):
            return -1

        result, error = _get_task_result(task)
        if result and result.success:
            remove_success += 1
            sync_group_after_action(ACTION_FAMILY_REMOVE, account_id, True, result.message, {"member_email": email})
            await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "ok", "message": (result.message or "已移除")[:120]})
        else:
            fail_msg = result.message if result else (str(error) if error else "移除失败")
            await ws.send_json({"type": "step", "name": f"移除 {email}", "status": "fail", "message": fail_msg[:120]})

    await ws.send_json({"type": "step", "name": "移除完成", "status": "ok", "message": f"移除 {remove_success}/{len(remove_emails)}"})
    return remove_success


async def _swap_phase_login_and_accept(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    account_id: int,
    invite_success: list[str],
    sub_map: dict[str, dict],
) -> tuple[int, list[str]]:
    """阶段3.5+4: 登录子号并自动接受邀请。返回 (accept_success, accept_fail)。"""
    from sqlalchemy import func

    from services.family_api import FamilyAPI

    # ── 登录子号 ──
    await ws.send_json({"type": "step", "name": PHASE_LOGIN_SUB, "status": "info", "message": f"为 {len(invite_success)} 个子号刷新 cookies"})

    login_success = 0
    login_fail = []
    for i, email in enumerate(invite_success):
        if cancel_token.is_cancelled:
            break

        info = sub_map.get(email.lower())
        if not info:
            login_fail.append(f"{email}: 账号不存在")
            continue

        cookies_json = info["cookies_json"]
        if cookies_json:
            try:
                test_cookies = json.loads(cookies_json)

                def _validate_cookies(_c=test_cookies):
                    with FamilyAPI(_c):
                        pass  # constructor refresh_tokens 成功 = cookies 有效

                await asyncio.get_running_loop().run_in_executor(None, _validate_cookies)
                login_success += 1
                await ws.send_json({"type": "step", "name": f"验证 {email}", "status": "ok", "message": "cookies 有效"})
                continue
            except Exception:
                pass

        await ws.send_json({"type": "step", "name": f"登录 {email}", "status": "running", "message": f"({i+1}/{len(invite_success)})"})

        sub_profile_id = info["profile_id"]
        if not sub_profile_id:
            sub_profile_id = await asyncio.get_running_loop().run_in_executor(
                None, _swap_ensure_sub_profile, email, info["id"],
            )
            if not sub_profile_id:
                login_fail.append(f"{email}: 创建配置失败")
                continue

        try:
            if not browser_manager.is_running(sub_profile_id):
                from sqlalchemy.orm import joinedload

                def _launch_sub():
                    with get_db_session() as db:
                        fresh_bp = (
                            db.query(BrowserProfile)
                            .options(joinedload(BrowserProfile.account))
                            .filter(BrowserProfile.id == sub_profile_id)
                            .first()
                        )
                        _ = fresh_bp.account
                        return fresh_bp

                fresh_bp = await asyncio.get_running_loop().run_in_executor(None, _launch_sub)
                await browser_manager.launch(fresh_bp)
        except Exception as exc:
            login_fail.append(f"{email}: 启动浏览器失败 {exc}")
            continue

        try:
            from services.verification import extract_verification_link
            verification_url = extract_verification_link(info["notes"]) or ""

            result = await run_auto_login(
                sub_profile_id, email, info["password"], info["totp_secret"],
                info["recovery_email"], verification_url,
                on_step=_create_step_handler(msg_queue, 2000 + i * 100),
                cancel_token=cancel_token,
            )
            await _flush_step_messages(ws, msg_queue)

            if result and result.success:
                login_success += 1
                save_browser_cookies(info["id"], sub_profile_id)
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

    await ws.send_json({"type": "step", "name": "登录完成", "status": "ok", "message": f"登录成功 {login_success}/{len(invite_success)}"})

    # ── 自动接受邀请 ──
    await ws.send_json({"type": "step", "name": PHASE_ACCEPT_INVITE, "status": "info", "message": f"共 {len(invite_success)} 个"})

    accept_success = 0
    accept_fail = []

    for i, email in enumerate(invite_success):
        if cancel_token.is_cancelled:
            break

        await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "running", "message": f"({i+1}/{len(invite_success)})"})

        # 重新从 DB 读取 cookies
        def _get_cookies(e=email):
            with get_db_session() as db:
                sub = db.query(Account).filter(func.lower(Account.email) == e.lower()).first()
                if sub:
                    return sub.cookies_json or "", sub.id
                return "", None

        cookies_json, sub_account_id = await asyncio.get_running_loop().run_in_executor(None, _get_cookies)

        if not cookies_json:
            accept_fail.append(f"{email}: 无 cookies (需先登录)")
            await ws.send_json({"type": "step", "name": f"接受 {email}", "status": "fail", "message": "无 cookies"})
            continue

        try:
            cookies = json.loads(cookies_json)

            def _accept(_c=cookies):
                with FamilyAPI(_c) as api:
                    return api.accept_invite()

            result = await asyncio.get_running_loop().run_in_executor(None, _accept)
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

    return accept_success, accept_fail


async def _swap_phase_discover_sync(
    ws: WebSocket,
    profile_id: int | None,
    account_id: int,
    invite_success: list[str],
) -> int:
    """阶段5: 完整 discover 同步。返回实际加入数。"""
    await ws.send_json({"type": "step", "name": PHASE_DISCOVER_SYNC, "status": "info", "message": "执行完整同步..."})

    verified_count = 0
    try:
        main_info = await asyncio.get_running_loop().run_in_executor(
            None, _swap_load_main_for_discover, account_id,
        )
        if not main_info:
            await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": "主号信息缺失"})
            return 0

        dr = await asyncio.get_running_loop().run_in_executor(
            None,
            discover_family_by_cookies,
            account_id,
            main_info["cookies_json"],
            profile_id,
            main_info["email"],
            main_info["password"],
            main_info["totp_secret"],
            main_info["recovery_email"],
        )

        if dr and dr.success:
            sync_group_from_discover(account_id, dr)
            save_subscription_status(account_id, dr.subscription_status, dr.subscription_expiry)
            actual_emails = {
                m.get("email", "").lower()
                for m in (dr.members or [])
                if m.get("email") and m.get("role") != "manager"
            }
            for email in invite_success:
                if email.lower() in actual_emails:
                    verified_count += 1
            await ws.send_json({"type": "step", "name": "同步验证", "status": "ok", "message": f"discover 同步完成, 实际加入 {verified_count}/{len(invite_success)}"})
        else:
            await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": f"discover 失败: {dr.message if dr else '未知'}, 以接受结果为准"})
    except Exception as exc:
        await ws.send_json({"type": "step", "name": "同步验证", "status": "skip", "message": f"同步异常: {str(exc)[:80]}"})

    return verified_count


async def _handle_family_swap(
    ws: WebSocket,
    msg_queue: queue.Queue,
    cancel_token: CancellationToken,
    profile_id: int | None,
    account_id: int,
    password: str,
    totp_secret: str,
    remove_emails: list[str],
    new_count: int = 0,
    specific_emails: list[str] | None = None,
) -> bool:
    """统一换号：移除旧子号 → 选取/指定新子号 → 邀请 → 自动接受 → discover 同步。"""

    if not profile_id or not browser_manager.is_running(profile_id):
        await ws.send_json({"type": "step", "name": "启动浏览器", "status": "running", "message": "自动启动主号浏览器..."})
        try:
            bp = await asyncio.get_running_loop().run_in_executor(
                None, _swap_ensure_browser_profile, account_id,
            )
            profile_id = bp.id
            await browser_manager.launch(bp)
            await ws.send_json({"type": "step", "name": "启动浏览器", "status": "ok", "message": "浏览器已启动"})
        except Exception as exc:
            await ws.send_json({"type": "result", "success": False, "message": f"启动浏览器失败: {exc}", "duration_ms": 0})
            return True

    if not remove_emails:
        emails, _ = await asyncio.get_running_loop().run_in_executor(
            None, _swap_resolve_remove_emails, account_id,
        )
        if not emails:
            await ws.send_json({"type": "result", "success": False, "message": "当前家庭组没有子号可替换", "duration_ms": 0})
            return True

        remove_emails = emails
        if new_count <= 0 and not specific_emails:
            new_count = len(remove_emails)

        await ws.send_json({
            "type": "step", "name": "换号",
            "status": "info",
            "message": f"将移除 {len(remove_emails)} 个子号: {', '.join(remove_emails)}",
        })

    remove_success = 0
    if remove_emails:
        remove_success = await _swap_phase_remove(
            ws, msg_queue, cancel_token, profile_id, account_id, password, totp_secret, remove_emails,
        )
        if remove_success < 0:  # cancelled
            return False
        if remove_success < len(remove_emails):
            await ws.send_json({
                "type": "result",
                "success": False,
                "message": f"移除未全部成功 ({remove_success}/{len(remove_emails)}), 已中止换号",
                "duration_ms": 0,
            })
            return True

    if specific_emails:
        selected_emails = specific_emails
        actual_count = len(selected_emails)
        await ws.send_json({"type": "step", "name": PHASE_INVITE_NEW, "status": "info", "message": f"指定 {actual_count} 个账号"})
    else:
        await ws.send_json({"type": "result", "success": False, "message": "请指定新成员邮箱", "duration_ms": 0})
        return True

    await ws.send_json({"type": "step", "name": "选号完成", "status": "ok", "message": f"已选取 {actual_count} 个: {', '.join(selected_emails)}"})

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

    await ws.send_json({"type": "step", "name": "邀请完成", "status": "ok", "message": f"邀请成功 {len(invite_success)}/{actual_count}"})

    if not invite_success:
        await ws.send_json({"type": "result", "success": False, "message": f"邀请全部失败: {'; '.join(invite_fail)}", "duration_ms": 0})
        return True

    sub_map = await asyncio.get_running_loop().run_in_executor(
        None, _swap_batch_load_sub_accounts, invite_success,
    )

    accept_success, accept_fail = await _swap_phase_login_and_accept(
        ws, msg_queue, cancel_token, account_id, invite_success, sub_map,
    )

    verified_count = await _swap_phase_discover_sync(
        ws, profile_id, account_id, invite_success,
    )
    if verified_count > 0:
        accept_success = verified_count

    parts = []
    if remove_emails:
        parts.append(f"移除 {remove_success}/{len(remove_emails)}")
    parts.append(f"邀请 {len(invite_success)}/{actual_count}")
    parts.append(f"加入 {accept_success}/{len(invite_success)}")
    summary = f"换号完成: {', '.join(parts)}"
    if accept_fail:
        summary += f" | 失败: {'; '.join(accept_fail)}"

    await ws.send_json({"type": "result", "success": accept_success > 0 or verified_count > 0, "message": summary, "duration_ms": 0})
    return True
