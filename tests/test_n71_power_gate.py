"""Fully synthetic tests for the N71 touch regulator/clock recovery gate."""
import importlib.util
import unittest
from dataclasses import replace
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools/touch/n71_power_gate.py"
SPEC = importlib.util.spec_from_file_location("n71_power_gate", SOURCE)
GATE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


class N71PowerGateTests(unittest.TestCase):
    def setUp(self):
        self.before = GATE.Snapshot(0x800002EE, 0x0F, 0x01, 1)
        self.during = GATE.Snapshot(0x000802DC, 0x1F, 0x01, 0)
        self.after = self.before

    def check_rejected(self, before=None, during=None, after=None, expected=""):
        result = GATE.audit(
            self.before if before is None else before,
            self.during if during is None else during,
            self.after if after is None else after,
        )
        self.assertTrue(result)
        self.assertTrue(any(expected in s for s in result), result)

    def test_valid_synthetic_roundtrip(self):
        self.assertEqual(GATE.audit(self.before, self.during, self.after), [])

    def test_missing_gpio_reset_readback_blocks_pass(self):
        self.check_rejected(after=replace(self.after, reset_level=None),
                            expected="reset GPIO")

    def test_reset_not_restored(self):
        self.check_rejected(after=replace(self.after, reset_level=0),
                            expected="reset GPIO")

    def test_clock_unknown_bits_rejected(self):
        self.check_rejected(during=replace(self.during, clock=0x001802DC),
                            expected="unknown bits")

    def test_clock_stuck_busy_rejected(self):
        self.check_rejected(during=replace(self.during, clock=0x000C02DC),
                            expected="busy")

    def test_clock_baseline_mismatch_rejected(self):
        self.check_rejected(before=replace(self.before, clock=0x000002EE),
                            expected="historical disabled baseline")

    def test_analog_regulator_modified_other_bits(self):
        self.check_rejected(during=replace(self.during, analog=0x1E),
                            expected="beyond expected")

    def test_analog_not_restored_rejected(self):
        self.check_rejected(after=replace(self.after, analog=0x1F),
                            expected="not restored")

    def test_clock_not_restored_rejected(self):
        self.check_rejected(after=replace(self.after, clock=self.during.clock),
                            expected="not restored")

    def test_core_enable_bit_absent_rejected(self):
        self.check_rejected(before=replace(self.before, core=0x00),
                            expected="core regulator enable bit")

    def test_core_changed_during_active_state_rejected(self):
        self.check_rejected(during=replace(self.during, core=0x03),
                            expected="changed unexpectedly")

    def test_reference_clock_divider_invalid(self):
        self.check_rejected(during=replace(self.during, clock=0x00080001),
                            expected="implausible")

    def test_out_of_range_raw_register_rejected(self):
        self.check_rejected(before=replace(self.before, analog=0x100),
                            expected="8-bit")


if __name__ == "__main__":
    unittest.main()
