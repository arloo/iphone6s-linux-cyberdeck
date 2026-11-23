# SPDX-License-Identifier: MIT
"""Simulated follow-on 300mA charge bridge, never touches a device."""
from pathlib import Path
import unittest
from test_n71_charge_low_soc_recovery_once import RecoveryTests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/n71_charge_low_soc_bridge_38c_once.sh").read_text()


class LowSOCFollowonTests(unittest.TestCase):
    def setUp(self):
        self.fx = RecoveryTests(methodName="test_read_only_check_passes_expected_23pct")
        self.fx.setUp()
        root = self.fx.root
        (root / "sys/class/power_supply/bq27540-0/capacity").write_text("34\n")
        (root / "proc/modules").write_text("")
        (root / "dmesg").write_text(
            "[ 7601.93] n71-sn2400-trial: RESTORE reason=module-exit input=00 rc=0\n")
        t = SOURCE
        for path in ("/usr", "/sys", "/proc", "/run"):
            t = t.replace(path, str(root) + path)
        t = t.replace('while [ "$n" -lt 270 ]',
                      'while [ "$n" -lt 4 ]')
        self.fx.script.write_text(t)

    def tearDown(self):
        self.fx.tearDown()

    def test_realistic_gauge_fallback_and_full_synthetic_cycle(self):
        result = self.fx.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_LOW_SOC_BRIDGE_PREFLIGHT_PASS", result.stdout)
        result = self.fx.run_script("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_LOW_SOC_BRIDGE_300MA_ARMED lease_seconds=600", result.stdout)
        self.assertIn("N71_RECOVERY_BASELINE_RESTORED=PASS", result.stdout)
        self.assertEqual((self.fx.root / "proc/modules").read_text(), "")

    def test_trips_at_37point5_and_rejects_out_of_window(self):
        f = self.fx.root / "sys/class/power_supply/bq27540-0"
        for key, bad in (("capacity", "19"), ("capacity", "37"),
                         ("temp", "375"), ("voltage_now", "3499999")):
            with self.subTest(key=key, bad=bad):
                x = f / key
                old = x.read_text()
                x.write_text(bad + "\n")
                self.assertNotEqual(self.fx.run_script().returncode, 0)
                x.write_text(old)
        self.assertIn("TEMP_TRIP_TENTHS=375", SOURCE)
        self.assertIn("LEASE_SECONDS=600", SOURCE)
        self.assertIn("MIN_CAPACITY=20", SOURCE)
        self.assertIn("MAX_CAPACITY=36", SOURCE)

if __name__ == "__main__":
    unittest.main()
