"""自动化模块内部共享工具（不对外暴露）。"""
from __future__ import annotations

import logging

from services.browser import browser_manager

logger = logging.getLogger(__name__)


def is_debug_mode() -> bool:
    """读取 config 表的 debug_mode 设置（D4 阶段会迁移到 runtime_config）。"""
    try:
        from models.database import get_db_session
        from models.orm import Config
        with get_db_session() as db:
            row = db.query(Config).filter(Config.key == "debug_mode").first()
            return row.value == "true" if row else False
    except Exception:
        return False


def get_profile_id_from_page(page) -> int:
    """从 page 对象反查 profile_id（用于 sync 函数内提取 cookies）。"""
    for pid, inst in browser_manager._instances.items():
        if inst.page is page:
            return pid
    ids = browser_manager.get_running_ids()
    return ids[0] if ids else 0


def build_member_list(members_info: dict, *, admin_role_const: str) -> list[dict]:
    """把 family_api.query_members() 的输出转成 discover 用的标准成员列表。

    消除 discover_family_group_sync 与 _discover_from_cookies 的重复代码。
    """
    members: list[dict] = []
    for m in members_info["members"]:
        if m.get("pending"):
            role_str = "pending"
        elif m["role"] == admin_role_const:
            role_str = "manager"
        else:
            role_str = "member"
        members.append({
            "name": m["name"],
            "email": m.get("email", ""),
            "role": role_str,
        })
    return members
