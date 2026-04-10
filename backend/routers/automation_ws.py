"""自动化操作 - WebSocket handler + 批量登录"""
import asyncio
import json
import logging
import queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.database import get_db_session
from models.orm import Account, BrowserProfile
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
from services.browser import browser_manager
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
    ACTION_FAMILY_SWAP,
    ACTION_POOL_BATCH_LOGIN,
    ACTION_OAUTH,
    ACTION_PHONE_VERIFY,
)

from routers.automation_helpers import (
    _create_step_handler,
    _flush_step_messages,
    _poll_cancel_command,
    _drain_task_queue,
    _get_task_result,
)
from services.automation_utils import (
    decrypt_field,
    save_browser_cookies,
    save_oauth_credential,
    handle_login_success,
    save_subscription_status,
)
from routers.automation_swap import _handle_family_swap

logger = logging.getLogger(__name__)


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
                "password": decrypt_field(row.password),
                "totp_secret": decrypt_field(row.totp_secret),
                "recovery_email": decrypt_field(row.recovery_email),
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
                save_browser_cookies(acct["id"], profile_id)
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
                # family-discover / family-swap / pool-batch-login 不强制要求浏览器运行
                # login 也豁免 (启动浏览器后自动登录, 避免竞态)
                if action in (ACTION_FAMILY_DISCOVER, ACTION_FAMILY_SWAP, ACTION_POOL_BATCH_LOGIN, "login"):
                    profile_id = profile.id if profile else None
                elif not profile or not browser_manager.is_running(profile.id):
                    await ws.send_json({"type": "error", "message": f"浏览器未启动 (action={action})"})
                    continue
                else:
                    profile_id = profile.id
                email = account.email
                password = decrypt_field(account.password)
                totp_secret = decrypt_field(account.totp_secret) or ""
                recovery_email = decrypt_field(account.recovery_email) or ""
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
                    save_subscription_status(account_id, dr.subscription_status, dr.subscription_expiry)
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
            elif action == ACTION_FAMILY_SWAP:
                swap_remove = [e.strip() for e in data.get("remove_emails", "").split(",") if e.strip()]
                swap_count = int(data.get("new_count", "0") or "0")
                swap_specific = [e.strip() for e in data.get("specific_emails", "").split(",") if e.strip()]
                if not await _handle_family_swap(
                    ws=ws,
                    msg_queue=msg_queue,
                    cancel_token=cancel_token,
                    profile_id=profile_id,
                    account_id=account_id,
                    password=password,
                    totp_secret=totp_secret,
                    remove_emails=swap_remove,
                    new_count=swap_count,
                    specific_emails=swap_specific or None,
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
                        handle_login_success(
                            account_id,
                            profile_id,
                            email,
                            password,
                            totp_secret,
                            recovery_email,
                        )
                    else:
                        save_browser_cookies(account_id, profile_id)
                    # OAuth 成功后保存凭证
                    if action == ACTION_OAUTH and hasattr(result, 'extra') and result.extra and result.extra.get("credential"):
                        save_oauth_credential(account_id, result.extra["credential"])
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
