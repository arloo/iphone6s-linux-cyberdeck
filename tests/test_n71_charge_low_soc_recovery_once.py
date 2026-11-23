# SPDX-License-Identifier: MIT
"""No-hardware tests for the owner-only low-SOC charging rescue policy.

The tested script is rewritten to temporary fake /sys /proc /usr /run.
All device/module operations are simulated; no SSH, I2C, MMIO or phone is used.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/n71_charge_low_soc_recovery_once.sh").read_text()
SHA = "06b497deb2baf3724fe3d03f72870df2910d40b27afd71e176df52f2358aafea"


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="n71-charge-recovery-synth-")
        self.root = Path(self.tmp.name)
        for folder in ("sys/class/power_supply/bq27540-0",
                       "sys/module/n71_sn2400_input_trial/parameters",
                       "sys/class/udc/20c100000.usbdev",
                       "proc/device-tree", "run", "usr/lib/cyberdeck",
                       "usr/bin", "bin"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        p = self.root / "sys/class/power_supply/bq27540-0"
        for key, value in {"capacity": "23", "temp": "325",
                           "voltage_now": "3613000", "health": "Good",
                           "current_now": "-229000"}.items():
            (p / key).write_text(value + "\n")
        q = self.root / "sys/module/n71_sn2400_input_trial/parameters"
        for key, value in {"armed": "Y", "input_ua": "300000",
                           "lease_seconds": "3600"}.items():
            (q / key).write_text(value + "\n")
        (self.root / "sys/class/udc/20c100000.usbdev/state").write_text("configured\n")
        (self.root / "proc/device-tree/compatible").write_bytes(b"apple,n71\0apple,s8000\0")
        (self.root / "proc/modules").write_text("n71_sn2400_input_trial 49152 0 - Live 0x0\n")
        (self.root / "usr/lib/cyberdeck/n71-sn2400-input-trial.ko").write_bytes(b"SIMULATED-NONMODULE\n")
        self.logs = self.root / "dmesg"
        self.logs.write_text("[ 3603.36] n71-sn2400-trial: RESTORE reason=lease-expired input=00 rc=0\n")
        for name, code in {
            "id": '#!/bin/sh\necho 0\n',
            "uname": '#!/bin/sh\necho 7.3.0-rc1-n71-batt2-g68aadac820d0-dirty\n',
            "sha256sum": '#!/bin/sh\necho "' + SHA + '  SIM"\n',
            "dmesg": '#!/bin/sh\ncat "$SIM_ROOT/dmesg"\n',
            "sleep": '#!/bin/sh\nexit 0\n',
            "rmmod": '''#!/bin/sh
set -eu
test "$1" = n71_sn2400_input_trial
if test -e "$SIM_ROOT/sys/module/n71_sn2400_input_trial/parameters/lease_seconds" &&
   test "$(cat "$SIM_ROOT/sys/module/n71_sn2400_input_trial/parameters/lease_seconds")" = 600; then
    echo "[ 3999.00] n71-sn2400-trial: RESTORE reason=module-exit input=00 rc=0" >> "$SIM_ROOT/dmesg"
fi
rm -rf "$SIM_ROOT/sys/module/n71_sn2400_input_trial/parameters"
printf '' > "$SIM_ROOT/proc/modules"
''',
        }.items():
            path = self.root / "bin" / name
            path.write_text(code)
            path.chmod(0o700)
        loader = self.root / "usr/bin/n71-module-once"
        loader.write_text('''#!/bin/sh
set -eu
test "$2" = 'armed=1 input_ua=300000 lease_seconds=600'
mkdir -p "$SIM_ROOT/sys/module/n71_sn2400_input_trial/parameters"
p="$SIM_ROOT/sys/module/n71_sn2400_input_trial/parameters"
echo Y > "$p/armed"
echo 300000 > "$p/input_ua"
echo 600 > "$p/lease_seconds"
echo 'n71_sn2400_input_trial 49152 0 - Live 0x0' > "$SIM_ROOT/proc/modules"
echo '[ 3603.37] n71-sn2400-trial: APPLIED input_uA=300000 original_uA=90000 VBUS_uV=4900000 automatic_restore_ms=600000' >> "$SIM_ROOT/dmesg"
echo '[ 3605.37] n71-sn2400-trial: MONITOR VBUS_uV=4900000 status=b1 input_uA=300000' >> "$SIM_ROOT/dmesg"
''')
        loader.chmod(0o700)
        transformed = SOURCE
        for path in ("/usr", "/sys", "/proc", "/run"):
            transformed = transformed.replace(path, str(self.root) + path)
        # Accelerate only the synthetic exercise; keep real lease untouched.
        transformed = transformed.replace('while [ "$n" -lt 270 ]', 'while [ "$n" -lt 4 ]')
        self.script = self.root / "simulated.sh"
        self.script.write_text(transformed)
        self.env = dict(os.environ, SIM_ROOT=str(self.root),
                        PATH=str(self.root / "bin") + ":" + os.environ["PATH"],
                        N71_HOST_USB_CONFIG_MAX_MA="500")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, mode="--check", *, env=None):
        return subprocess.run(["sh", str(self.script), mode],
                              env=env or self.env, capture_output=True,
                              text=True, timeout=20)

    def test_read_only_check_passes_expected_23pct(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_RECOVERY_PREFLIGHT_PASS", result.stdout)
        self.assertIn("lease-expired input=00 rc=0", self.logs.read_text())
        self.assertEqual((self.root / "sys/module/n71_sn2400_input_trial/parameters/lease_seconds").read_text().strip(), "3600")

    def test_policy_denies_unverified_source(self):
        env = dict(self.env)
        env.pop("N71_HOST_USB_CONFIG_MAX_MA")
        self.assertNotEqual(self.run_script(env=env).returncode, 0)

    def test_rejects_critical_temperature_soc_voltage_and_bad_health(self):
        p = self.root / "sys/class/power_supply/bq27540-0"
        for key, bad in (("capacity", "19"), ("capacity", "35"),
                         ("temp", "375"), ("voltage_now", "3499999"),
                         ("voltage_now", "4150000"), ("health", "Unknown")):
            with self.subTest(key=key, bad=bad):
                f = p / key
                old = f.read_text()
                f.write_text(bad + "\n")
                self.assertNotEqual(self.run_script().returncode, 0)
                f.write_text(old)

    def test_rejects_wrong_usb_module_or_failed_old_rollback(self):
        f = self.root / "sys/class/udc/20c100000.usbdev/state"
        f.write_text("not attached\n")
        self.assertNotEqual(self.run_script().returncode, 0)
        f.write_text("configured\n")
        self.logs.write_text("[ 3603.36] n71-sn2400-trial: ROLLBACK_FAILED\n")
        self.assertNotEqual(self.run_script().returncode, 0)
        self.logs.write_text("[ 3603.36] n71-sn2400-trial: RESTORE reason=lease-expired input=00 rc=0\n")
        f = self.root / "proc/modules"
        f.write_text(f.read_text() + "n71_s3e_p0 999 0 - Live 0x0\n")
        self.assertNotEqual(self.run_script().returncode, 0)

    def test_bounded_run_unloads_and_restores_without_storage(self):
        result = self.run_script("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("N71_RECOVERY_300MA_ARMED", result.stdout)
        self.assertIn("N71_RECOVERY_BASELINE_RESTORED=PASS", result.stdout)
        self.assertFalse((self.root / "proc/modules").read_text())
        self.assertIn("RESTORE reason=module-exit input=00 rc=0", self.logs.read_text())
        self.assertIn("lease_seconds=600", SOURCE)
        self.assertIn("TEMP_TRIP_TENTHS=375", SOURCE)
        self.assertNotIn("input_ua=500000", SOURCE)
        self.assertNotIn("dd if=", SOURCE)
        self.assertNotIn("mkfs.", SOURCE)

if __name__ == "__main__":
    unittest.main()
