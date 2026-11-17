"""Offline source-data minimization and rendering gates for the N71 companion push."""
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experimental/briefing/n71_push_briefing.py"
spec = importlib.util.spec_from_file_location("push", PATH)
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)
ZONE = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 16, 16, 30, tzinfo=ZONE)

def sample():
    return {
        "generated_at": NOW.isoformat(),
        "brief": {
            "overview": "Review the launch proposal.",
            "actions": [{"title": "Call supplier", "reason": "Reply needed", "source": "email"}],
            "suggested_todos": [{"text": "Check deadline", "due": "", "priority": "alta", "source": "calendar"}]
        },
        "source_status": {"mail": "connected", "calendar": "connected", "whatsapp": "unavailable"},
        "mail": [{"body": "SECRET_BODY_NEVER_LEAK"}],
        "whatsapp_raw": [{"text": "SECRET_CHAT_NEVER_LEAK"}],
        "oauth_token": "SECRET_TOKEN_NEVER_LEAK",
        "agenda": [{"title": "Status check", "start": "2026-11-17T10:00:00+01:00"}],
        "error": "",
    }

class BriefingPush(unittest.TestCase):
    def test_reduced_payload_and_no_credentials(self):
        data, encoded, display = push.payload_from(sample(), NOW)
        self.assertFalse(data["cached"])
        self.assertTrue(data["whatsapp_is_notification_only"])
        for forbidden in (b"SECRET_BODY_NEVER_LEAK", b"SECRET_CHAT_NEVER_LEAK", b"SECRET_TOKEN_NEVER_LEAK"):
            self.assertNotIn(forbidden, encoded)
            self.assertNotIn(forbidden, display)
        self.assertIn(b"Call supplier", display)
        self.assertIn(b"Status check", display)

    def test_stale_and_invalid_context(self):
        source = sample()
        source["generated_at"] = (NOW - timedelta(hours=7)).isoformat()
        data, _, _ = push.payload_from(source, NOW)
        self.assertTrue(data["cached"])
        source["generated_at"] = (NOW + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            push.payload_from(source, NOW)
        source = sample()
        source["error"] = "upstream error"
        with self.assertRaises(ValueError):
            push.payload_from(source, NOW)

    def test_terminal_control_characters_removed(self):
        source = sample()
        source["brief"]["overview"] = "\x1b[31mUrgent\x07 item"
        data, _, terminal = push.payload_from(source, NOW)
        self.assertNotIn(b"\x1b", terminal)
        self.assertNotIn(b"\x07", terminal)
        self.assertIn("Urgent", data["overview"])

    def test_no_embedded_account_secrets_or_network_bypass(self):
        src = PATH.read_text()
        self.assertIn("SSH_CONFIG", src)
        self.assertIn("ssh_push", src)
        self.assertIn("no fallback transport", src)
        self.assertNotIn("OPENAI_API_KEY", src)
        ui = (ROOT / "examples/cyberdeck-shell/cyberdeck-shell.c").read_text()
        self.assertIn('"/run/cyberdeck/today.txt"', ui)
        self.assertIn('"TODAY"', ui)

    def test_private_policy_revision_blocks_stale_ai_phone_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "wa-privacy.json"
            doc = {"version": 1, "mode": "strict", "include_groups": False,
                   "excluded_contacts": [], "excluded_groups": []}
            policy.write_text(json.dumps(doc))
            policy.chmod(0o600)
            info = policy.stat()
            state = {"wa_privacy_revision": f"{info.st_mtime_ns}:{info.st_size}"}
            self.assertEqual(push.assert_whatsapp_privacy_revision(state, policy),
                             state["wa_privacy_revision"])
            doc["excluded_contacts"].append("excluded-test-contact")
            policy.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "exclusions changed"):
                push.assert_whatsapp_privacy_revision(state, policy)

    def test_insecure_or_malformed_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "wa-privacy.json"
            policy.write_text('{"version":1,"mode":"open"}')
            policy.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "Invalid or incomplete"):
                push.assert_whatsapp_privacy_revision({"wa_privacy_revision": "unconfigured"}, policy)
            policy.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "not private"):
                push.assert_whatsapp_privacy_revision({"wa_privacy_revision": "unconfigured"}, policy)

    def test_unconfigured_policy_must_match_state_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "not-configured.json"
            with self.assertRaisesRegex(ValueError, "exclusions changed"):
                push.assert_whatsapp_privacy_revision({}, missing)
            self.assertEqual(push.assert_whatsapp_privacy_revision(
                {"wa_privacy_revision": "unconfigured"}, missing), "unconfigured")


if __name__ == "__main__":
    unittest.main()
