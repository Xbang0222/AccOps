import unittest

from fastapi.security import HTTPAuthorizationCredentials

from deps import create_access_token, verify_token, verify_ws_token, state


class AuthTokenPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        state.logged_in = False

    def test_http_token_remains_valid_without_runtime_login_flag(self) -> None:
        token = create_access_token({"sub": "user"})
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )

        payload = verify_token(credentials)

        self.assertEqual(payload["sub"], "user")

    def test_websocket_token_remains_valid_without_runtime_login_flag(self) -> None:
        token = create_access_token({"sub": "user"})

        self.assertTrue(verify_ws_token(token))


if __name__ == "__main__":
    unittest.main()
