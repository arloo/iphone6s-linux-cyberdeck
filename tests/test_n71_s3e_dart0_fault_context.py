# SPDX-License-Identifier: MIT
"""S8000 DART0 post-stop fault-context observer: offline safety contracts.

A first-generation register-layout hypothesis is NOT proof of S8000 layout,
transaction drain, or attribution. Never read physical device MMIO in tests.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "experimental/port0/n71_s3e_admin_identify_once.h").read_text()

class Dart0PoststopContextTests(unittest.TestCase):
    def test_guarded_after_controller_shutdown_and_bus_master_off(self):
        start = SOURCE.index("if (r.master_off && !r.disable_rc) {")
        stop = SOURCE.index("pr_info(\"n71-s3e-p0: ADMIN_STAGE", start)
        snippet = SOURCE[start:stop]
        self.assertIn("if (r.master_off && !r.disable_rc) {", snippet)
        self.assertIn("if (ans_phase_trace_ro && r.controller_stop_observed &&", snippet)
        self.assertIn("n71_admin_memory.dart_mapped && dart_fault)", snippet)
        self.assertGreater(snippet.index("ADMIN_DART0_FAULT_CONTEXT_RO"),
                           snippet.index("ADMIN_POST_STOP_DMA_SNAPSHOT"))
        self.assertIn("s8000_v0_layout_unverified=YES", snippet)
        self.assertIn("fault_not_dma_fence=YES", snippet)
        self.assertIn("quarantine_unchanged=YES", snippet)

    def test_explicit_register_offsets_and_redaction(self):
        a = SOURCE.index("/* Opt-in, read-only fault-context hypothesis")
        b = SOURCE.index("raw_context_redacted=YES", a)
        observer = SOURCE[a:b]
        for off in ("+0x14", "+0x18", "+0x1c"):
            self.assertIn("readl((u8 __iomem *)m->dart" + off + ")", observer)
        self.assertIn("!!(dart_fault & BIT(8))", SOURCE)
        self.assertIn("!!(dart_fault & BIT(10))", SOURCE)
        self.assertIn("!!fault_address", SOURCE)
        for forbidden in ("writel(", "writew(", "dma_unmap_", "free_page(",
                          "n71_admin_write(", "n71_admin_dart_map("):
            self.assertNotIn(forbidden, observer)
        for raw in ("axi0=%08x", "axi1=%08x", "fault_address=%08x",
                    "addr=%08x", "dart_error_address=%x"):
            self.assertNotIn(raw, observer)

    def test_status_flags_dont_imply_dma_completion(self):
        self.assertIn("fault_not_dma_fence=YES", SOURCE)
        self.assertIn("dma_quiescence_proven=NO", SOURCE)
        self.assertIn("if (rc==-3) return -3;", SOURCE)
        self.assertIn("if (n71_admin_unprepare(ctx)) return -3;", SOURCE)

if __name__ == "__main__":
    unittest.main()
