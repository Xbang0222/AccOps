import asyncio
import json
import queue
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import WebSocketDisconnect

from deps import create_access_token
from models.orm import Account, BrowserProfile
from routers.automation_helpers import (
    _create_step_handler,
    _get_task_result,
)
from routers.automation_ws import (
    automation_websocket,
)
from services.automation.persistence import (
    sync_account_state_after_login,
)


class AutomationRouterHelperTests(unittest.IsolatedAsyncioTestCase):
    class _FakeQuery:
        def __init__(self, result) -> None:
            self._result = result

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self._result

    class _FakeDb:
        def __init__(self, account, profile) -> None:
            self._account = account
            self._profile = profile

        def query(self, model):
            if model is Account:
                return AutomationRouterHelperTests._FakeQuery(self._account)
            if model is BrowserProfile:
                return AutomationRouterHelperTests._FakeQuery(self._profile)
            raise AssertionError(f"Unexpected model: {model}")

    class _FakeWebSocket:
        def __init__(self, token: str, messages: list[str]) -> None:
            self.query_params = {"token": token}
            self._messages = messages
            self.sent_messages: list[dict] = []
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive_text(self) -> str:
            if self._messages:
                return self._messages.pop(0)
            raise WebSocketDisconnect()

        async def send_json(self, data: dict) -> None:
            self.sent_messages.append(data)

        async def close(self, code: int = 1000, reason: str | None = None) -> None:
            return None

    async def test_create_step_handler_applies_offset(self) -> None:
        message_queue = queue.Queue()
        on_step = _create_step_handler(message_queue, 200)

        on_step({"type": "step", "step": 3, "name": "test"})

        self.assertEqual(message_queue.get_nowait()["step"], 203)

    async def test_get_task_result_returns_result_without_error(self) -> None:
        async def succeed():
            return "ok"

        task = asyncio.create_task(succeed())
        await task

        result, error_message = _get_task_result(task)

        self.assertEqual(result, "ok")
        self.assertEqual(error_message, "")

    async def test_get_task_result_returns_error_message(self) -> None:
        async def fail():
            raise RuntimeError("boom")

        task = asyncio.create_task(fail())
        with self.assertRaises(RuntimeError):
            await task

        result, error_message = _get_task_result(task)

        self.assertIsNone(result)
        self.assertEqual(error_message, "boom")

    async def test_sync_account_state_after_login_updates_subscription(self) -> None:
        discover_result = type(
            "DiscoverResult",
            (),
            {
                "success": True,
                "message": "ok",
                "subscription_status": "ultra",
                "subscription_expiry": "Mar 23, 2026",
            },
        )()

        with patch("services.automation.persistence.browser_manager.get_cookies", return_value={"SID": "cookie"}), patch(
            "services.automation.persistence.discover_family_by_cookies",
            return_value=discover_result,
        ) as discover_mock, patch("services.automation.persistence.save_subscription_status") as save_subscription_mock:
            sync_account_state_after_login(
                account_id=7,
                profile_id=9,
                email="user@example.com",
                password="secret",
                totp_secret="totp",
                recovery_email="recovery@example.com",
            )

        discover_mock.assert_called_once()
        save_subscription_mock.assert_called_once_with(7, "ultra", "Mar 23, 2026")

    async def test_automation_websocket_sends_result_message_after_login_success(self) -> None:
        token = create_access_token({"sub": "user"})
        account = type(
            "FakeAccount",
            (),
            {
                "id": 1,
                "email": "user@example.com",
                "password": "secret",
                "totp_secret": "",
                "recovery_email": "",
                "notes": "",
            },
        )()
        profile = type("FakeProfile", (), {"id": 11, "account_id": 1})()
        fake_db = self._FakeDb(account, profile)
        ws = self._FakeWebSocket(token, [json.dumps({"action": "login", "account_id": 1})])
        result = type("AutomationResult", (), {"success": True, "message": "登录成功"})()

        @contextmanager
        def fake_db_session():
            yield fake_db

        async def fake_drain_task_queue(_ws, _msg_queue, task, _cancel_token):
            await task
            return True

        with patch("routers.automation_ws.get_db_session", fake_db_session), patch(
            "routers.automation_ws.browser_manager.is_running",
            return_value=True,
        ), patch("routers.automation_ws.run_auto_login", return_value=result), patch(
            "routers.automation_ws._drain_task_queue",
            side_effect=fake_drain_task_queue,
        ), patch("routers.automation_ws.handle_login_success") as handle_login_success_mock:
            await automation_websocket(ws)

        self.assertTrue(ws.accepted)
        self.assertIn(
            {
                "type": "result",
                "success": True,
                "message": "登录成功",
                "duration_ms": 0,
            },
            ws.sent_messages,
        )
        handle_login_success_mock.assert_called_once_with(
            1,
            11,
            "user@example.com",
            "secret",
            "",
            "",
        )


if __name__ == "__main__":
    unittest.main()
