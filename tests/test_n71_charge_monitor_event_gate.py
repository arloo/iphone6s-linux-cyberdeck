import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from n71_charge_monitor_event_gate import verify_active_charge_monitor as check

class ChargeMonitorGateTests(unittest.TestCase):
    good = "[ 100.000000] n71-sn2400-trial: MONITOR VBUS_uV=4775000 status=b1 input_uA=500000"
    def test_fresh_monitor(self):
        self.assertEqual(check(self.good, 102), 2)
    def test_loaded_module_with_stopped_monitor_is_refused(self):
        for message in ("MONITOR_STOP rc=-34 VBUS_uV=0", "RESTORE reason=monitor-stop input=00 rc=0", "ROLLBACK_FAILED module retained for cleanup"):
            with self.subTest(message=message), self.assertRaises(RuntimeError):
                check(self.good + "\n[101] n71-sn2400-trial: " + message, 102)
    def test_stale_or_missing_telemetry_is_refused(self):
        for value, now in ((self.good, 110), (self.good, 98), ("", 102)):
            with self.subTest(value=value, now=now), self.assertRaises(RuntimeError):
                check(value, now)
    def test_wrong_input_or_voltage_is_refused(self):
        for changed in (self.good.replace("500000", "300000"), self.good.replace("4775000", "4300000"), self.good.replace("4775000", "5600000")):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                check(changed, 102)
    def test_fresh_apply_after_old_stop(self):
        text = "[99] n71-sn2400-trial: RESTORE reason=monitor-stop input=00 rc=0\n[100] n71-sn2400-trial: APPLIED input_uA=500000 original_uA=90000 VBUS_uV=4775000 automatic_restore_ms=3600000"
        self.assertEqual(check(text, 100.2), 100.2-100)
if __name__ == "__main__":
    unittest.main()
