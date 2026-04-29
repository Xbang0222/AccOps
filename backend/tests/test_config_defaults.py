import importlib
import os
import unittest

import config


class ConfigDefaultsTests(unittest.TestCase):
    def test_default_secret_key_is_stable_without_env(self) -> None:
        original = os.environ.pop("GAM_SECRET_KEY", None)
        try:
            first = importlib.reload(config).SECRET_KEY
            second = importlib.reload(config).SECRET_KEY

            self.assertEqual(first, second)
        finally:
            if original is not None:
                os.environ["GAM_SECRET_KEY"] = original
            importlib.reload(config)

    def test_default_cors_origins_include_localhost_and_loopback(self) -> None:
        original = os.environ.pop("GAM_CORS_ORIGINS", None)
        try:
            origins = importlib.reload(config).CORS_ORIGINS

            self.assertIn("http://localhost:17894", origins)
            self.assertIn("http://127.0.0.1:17894", origins)
        finally:
            if original is not None:
                os.environ["GAM_CORS_ORIGINS"] = original
            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
