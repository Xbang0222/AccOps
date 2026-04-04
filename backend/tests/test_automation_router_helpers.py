import asyncio
import queue
import unittest

from routers.automation import _create_step_handler, _get_task_result


class AutomationRouterHelperTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
