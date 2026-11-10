"""Offline contract tests for the S8000 touch reference-clock rollback settle fix."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/0004-n71-touch-clock-bounded-restore-settle-rfc.patch"
IDLE = 0x800002EE
ACTIVE = 0x000802DC
BUSY = 1 << 18


def settle_trace(values, limit=5000):
    """Synthetic bounded polling model; never accesses hardware."""
    for index, value in enumerate(values[:limit], 1):
        if value == IDLE and not (value & BUSY):
            return ("PASS", index)
    return ("TIMEOUT", min(len(values), limit))


class N71ClockRestoreSettleTests(unittest.TestCase):
    def test_delayed_register_restore_eventually_succeeds(self):
        self.assertEqual(settle_trace([ACTIVE, ACTIVE, IDLE]), ("PASS", 3))

    def test_immediate_restore_succeeds(self):
        self.assertEqual(settle_trace([IDLE]), ("PASS", 1))

    def test_permanent_active_value_does_not_falsely_pass(self):
        self.assertEqual(settle_trace([ACTIVE] * 5000), ("TIMEOUT", 5000))

    def test_correct_bits_not_enough_if_value_is_not_exact(self):
        self.assertEqual(settle_trace([IDLE ^ 1] * 10), ("TIMEOUT", 10))

    def test_poll_limit_prevents_unbounded_retry(self):
        self.assertEqual(settle_trace([ACTIVE] * 5000 + [IDLE]), ("TIMEOUT", 5000))

    def test_patch_changes_only_touch_clock_source(self):
        diff = PATCH.read_text()
        self.assertEqual(
            [line for line in diff.splitlines() if line.startswith("diff --git ")],
            ["diff --git a/drivers/clk/clk-apple-touch.c "
             "b/drivers/clk/clk-apple-touch.c"],
        )

    def test_both_error_and_normal_disable_paths_poll_exact_baseline(self):
        diff = PATCH.read_text()
        added = "\n".join(
            line[1:] for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        self.assertGreaterEqual(added.count("regmap_read_poll_timeout_atomic("), 2)
        self.assertGreaterEqual(added.count("readback == tc->saved_reg"), 2)
        self.assertGreaterEqual(added.count("!(readback & TOUCH_CLK_BUSY)"), 2)
        self.assertGreaterEqual(added.count("10, 50000"), 2)

    def test_fail_closed_saves_baseline_until_recovery(self):
        diff = PATCH.read_text()
        self.assertIn('touch clock baseline restore did not settle', diff)
        self.assertIn('touch clock enable rollback failed', diff)
        self.assertNotIn('+\\ttc->saved_valid = false;', diff)


if __name__ == "__main__":
    unittest.main()
