"""Offline reproducibility, CI status and upstream integrity contracts.

All tests use temporary local fixtures. No network access and no phone I/O.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/fetch_upstreams.py"
SPEC = importlib.util.spec_from_file_location("fetch_upstreams", SRC)
FETCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FETCH)


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE
    ).strip()


class SourcePinAndCiTests(unittest.TestCase):
    def test_all_upstream_pins_have_exact_commit_sha(self):
        data = FETCH.load_manifest()
        self.assertEqual(set(data["sources"]), {
            "linux", "m1n1", "boot_kit", "documentation"
        })
        for entry in data["sources"].values():
            self.assertEqual(len(entry["commit"]), 40)
            self.assertTrue(entry["url"].startswith("https://github.com/"))

    def test_rejects_non_pinned_or_non_github_source(self):
        data = FETCH.load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "upstreams.json"
            data["sources"]["linux"]["commit"] = "HEAD"
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "40-hex"):
                FETCH.load_manifest(manifest)
            data["sources"]["linux"]["commit"] = "0" * 40
            data["sources"]["linux"]["url"] = "file:///tmp/private"
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "GitHub"):
                FETCH.load_manifest(manifest)

    def test_verify_checkout_requires_exact_sha_and_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local-test-repo"
            path.mkdir()
            git("init", "-q", cwd=path)
            git("config", "user.name", "CI fixture", cwd=path)
            git("config", "user.email", "noreply@github.com", cwd=path)
            git("config", "commit.gpgsign", "false", cwd=path)
            (path / "test.txt").write_text("public synthetic fixture")
            git("add", ".", cwd=path)
            git("commit", "-qm", "fixture", cwd=path)
            origin = "https://github.com/example/synthetic-kernel.git"
            git("remote", "add", "origin", origin, cwd=path)
            source = {"url": origin, "commit": git("rev-parse", "HEAD", cwd=path)}
            FETCH.verify_checkout(path, source)
            with self.assertRaisesRegex(ValueError, "HEAD"):
                FETCH.verify_checkout(path, {"url": origin, "commit": "1" * 40})
            with self.assertRaisesRegex(ValueError, "origin"):
                FETCH.verify_checkout(path, {
                    "url": "https://github.com/elsewhere/repo.git",
                    "commit": source["commit"]
                })
            (path / "test.txt").write_text("different uncommitted content")
            with self.assertRaisesRegex(ValueError, "dirty"):
                FETCH.verify_checkout(path, source)

    def test_s8003_never_claimed_live(self):
        matrix = json.loads((ROOT / "manifests/test-matrix.json").read_text())
        variant = next(p for p in matrix["profiles"] if p["id"] == "s8003-n71m")
        self.assertFalse(variant["evidence"])
        self.assertEqual(set(variant["hardware_results"].values()), {"not_tested"})
        self.assertEqual(variant["experiment_policy"],
                         "deferred_until_compatible_device_available")

    def test_live_touch_status_cannot_derive_from_hbpp(self):
        matrix = json.loads((ROOT / "manifests/test-matrix.json").read_text())
        s8000 = next(p for p in matrix["profiles"] if p["id"] == "s8000-n71")
        state = s8000["hardware_results"]
        self.assertEqual(state["hbpp_strict_read"], "live_pass")
        self.assertNotEqual(state["touch_evdev_multitouch"], "live_pass")
        self.assertEqual(state["calibration_ack_data"], "live_pass")

    def test_workflow_separates_three_levels(self):
        content = (ROOT / "ci/verify.yml").read_text()
        self.assertIn('"on":', content)
        self.assertIn("OFFLINE |", content)
        self.assertIn("BUILD |", content)
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("compile_kernel_rfc:", content)
        self.assertNotIn("hardware-live-pass", content)

    def test_no_proprietary_files_in_public_source_workflow(self):
        content = (ROOT / "ci/verify.yml").read_text()
        self.assertNotIn("curl -L", content)
        self.assertNotIn("IPSW", content)
        self.assertNotIn("firmware-private/", content)
        self.assertIn("Only the job status and compiler diagnostics", content)

    def test_sanitized_evidence_has_no_device_identifiers(self):
        for filename in sorted((ROOT / "results").glob("*.json")):
            with self.subTest(file=filename.name):
                value = json.loads(filename.read_text())
                self.assertEqual(value["profile"], "s8000-n71")
                self.assertEqual(value["level"], "hardware")
                self.assertIn(value["result"], ("live_pass", "partial", "blocked"))
                self.assertNotIn("serial", filename.read_text().lower())
                self.assertNotIn("private_key", filename.read_text().lower())


if __name__ == "__main__":
    unittest.main()
