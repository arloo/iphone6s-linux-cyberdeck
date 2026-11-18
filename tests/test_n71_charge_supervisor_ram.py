"""Offline fail-closed checks for N71 RAM charge supervisor event epochs."""
import pathlib
import subprocess
import unittest

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / "scripts/n71_charge_supervisor_ram.sh").read_text()
AWK = SOURCE.split("dmesg | awk '", 1)[1].split("'\n}", 1)[0]

class ChargeSupervisorEpochTests(unittest.TestCase):
    def events(self, data):
        p = subprocess.run(["awk", AWK], input=data, text=True, capture_output=True, check=True)
        return dict(row.split("|", 1) for row in p.stdout.splitlines())

    def test_older_restore_is_not_mistaken_for_new_failure(self):
        e=self.events("""[ 1064.426501] n71-sn2400-trial: RESTORE reason=module-exit input=00 rc=0
[ 1064.550393] n71-sn2400-trial: APPLIED input_uA=300000 original_uA=90000 VBUS_uV=5025000 automatic_restore_ms=3600000
[ 1066.642474] n71-sn2400-trial: MONITOR VBUS_uV=4900000 status=b1 input_uA=300000
""")
        self.assertEqual(e["FAILURE"], "")
        self.assertIn("1064.550393", e["APPLIED"])
        self.assertIn("1066.642474", e["MONITOR"])

    def test_stop_in_active_lease_is_detected(self):
        e=self.events("""[ 1064.550393] n71-sn2400-trial: APPLIED input_uA=300000 original_uA=90000 VBUS_uV=5025000 automatic_restore_ms=3600000
[ 1066.642474] n71-sn2400-trial: MONITOR VBUS_uV=4900000 status=b1 input_uA=300000
[ 1068.000000] n71-sn2400-trial: MONITOR_STOP rc=-34 phase=battery
[ 1068.000001] n71-sn2400-trial: RESTORE reason=monitor-stop input=00 rc=0
""")
        self.assertIn("RESTORE reason=monitor-stop", e["FAILURE"])

    def test_new_applied_resets_previous_fault_and_requires_new_monitor(self):
        e=self.events("""[ 1080.000000] n71-sn2400-trial: APPLIED input_uA=300000 automatic_restore_ms=3600000
[ 1080.000001] n71-sn2400-trial: RESTORE reason=monitor-stop input=00 rc=0
[ 1100.000000] n71-sn2400-trial: APPLIED input_uA=300000 automatic_restore_ms=3600000
""")
        self.assertEqual(e["FAILURE"], "")
        self.assertEqual(e["MONITOR"], "")

if __name__ == "__main__":
    unittest.main()
