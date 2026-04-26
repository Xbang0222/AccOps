"""自动化 WebSocket 基础设施 (步骤回调 / 队列转发 / 取消轮询 / 任务结果)。

公开 API: create_step_handler / drain_task_queue / get_task_result / flush_step_messages。
内部细节: _poll_cancel_command / _sanitize_error。
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import re

from fastapi import WebSocket, WebSocketDisconnect

from services.automation.types import CancellationToken

logger = logging.getLogger(__name__)


def create_step_handler(msg_queue: queue.Queue, step_offset: int = 0):
    """创建带步骤偏移的步骤回调。"""
    def on_step(step_data: dict):
        if step_offset and step_data.get("step"):
            step_data = {**step_data, "step": step_data["step"] + step_offset}
        msg_queue.put(step_data)

    return on_step


async def flush_step_messages(ws: WebSocket, msg_queue: queue.Queue):
    """将队列中的步骤消息转发给前端。"""
    # queue.empty() 与 get_nowait() 之间存在竞态; 以 try/except 收口防御 queue.Empty
    while True:
        try:
            message = msg_queue.get_nowait()
        except queue.Empty:
            break
        if message.get("type") != "result":
            await ws.send_json(message)


async def _poll_cancel_command(ws: WebSocket, cancel_token: CancellationToken) -> bool:
    """轮询前端取消命令; 返回 False 表示连接已断开。"""
    try:
        raw_cancel = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
        incoming = json.loads(raw_cancel)
        # 客户端可能发送非 dict JSON (如纯数字/字符串), 忽略而非崩溃
        if isinstance(incoming, dict) and incoming.get("action") == "cancel":
            cancel_token.cancel()
            await ws.send_json({"type": "step", "name": "取消操作", "status": "info", "message": "正在取消..."})
        return True
    except TimeoutError:
        return True
    except json.JSONDecodeError:
        return True
    except WebSocketDisconnect:
        cancel_token.cancel()
        return False
    except RuntimeError:
        # WebSocket 处于无法 receive 的状态 (已关闭/状态错乱), 视为断连
        cancel_token.cancel()
        return False


async def drain_task_queue(ws: WebSocket, msg_queue: queue.Queue, task, cancel_token: CancellationToken) -> bool:
    """在任务执行期间持续转发步骤, 并监听取消信号。"""
    while not task.done():
        await flush_step_messages(ws, msg_queue)
        if not await _poll_cancel_command(ws, cancel_token):
            return False

    await flush_step_messages(ws, msg_queue)
    return True


def _sanitize_error(exc: Exception) -> str:
    """Truncate and strip internal file paths from exception messages."""
    msg = str(exc)[:200]
    msg = re.sub(r'/[\w/.-]+\.py:\d+', '[internal]', msg)
    return msg


def get_task_result(task):
    """提取已完成任务的结果与错误消息。"""
    exception = task.exception()
    if exception:
        return None, _sanitize_error(exception)
    return task.result(), ""


__all__ = [
    "create_step_handler",
    "drain_task_queue",
    "flush_step_messages",
    "get_task_result",
]
