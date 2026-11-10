"""Offline tests for Git identity privacy pre-push gate."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_git_privacy", ROOT / "tools/security/check_git_privacy.py"
)
PRIVACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRIVACY)


class GitPrivacyTests(unittest.TestCase):
    def test_numeric_plus_noreply_identity(self):
        self.assertTrue(PRIVACY.allowed_identity("123+sample@users.noreply.github.com"))

    def test_plain_noreply_identity(self):
        self.assertTrue(PRIVACY.allowed_identity("example@users.noreply.github.com"))

    def test_github_legacy_committer(self):
        self.assertTrue(PRIVACY.allowed_identity("noreply@github.com"))

    def test_personal_email_rejected(self):
        self.assertFalse(PRIVACY.allowed_identity("person" + "@" + "personal-mail.test"))

    def test_unicode_or_invalid_values_rejected(self):
        for value in ["", " ", "John Doe", "x" + "@" + "other.github.com", "ü@users.noreply.github.com"]:
            with self.subTest(value=value):
                self.assertFalse(PRIVACY.allowed_identity(value))


if __name__ == "__main__":
    unittest.main()
