# SPDX-License-Identifier: MIT
"""No-hardware checks for the 35%+ 38C-capped charger supervisor."""
from pathlib import Path
import shutil
import unittest

from test_n71_charge_low_soc_recovery_once import RecoveryTests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/n71_charge_standard_38c_once.sh").read_text()


class StandardThirtyEightDegreeTests(unittest.TestCase):
    def setUp(self):
        self.fx = RecoveryTests(methodName="test_read_only_check_passes_expected_23pct")
        self.fx.setUp()
        root = self.fx.root
        (root / "sys/class/power_supply/bq27540-0/capacity").write_text("35\n")
        (root / "proc/modules").write_text("")
        shutil.rmtree(root / "sys/module/n71_sn2400_input_trial/parameters")
        (root / "dmesg").write_text(
            "[ 7601.930311] n71-sn2400-trial: RESTORE reason=module-exit input=00 rc=0\n")
        loader = root / "usr/bin/n71-module-once"
        t = loader.read_text().replace("lease_seconds=600", "lease_seconds=3600")
        t = t.replace("automatic_restore_ms=600000", "automatic_restore_ms=3600000")
        t = t.replace("echo 600 >", "echo 3600 >")
        loader.write_text(t)
        rm = root / "bin/rmmod"
        rm.write_text(rm.read_text().replace("= 600", "= 3600"))
        t = SOURCE
        for path in ("/usr", "/sys", "/proc", "/run"):
            t = t.replace(path, str(root) + path)
        t = t.replace('while [ "$n" -lt 1770 ]',
                      'while [ "$n" -lt 4 ]')
        self.fx.script.write_text(t)

    def tearDown(self):
        self.fx.tearDown()

    def test_preflight_and_early_hardware_restore(self):
        result = self.fx.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_STANDARD_CHARGE_PREFLIGHT_PASS", result.stdout)
        result = self.fx.run_script("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_STANDARD_300MA_ARMED lease_seconds=3600", result.stdout)
        self.assertIn("N71_RECOVERY_BASELINE_RESTORED=PASS", result.stdout)
        self.assertEqual((self.fx.root / "proc/modules").read_text(), "")

    def test_minimum_35pct_and_37point5_temp(self):
        root = self.fx.root
        for metric, bad in (("capacity", "34"), ("temp", "375"),
                            ("voltage_now", "4150000")):
            with self.subTest(metric=metric, bad=bad):
                f = root / "sys/class/power_supply/bq27540-0" / metric
                old = f.read_text()
                f.write_text(bad + "\n")
                self.assertNotEqual(self.fx.run_script().returncode, 0)
                f.write_text(old)

    def test_exact_300ma_and_no_internal_storage_touch(self):
        self.assertIn("LEASE_SECONDS=3600", SOURCE)
        self.assertIn("TEMP_TRIP_TENTHS=375", SOURCE)
        self.assertIn("MIN_CAPACITY=35", SOURCE)
        self.assertIn("REQUIRED_INPUT_UA=300000", SOURCE)
        self.assertIn("another charging supervisor holds lock", SOURCE)
        self.assertNotIn("input_ua=500000", SOURCE)
        self.assertNotIn("n71_s3e_p0.ko", SOURCE)
        self.assertNotIn("mkfs.", SOURCE)
        self.assertNotIn("dd if=", SOURCE)

if __name__ == "__main__":
    unittest.main()
