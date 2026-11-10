"""Regression checks for the upstream-targeted N71 touch rollback RFC patch.

These are **source-contract checks only**, not proof of hardware behavior.
"""
from pathlib import Path
import re
import unittest


PATCH = (
    Path(__file__).resolve().parents[1]
    / "patches/0001-n71-z2-rollback-and-touch-ref-clock-rfc.patch"
)


class N71RollbackPatchContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PATCH.read_text()
        cls.additions = "\n".join(
            line[1:] for line in cls.text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def test_patch_touches_only_expected_driver_files(self):
        touched = re.findall(r"^diff --git a/(\S+)", self.text, re.M)
        self.assertEqual(
            sorted(touched),
            ["drivers/clk/clk-apple-touch.c",
             "drivers/input/touchscreen/apple_z2.c"],
        )

    def test_first_hbpp_handshake_routes_to_power_cleanup(self):
        self.assertIn("\t\tgoto err_power_off;", self.additions)
        self.assertIn("apple_z2_hbpp_probe(z2, NULL)", self.text)

    def test_shared_hbpp_cleanup_resets_power(self):
        for item in ("err_power_off:", "apple_z2_power_off(z2);",
                     "z2->booted = false;"):
            self.assertIn(item, self.additions)
        self.assertIn("return error;", self.text)

    def test_no_early_error_return_after_first_hbpp(self):
        self.assertIn("-\t\treturn error;", self.text)

    def test_clock_preserves_original_raw_value(self):
        for item in ("tc->saved_reg = val;", "tc->saved_valid = true;",
                     "regmap_write(tc->map, tc->reg, tc->saved_reg)"):
            self.assertIn(item, self.additions)

    def test_clock_restore_checks_readback(self):
        self.assertGreaterEqual(self.additions.count("readback != tc->saved_reg"), 2)

    def test_clock_enable_failed_rollback_is_fail_closed(self):
        self.assertIn("if (restore_ret) {", self.additions)
        self.assertIn("return restore_ret;", self.additions)

    def test_clock_unknown_bits_fail_closed(self):
        self.assertIn("(val & ~TOUCH_CLK_KNOWN)", self.additions)


if __name__ == "__main__":
    unittest.main()
