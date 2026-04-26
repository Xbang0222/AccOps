import unittest
from unittest.mock import AsyncMock, patch

from services.automation import run_phone_verify


class AutomationWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_phone_verify_returns_browser_not_running_result(self) -> None:
        with patch("services.automation.runners.browser_manager.get_page", return_value=None):
            result = await run_phone_verify(1, "https://example.com/verify")

        self.assertFalse(result.success)
        self.assertEqual(result.message, "浏览器未启动")

    async def test_run_phone_verify_wraps_sync_phone_result(self) -> None:
        page = object()

        with patch("services.automation.runners.browser_manager.get_page", return_value=page), patch(
            "services.automation.runners._run_sync",
            new=AsyncMock(return_value={"success": True, "message": "验证成功", "code": "123456"}),
        ) as run_sync_mock:
            result = await run_phone_verify(3, "https://example.com/verify")

        self.assertTrue(result.success)
        self.assertEqual(result.message, "验证成功")
        self.assertEqual(result.extra["code"], "123456")
        run_sync_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
