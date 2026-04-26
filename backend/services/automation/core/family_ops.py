"""家庭组 RPC 操作（create / invite / accept / remove / leave）。"""
from __future__ import annotations

import logging

from services.automation.core._shared import get_profile_id_from_page
from services.automation.types import AutomationResult, StepTracker
from services.browser import browser_manager, get_rapt_sync
from services.family_api import FamilyAPI, NoInvitationError, RPCError, TokenError

logger = logging.getLogger(__name__)


def create_family_group_sync(page, on_step=None, cancel_token=None) -> AutomationResult:
    """创建家庭组 (纯 RPC)"""
    tracker = StepTracker("create_family", on_step)

    tracker.step("提取 cookies", "info")
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            tracker.step("查询家庭组状态", "info")
            status = api.query_status()
            if status["has_family"]:
                return tracker.result(False, "已有家庭组, 无需创建", step="check")

            tracker.step("创建家庭组", "info", "nKULBd → Wffnob → c5gch")
            ok = api.create_family()

            if ok:
                return tracker.result(True, "家庭组创建成功")
            else:
                return tracker.result(False, "家庭组创建失败", step="create")
    except (TokenError, RPCError) as e:
        return tracker.result(False, str(e), step="rpc")
    except Exception as e:
        return tracker.result(False, f"异常: {e}", step="error")


def send_family_invite_sync(page, invite_email: str, on_step=None, cancel_token=None) -> AutomationResult:
    """发送家庭组邀请 (纯 RPC)"""
    tracker = StepTracker("send_invite", on_step)

    tracker.step("提取 cookies", "info")
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            tracker.step("发送邀请", "info", invite_email)
            result = api.send_invite(invite_email)

            if result["success"]:
                return tracker.result(True, f"邀请已发送: {invite_email}")
            else:
                err = result.get("error", "未知原因")
                return tracker.result(False, f"邀请发送失败: {invite_email} ({err})", step="invite")
    except (TokenError, RPCError) as e:
        return tracker.result(False, str(e), step="rpc")
    except Exception as e:
        return tracker.result(False, f"异常: {e}", step="error")


def accept_family_invite_sync(page, on_step=None, cancel_token=None) -> AutomationResult:
    """接受家庭组邀请 (纯 RPC)"""
    tracker = StepTracker("accept_invite", on_step)

    tracker.step("提取 cookies", "info")
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            tracker.step("查找并接受邀请", "info")
            result = api.accept_invite()

            if result["success"]:
                return tracker.result(True, "邀请已接受")
            else:
                error = result.get("error", "接受邀请失败")
                return tracker.result(False, error, step="accept")
    except NoInvitationError:
        return tracker.result(False, "没有待接受的邀请", step="no_invite")
    except (TokenError, RPCError) as e:
        return tracker.result(False, str(e), step="rpc")
    except Exception as e:
        return tracker.result(False, f"异常: {e}", step="error")


def remove_family_member_sync(page, member_email: str, password: str = "",
                              totp_secret: str = "", on_step=None) -> AutomationResult:
    """移除家庭组成员 (已接受成员需要 rapt, 未接受成员撤销邀请)"""
    tracker = StepTracker("remove_member", on_step)

    tracker.step("提取 cookies", "info")
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            tracker.step("查询成员列表", "info")
            members_info = api.query_members()
            if not members_info["has_family"]:
                return tracker.result(False, "不在家庭组中", step="check")

            target = None
            for m in members_info["members"]:
                if m.get("email", "").lower() == member_email.lower():
                    target = m
                    break

            if not target:
                return tracker.result(False, f"未找到成员: {member_email}", step="find_member")

            tracker.step("找到成员", "ok", f"{target['name']} ({target['user_id']})")

            if target.get("pending"):
                invitation_id = target.get("invitation_id")
                if not invitation_id:
                    return tracker.result(False, f"未找到邀请 ID: {member_email}", step="no_invite_id")

                tracker.step("撤销邀请", "info", member_email)
                ok = api.cancel_invite(invitation_id)
                if ok:
                    return tracker.result(True, f"已撤销邀请: {member_email}")
                else:
                    return tracker.result(False, f"撤销邀请失败: {member_email}", step="cancel")

            member_user_id = target["user_id"]

            tracker.step("密码重验证", "info", "获取 rapt token")
            rapt = get_rapt_sync(page, f"/family/remove/g/{member_user_id}", password, totp_secret)
            if not rapt:
                return tracker.result(False, "获取 rapt token 失败", step="rapt")
            tracker.step("rapt 获取成功", "ok")

            cookies = browser_manager.get_cookies(get_profile_id_from_page(page))
            api.client.cookies.update(cookies)
            api.refresh_tokens()

            tracker.step("移除成员", "info", member_email)
            ok = api.remove_member(member_user_id, rapt)

            if ok:
                return tracker.result(True, f"已移除成员: {member_email}")
            else:
                return tracker.result(False, f"移除成员失败: {member_email}", step="remove")
    except (TokenError, RPCError) as e:
        return tracker.result(False, str(e), step="rpc")
    except Exception as e:
        return tracker.result(False, f"异常: {e}", step="error")


def leave_family_group_sync(page, password: str = "", totp_secret: str = "",
                            on_step=None) -> AutomationResult:
    """退出/删除家庭组 (需要 rapt)"""
    tracker = StepTracker("leave_family", on_step)

    tracker.step("提取 cookies", "info")
    cookies = browser_manager.get_cookies(get_profile_id_from_page(page))

    try:
        with FamilyAPI(cookies) as api:
            tracker.step("查询家庭组状态", "info")
            members_info = api.query_members()
            if not members_info["has_family"]:
                return tracker.result(False, "不在家庭组中", step="check")

            is_admin = members_info["is_admin"]
            action = "删除家庭组" if is_admin else "退出家庭组"
            target_path = "/family/delete" if is_admin else "/family/leave"

            tracker.step("密码重验证", "info", f"{action} - 获取 rapt")
            rapt = get_rapt_sync(page, target_path, password, totp_secret)
            if not rapt:
                return tracker.result(False, "获取 rapt token 失败", step="rapt")
            tracker.step("rapt 获取成功", "ok")

            cookies = browser_manager.get_cookies(get_profile_id_from_page(page))
            api.client.cookies.update(cookies)
            api.refresh_tokens()

            tracker.step(action, "info")
            if is_admin:
                ok = api.delete_family(rapt)
            else:
                ok = api.leave_family(rapt)

            if ok:
                return tracker.result(True, f"{action}成功")
            else:
                return tracker.result(False, f"{action}失败", step="leave_delete")
    except (TokenError, RPCError) as e:
        return tracker.result(False, str(e), step="rpc")
    except Exception as e:
        return tracker.result(False, f"异常: {e}", step="error")
