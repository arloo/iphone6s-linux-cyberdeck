#!/usr/bin/env python3
"""Fail closed when public project manifest, evidence or CI hierarchy regresses."""
from __future__ import annotations

import json
from pathlib import Path
import re
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"live_pass", "partial", "blocked", "not_tested"}
TASKS = {
    "ram_boot", "framebuffer_750x1334", "spi2_host_lifecycle",
    "touch_clock_rollback", "touch_analog_rollback", "hbpp_strict_read",
    "calibration_ack_data", "touch_evdev_multitouch",
    "wifi_network", "bluetooth_scan", "bluetooth_pairing",
    "authenticated_remote_shell",
}
COMPONENTS = {"linux", "m1n1", "boot_kit", "documentation"}
SECRET_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@(?:gmail|yahoo|outlook|hotmail|actomedia)\.[a-z.]+"
    r"|(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"
    r"|-----BEGIN [^-]+PRIVATE KEY"
)


def check() -> None:
    upstream = json.loads((ROOT / "manifests/upstreams.json").read_text())
    matrix = json.loads((ROOT / "manifests/test-matrix.json").read_text())
    assert upstream["schema_version"] == matrix["schema_version"] == 1
    assert set(upstream["sources"]) == COMPONENTS
    assert upstream["policy"]["fetch_source_only"] is True
    assert upstream["policy"]["proprietary_assets_in_repository"] is False
    for name, obj in upstream["sources"].items():
        assert re.fullmatch(r"[0-9a-f]{40}", obj["commit"]), name
        assert re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+\.git", obj["url"]), name
    assert matrix["upstream_kernel_commit"] == upstream["sources"]["linux"]["commit"]
    assert date.fromisoformat(matrix["last_reviewed"]) <= date.today()
    profiles = {item["id"]: item for item in matrix["profiles"]}
    assert set(profiles) == set(upstream["profiles"])
    expected = {"s8000-n71", "s8003-n71m"}
    assert set(profiles) == expected
    for name, profile in profiles.items():
        assert profile["dtb"] == upstream["profiles"][name]["dtb"]
        results = profile["hardware_results"]
        assert set(results) == TASKS
        assert set(results.values()) <= STATUSES
        for evidence in profile["evidence"]:
            path = ROOT / evidence
            assert path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
    assert all(s == "not_tested" for s in profiles["s8003-n71m"]["hardware_results"].values())
    assert profiles["s8003-n71m"]["experiment_policy"] == "deferred_until_compatible_device_available"
    assert not profiles["s8003-n71m"]["evidence"]
    s8000 = profiles["s8000-n71"]["hardware_results"]
    assert s8000["hbpp_strict_read"] == "live_pass"
    assert s8000["touch_evdev_multitouch"] != "live_pass"
    assert s8000["calibration_ack_data"] != "live_pass"
    assert s8000["authenticated_remote_shell"] != "live_pass"

    # Evidence is a manually reviewed sanitized artifact, never a CI assertion.
    for path in sorted((ROOT / "results").glob("*.json")):
        item = json.loads(path.read_text())
        assert item["schema_version"] == 1
        assert item["profile"] in profiles
        assert item["level"] == "hardware"
        assert item["result"] in STATUSES
        assert date.fromisoformat(item["observed_on"]) <= date.today()
        assert item["evidence_report"] in profiles[item["profile"]]["evidence"]
        assert not SECRET_PATTERN.search(path.read_text())
        assert set(item) == {
            "schema_version", "profile", "level", "result",
            "test_id", "observed_on", "kernel_source_commit",
            "evidence_report", "summary"
        }
        assert item["kernel_source_commit"] == upstream["sources"]["linux"]["commit"]

    # The workflow is source-controlled even before GitHub grants the
    # separate workflow-write permission needed to activate Actions.
    workflow = (ROOT / "ci/verify.yml").read_text()
    active = ROOT / ".github/workflows/verify.yml"
    if active.exists():
        assert active.read_text() == workflow, "active workflow differs from versioned template"
    for marker in ("OFFLINE |", "BUILD |", "workflow_dispatch:",
                   "make test", "make all", "scripts/check_kernel_rfc.sh"):
        assert marker in workflow, marker
    assert not SECRET_PATTERN.search(workflow)
    print("MANIFEST_AND_EVIDENCE_PASS: 2 A9 variants, no S8003 hardware claims")
    print("GITHUB_ACTIONS=" + ("WORKFLOW_FILE_PRESENT_LOCAL_ONLY" if active.exists()
                               else "TEMPLATE_PREPARED_NOT_ACTIVATED"))


if __name__ == "__main__":
    check()
