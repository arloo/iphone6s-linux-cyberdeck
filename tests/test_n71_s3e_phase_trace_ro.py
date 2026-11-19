"""Source contracts: inert per-phase INTMS/PERST telemetry cannot authorize DMA release."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT/"experimental/port0/n71_s3e_p0_asserted_reset_rootstart.c"
HEADER=ROOT/"experimental/port0/n71_s3e_admin_identify_once.h"

class PhaseTraceTests(unittest.TestCase):
    def test_option_is_readonly_optin_and_incompatible_with_queue_retirement(self):
        source=OWNER.read_text()
        self.assertIn("static bool ans_phase_trace_ro;",source)
        self.assertIn("module_param(ans_phase_trace_ro, bool, 0400);",source)
        begin=source.index("static int __init n71_port0_init(void)")
        end=source.index("n71_p0=of_find_node_by_path",begin)
        early=source[begin:end]
        self.assertIn("if (ans_phase_trace_ro && (!ans_identify_once || ans_queue_retire_probe))",early)
        self.assertIn("return -EPERM;",early)
        self.assertLess(early.index("if (ans_phase_trace_ro"),early.index("if (!n71_board_gate())"))
        for forbidden in ("writel(", "writew(", "gpiod_direction_output("):
            self.assertNotIn(forbidden,early)

    def test_cc_trace_performs_only_original_cc_write(self):
        source=HEADER.read_text()
        begin=source.index("static void n71_admin_cc(")
        end=source.index("static unsigned int n71_admin_csts(",begin)
        block=source[begin:end]
        self.assertEqual(block.count("n71_admin_write(0x14,value);"),1)
        self.assertEqual(block.count("n71_admin_reg(0x0c)&1"),2)
        self.assertEqual(block.count("n71_storage_reset_level(ctx)==1"),2)
        self.assertEqual(block.count("if (ans_phase_trace_ro)"),2)
        for tag in ("enable", "shutdown", "disable", "edge=before", "edge=after", "no_dma_release=YES"):
            self.assertIn(tag,block)
        for forbidden in ("n71_admin_write(0x0c,", "n71_admin_write(0x24,",
                          "n71_admin_write(0x28,", "writel(", "writew(",
                          "dma_unmap_single(", "free_page("):
            self.assertNotIn(forbidden,block)

    def test_post_core_trace_stays_readonly_and_quarantined(self):
        source=HEADER.read_text()
        start=source.index('if (ans_phase_trace_ro)\n                    pr_info("n71-s3e-p0: ADMIN_POST_CORE_RO')
        end=source.index('pr_info("n71-s3e-p0: ADMIN_POST_STOP_DMA_SNAPSHOT',start)
        section=source[start:end]
        for part in ("intms_bit0=%u","reset_low=%u","hmb_descriptor_zero=%u",
                     "queues_owned=%u","no_dma_release=YES",
                     "n71_storage_reset_level(ctx)==0","n71_admin_reg(0x0c)&1"):
            self.assertIn(part,section)
        for forbidden in ("n71_admin_write(", "writel(", "writew(",
                          "gpiod_direction_output(", "dma_unmap_single(",
                          "free_page("):
            self.assertNotIn(forbidden,section)

    def test_existing_safety_gate_unchanged(self):
        q=(ROOT/"experimental/port0/n71_s3e_queue_retire_gate.h").read_text()
        self.assertIn("v->reset_low == 1",q)
        self.assertIn("(v->intms & 1)",q)
        header=HEADER.read_text()
        start=header.index("if (ans_queue_retire_probe) {")
        self.assertIn("rc=-3;",header[start:start+180])
        self.assertIn("ADMIN_POST_DISABLE_PREDICATES",header)

if __name__ == "__main__":
    unittest.main()
