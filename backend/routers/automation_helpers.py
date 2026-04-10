"""自动化操作 - WebSocket 基础设施 (步骤回调 / 队列转发 / 取消轮询 / 任务结果)"""
import asyncio
import json
import logging
import queue

from fastapi import WebSocket, WebSocketDisconnect

from services.automation import CancellationToken

logger = logging.getLogger(__name__)


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
