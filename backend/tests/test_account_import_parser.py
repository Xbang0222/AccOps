import unittest

from services.account_import_parser import parse_account_import_line


class ParseAccountImportLineTests(unittest.TestCase):
    def test_parse_line_with_totp_link_and_extra_notes(self) -> None:
        result = parse_account_import_line(
            "foo@gmail.com----password----recover@gmail.com----JBSWY3DPEHPK3PXP----https://example.com/verify----美国",
            default_tags="tag-a",
            default_group_name="group-a",
            default_notes="base",
        )

        self.assertEqual(result.email, "foo@gmail.com")
        self.assertEqual(result.password, "password")
        self.assertEqual(result.recovery_email, "recover@gmail.com")
        self.assertEqual(result.totp_secret, "JBSWY3DPEHPK3PXP")
        self.assertEqual(result.tags, "tag-a")
        self.assertEqual(result.group_name, "group-a")
        self.assertIn("验证链接: https://example.com/verify", result.notes)
        self.assertIn("base", result.notes)
        self.assertTrue(result.notes.endswith("美国"))

    def test_parse_pipe_delimited_line(self) -> None:
        result = parse_account_import_line(
            "foo@gmail.com|password|recover@gmail.com",
        )

        self.assertEqual(result.email, "foo@gmail.com")
        self.assertEqual(result.password, "password")
        self.assertEqual(result.recovery_email, "recover@gmail.com")
        self.assertEqual(result.totp_secret, "")
        self.assertEqual(result.notes, "")

    def test_reject_empty_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "邮箱为空"):
            parse_account_import_line("----password")


if __name__ == "__main__":
    unittest.main()
