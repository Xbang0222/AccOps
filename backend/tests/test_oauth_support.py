import unittest
from urllib.parse import parse_qs, urlparse

from services.oauth_support import build_auth_url, check_for_code, check_for_error, extract_validation_url


class OAuthSupportTests(unittest.TestCase):
    def test_build_auth_url_contains_expected_query(self) -> None:
        url = build_auth_url("state-123")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(query["state"], ["state-123"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertIn("scope", query)

    def test_extract_validation_url_prefers_metadata_url(self) -> None:
        error_text = (
            '[{"error":{"details":[{"metadata":{"validation_url":"https://accounts.google.com/test-link"}}]}}]'
        )
        self.assertEqual(
            extract_validation_url(error_text),
            "https://accounts.google.com/test-link",
        )

    def test_check_for_code_and_error(self) -> None:
        self.assertEqual(
            check_for_code("http://localhost:51121/oauth-callback?code=abc123&state=x"),
            "abc123",
        )
        self.assertEqual(
            check_for_error("http://localhost:51121/oauth-callback?error=access_denied"),
            "access_denied",
        )


if __name__ == "__main__":
    unittest.main()
