"""Offline fail-closed verification for opt-in 500 mA RAM supervisor."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=(ROOT/"scripts/n71_charge_supervisor_ram.sh").read_text()
HIGH=(ROOT/"scripts/n71_charge_supervisor_500ma_ram.sh").read_text()

class FastChargeProfileContract(unittest.TestCase):
    def test_default_300ma_still_untouched(self):
        self.assertIn("INPUT_UA=300000",BASE)
        self.assertIn("input_ua=300000 lease_seconds=3600",BASE)
        self.assertIn("MAX_RENEW_VOLTAGE_UV=4180000",BASE)

    def test_500ma_is_separate_optin_and_requires_verified_source(self):
        self.assertIn("INPUT_UA=500000",HIGH)
        self.assertIn("input_ua=500000 lease_seconds=3600",HIGH)
        self.assertNotIn("input_ua=300000",HIGH)
        self.assertNotIn("input_uA=300000",HIGH)
        self.assertIn("/run/n71-owner-verified-500ma-source",HIGH)
        self.assertIn("N71_500MA_USB_SOURCE_OWNER_VERIFIED",HIGH)
        self.assertIn("600 0",HIGH)

    def test_charger_safety_gates_unchanged(self):
        for value in (
            "MIN_RENEW_CAPACITY=35", "MAX_RENEW_VOLTAGE_UV=4180000",
            "LEASE_SECONDS=3600", "REFRESH_AT_AGE=2400",
            "verify_immutable", "verify_battery", "verify_monitor",
            "rmmod n71_sn2400_input_trial",
            "RESTORE reason=module-exit input=00 rc=0",
            "flock -n 9", "USB lost before rearm",
            "monitor telemetry stale", "input mismatch",
        ):
            self.assertIn(value,HIGH)

    def test_log_epoch_parser_ignores_old_lease_failure(self):
        awk=HIGH.split("dmesg | awk '",1)[1].split("'\n}",1)[0]
        logs="""[ 1040.000000] n71-sn2400-trial: RESTORE reason=monitor-stop input=00 rc=0
[ 1044.000000] n71-sn2400-trial: APPLIED input_uA=500000 original_uA=90000 VBUS_uV=4900000 automatic_restore_ms=3600000
[ 1046.000000] n71-sn2400-trial: MONITOR VBUS_uV=4800000 status=b1 input_uA=500000
"""
        p=subprocess.run(["awk",awk],input=logs,text=True,capture_output=True,check=True)
        fields=dict(row.split("|",1) for row in p.stdout.splitlines())
        self.assertIn("input_uA=500000",fields["APPLIED"])
        self.assertIn("input_uA=500000",fields["MONITOR"])
        self.assertEqual(fields["FAILURE"], "")

    def test_shell_syntax(self):
        p=subprocess.run(["sh","-n",str(ROOT/"scripts/n71_charge_supervisor_500ma_ram.sh")],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
