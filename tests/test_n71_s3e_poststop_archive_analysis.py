# SPDX-License-Identifier: MIT
"""Host-only replay contracts for sanitized archived S3E post-stop snapshots."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/storage/analyze_n71_s3e_poststop.py"
SPEC = importlib.util.spec_from_file_location("n71_s3e_poststop_analyzer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

def record(
    fifo="00000201", dart="00000500",
    t1="18.003", t2="18.004", t3="18.005",
    include_shutdown=True, include_identify=True,
):
    parts = ["[  10.001] unrelated: ECID=9999999912345678 PRIVATE_PATH=/tmp/DO_NOT_PRINT"]
    if include_identify:
        parts.append(
            f"[  {t1}] n71-s3e-p0: ADMIN_IDENTIFY_ONCE "
            "rc=-3 master_seen=1 controller_started=1 ready=1 "
            "submitted=1 completed=1 data_arrived=1 stopped=0 master_off=1"
        )
    if include_shutdown:
        parts.append(
            f"[  {t2}] n71-s3e-p0: ADMIN_SHUTDOWN_TRACE "
            "attempted=1 rc=0 csts=00000009 disable_rc=0 "
            "disable_csts=00000000 inner_rc=0 master_off=1"
        )
    parts.append(
        f"[  {t3}] n71-s3e-p0: ADMIN_POST_STOP_DMA_SNAPSHOT "
        f"dart_fault={dart} nvmmu_fifo={fifo} "
        "hmb_descriptor_zero=1 queues_zero=0 queues_owned_io_va=1 "
        "dart_queues_mapped=1 no_dma_release_attempted=YES "
        "quarantine_unchanged=YES"
    )
    return "\n".join(parts) + "\n"

class N71S3EPoststopArchiveTests(unittest.TestCase):
    def test_complete_quarantined_snapshot(self):
        x = MOD.aggregate([record()])
        self.assertEqual(x["files_examined"], 1)
        self.assertEqual(x["snapshots_found"], 1)
        self.assertEqual(x["unique_event_signatures"], 1)
        self.assertEqual(x["shutdown_consistent_snapshots"], 1)
        self.assertEqual(x["queue_mapping_retained_snapshots"], 1)
        self.assertEqual(x["explicitly_quarantined_snapshots"], 1)
        self.assertEqual(x["raw_nvmmu_fifo_histogram"], {"00000201": 1})
        self.assertEqual(x["raw_dart_fault_histogram"], {"00000500": 1})
        self.assertEqual(x["original_s5l_bit31_irq_branch_asserted_snapshots"], 0)
        self.assertEqual(x["original_s5l_bit31_irq_branch_clear_snapshots"], 1)
        self.assertEqual(x["dart_status_unparseable_snapshots"], 0)
        self.assertFalse(x["bit31_clear_proves_no_pending_dma"])
        self.assertFalse(x["bit31_clear_proves_no_other_dart_fault"])
        for key in ("independent_boot_count_proven", "fifo_bitfield_semantics_proven",
                    "hardware_dma_quiescence_proven", "dma_release_allowed"):
            self.assertIs(x[key], False, key)

    def test_duplicate_saved_capture_not_counted_twice(self):
        log = record()
        x = MOD.aggregate([log, log])
        self.assertEqual(x["files_examined"], 2)
        self.assertEqual(x["snapshots_found"], 2)
        self.assertEqual(x["deduplicated_copies"], 1)
        self.assertEqual(x["unique_event_signatures"], 1)
        self.assertEqual(x["raw_dart_fault_histogram"]["00000500"], 1)

    def test_variation_does_not_infer_fifo_or_dma_semantics(self):
        x = MOD.aggregate([
            record(fifo="00000201"),
            record(fifo="00000701", t1="28.003", t2="28.004", t3="28.005")
        ])
        self.assertEqual(x["raw_nvmmu_fifo_histogram"], {
            "00000201": 1, "00000701": 1
        })
        self.assertEqual(x["raw_dart_fault_histogram"], {"00000500": 2})
        self.assertFalse(x["hardware_dma_quiescence_proven"])
        self.assertFalse(x["fifo_bitfield_semantics_proven"])
        self.assertFalse(x["independent_boot_count_proven"])

    def test_missing_shutdown_has_no_success_claim(self):
        x = MOD.aggregate([record(include_shutdown=False)])
        self.assertEqual(x["shutdown_consistent_snapshots"], 0)
        self.assertEqual(x["explicitly_quarantined_snapshots"], 1)
        self.assertFalse(x["dma_release_allowed"])

    def test_missing_identify_not_quarantined_without_proof(self):
        x = MOD.aggregate([record(include_identify=False)])
        self.assertEqual(x["shutdown_consistent_snapshots"], 1)
        self.assertEqual(x["explicitly_quarantined_snapshots"], 0)

    def test_malformed_raw_register_is_not_a_valid_status(self):
        x = MOD.aggregate([record(fifo="NO_DATA", dart="abcdef0g")])
        self.assertEqual(x["raw_nvmmu_fifo_histogram"], {})
        self.assertEqual(x["raw_dart_fault_histogram"], {})
        self.assertEqual(x["dart_status_unparseable_snapshots"], 1)
        self.assertEqual(x["original_s5l_bit31_irq_branch_asserted_snapshots"], 0)
        self.assertEqual(x["original_s5l_bit31_irq_branch_clear_snapshots"], 0)
        self.assertFalse(x["dma_release_allowed"])

    def test_original_s5l_bit31_branch_and_no_dma_authority(self):
        x = MOD.aggregate([
            record(dart="80000500", t1="11.003", t2="11.004", t3="11.005"),
            record(dart="00000500", t1="22.003", t2="22.004", t3="22.005"),
            record(dart="00000100", t1="33.003", t2="33.004", t3="33.005"),
            record(dart="00000400", t1="44.003", t2="44.004", t3="44.005"),
            record(dart="ffffffff", t1="55.003", t2="55.004", t3="55.005"),
            record(dart="malformed", t1="66.003", t2="66.004", t3="66.005"),
        ])
        self.assertEqual(x["original_s5l_bit31_irq_branch_asserted_snapshots"], 2)
        self.assertEqual(x["original_s5l_bit31_irq_branch_clear_snapshots"], 3)
        self.assertEqual(x["dart_status_unparseable_snapshots"], 1)
        self.assertFalse(x["bit31_clear_proves_no_pending_dma"])
        self.assertFalse(x["bit31_clear_proves_no_other_dart_fault"])
        self.assertFalse(x["dma_release_allowed"])

    def test_cli_omits_identifiers_raw_data_and_paths(self):
        with tempfile.TemporaryDirectory() as t:
            log = Path(t) / "private-source-ECID123456789012.log"
            log.write_text(record(), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(log)],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            data = json.loads(run.stdout)
            self.assertEqual(data["snapshots_found"], 1)
            for forbidden in (str(log), "ECID", "9999999912345678",
                              "PRIVATE_PATH", "DO_NOT_PRINT",
                              "18.003", "18.004", "18.005"):
                self.assertNotIn(forbidden, run.stdout)
            self.assertFalse(data["dma_release_allowed"])

    def test_cli_error_never_discloses_missing_filename(self):
        with tempfile.TemporaryDirectory() as t:
            missing = str(Path(t) / "private-serial-DO_NOT_ECHO.log")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), missing],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(missing, run.stdout + run.stderr)
            self.assertNotIn("DO_NOT_ECHO", run.stdout + run.stderr)

    def test_empty_or_unrecognized_input_does_not_claim_success(self):
        self.assertEqual(MOD.aggregate([""])["snapshots_found"], 0)
        self.assertFalse(MOD.aggregate([""])["dma_release_allowed"])
        with tempfile.TemporaryDirectory() as t:
            empty = Path(t) / "empty"
            empty.write_text("unrelated logs")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(empty)],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(run.returncode, 1)
            self.assertFalse(json.loads(run.stdout)["dma_release_allowed"])

if __name__ == "__main__":
    unittest.main()
