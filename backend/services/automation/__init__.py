"""自动化模块公共 API

包结构：
    types.py            数据类型 (AutomationResult / FamilyDiscoverResult / StepTracker / CancellationToken)
    runners.py          异步包装器 (run_*) — router 层调用入口
    persistence.py      cookies / OAuth / 订阅状态落库
    ws_helpers.py       WebSocket 基础设施 (create_step_handler / drain_task_queue / get_task_result / flush_step_messages)
    core/
        login.py        登录 sync 函数
        family_ops.py   家庭组 RPC sync 函数
        discover.py     discover 4 级回退 + discover_family_by_cookies
        _shared.py      内部工具 (is_debug_mode / get_profile_id_from_page / build_member_list)
    orchestrator/
        swap.py         换号编排 (handle_family_swap)

router 层从顶层 `services.automation` 导入业务函数; WS 工具与编排器
按需从 `services.automation.ws_helpers` / `services.automation.orchestrator.swap` 子路径导入。
"""
from services.automation.core.discover import discover_family_by_cookies
from services.automation.runners import (
    run_accept_family_invite,
    run_auto_login,
    run_create_family_group,
    run_leave_family_group,
    run_oauth,
    run_phone_verify,
    run_remove_family_member,
    run_send_family_invite,
)
from services.automation.types import (
    AutomationResult,
    CancellationToken,
    CancelledError,
    ErrorCode,
    FamilyDiscoverResult,
    StepTracker,
)

__all__ = [
    # types
    "AutomationResult",
    "CancellationToken",
    "CancelledError",
    "ErrorCode",
    "FamilyDiscoverResult",
    "StepTracker",
    # discover
    "discover_family_by_cookies",
    # runners
    "run_accept_family_invite",
    "run_auto_login",
    "run_create_family_group",
    "run_leave_family_group",
    "run_oauth",
    "run_phone_verify",
    "run_remove_family_member",
    "run_send_family_invite",
]
