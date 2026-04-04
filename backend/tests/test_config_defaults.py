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


if __name__ == "__main__":
    unittest.main()
