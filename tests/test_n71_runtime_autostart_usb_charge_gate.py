# SPDX-License-Identifier: MIT
"""Execute a path-isolated boot script with mocked sysfs and shell commands.

Never interacts with a real USB controller, charger, PMIC or device. The
untouched production script has fixed root-owned paths and SHA256 checks.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'scripts/n71_runtime_autostart.sh').read_text()


class N71RAMBootChargerRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='n71-boot-charge-mock-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.bat = self.root / 'battery'
        self.bat.mkdir()
        for k, v in {'capacity': '90', 'voltage_now': '4050000',
                     'temp': '310', 'health': 'Good'}.items():
            (self.bat / k).write_text(v+'\n')
        (self.root/'board').write_bytes(b'apple,n71\0apple,s8000\0')
        (self.root/'udc').write_text('configured\n')
        (self.root/'uptime').write_text('70.000 60.000\n')
        (self.root/'modules').write_text('')
        (self.root/'loads').write_text('')
        self.env = {**os.environ, 'PATH': str(self.bin) + ':' + os.environ['PATH'],
                    'MOCK_LOADS': str(self.root/'loads'),
                    'MOCK_UDC': str(self.root/'udc'),
                    'MOCK_UDC_COUNT': str(self.root/'udc-count')}
        self._make('uname', 'echo 7.3.0-rc1-n71-batt2-test')
        self._make('dmesg', 'echo "BCM4350C5 (003.006.007) build 0825"')
        self._make('sha256sum', 'echo "mocked fixture: OK"')
        self._make('sleep', ':')
        self._make('nohup', 'exec "$@"')
        self._make('setsid', 'exec "$@"')
        for f in ('module-once','hci-probe','battery-status'):
            self._make(f, 'echo "$0 $*" >> "$MOCK_LOADS"')
        updates = {
            '/proc/device-tree/compatible': str(self.root/'board'),
            '/run/n71_runtime_attempted': str(self.root/'attempted'),
            '/run/n71_charge_worker_started': str(self.root/'worker-attempted'),
            '/usr/lib/cyberdeck/n71-runtime.sha256': str(self.root/'hashes'),
            '/usr/lib/cyberdeck/n71-charge-two-hour': str(self.root/'two-hour-profile'),
            '/run/n71_runtime_hashes.log': str(self.root/'hashes.log'),
            '/run/n71_charge_hashes.log': str(self.root/'charge-hashes.log'),
            '/run/n71_charge_monitor.log': str(self.root/'charge-monitor.log'),
            '/sys/class/udc/20c100000.usbdev/state': str(self.root/'udc'),
            '/sys/class/power_supply/bq27540-0': str(self.bat),
            '/sys/class/bluetooth/hci0': str(self.root/'hci'),
            '/proc/uptime': str(self.root/'uptime'),
            '/proc/modules': str(self.root/'modules'),
            '/usr/bin/n71-module-once': str(self.bin/'module-once'),
            '/usr/bin/n71-hci-probe': str(self.bin/'hci-probe'),
            '/usr/bin/n71-battery-status': str(self.bin/'battery-status'),
            '/usr/bin/n71-runtime-autostart': str(self.root/'worker-binary'),
            '/usr/bin/nohup': str(self.bin/'nohup'),
            '/usr/bin/setsid': str(self.bin/'setsid'),
        }
        self.script = SOURCE
        for old,new in updates.items():
            self.assertIn(old, self.script)
            self.script = self.script.replace(old,new)
        # Mock the detached child launch for deterministic, host-only checks.
        spawn='/usr/bin/nohup /usr/bin/setsid /bin/sh /usr/bin/n71-runtime-autostart --charge-worker \\'
        # Replacement of the absolute executable path happened above.
        spawn=spawn.replace('/usr/bin/n71-runtime-autostart', str(self.root/'worker-binary'))
        spawn=spawn.replace('/usr/bin/nohup', str(self.bin/'nohup'))
        spawn=spawn.replace('/usr/bin/setsid', str(self.bin/'setsid'))
        # The production script still contains an actual detached launch.
        original=spawn+'\n    > '+str(self.root/'charge-monitor.log')+' 2>&1 < /dev/null &'
        assert original in self.script, 'Charge worker launch must remain explicit'
        self.script=self.script.replace(original, 'echo CHARGER_WORKER_LAUNCH_REQUESTED >> "$MOCK_LOADS"')
        (self.root/'hci').mkdir()
        self.mock = self.root/'n71-runtime-mock.sh'
        self.mock.write_text(self.script)

    def _make(self, name, body):
        p = self.bin/name
        p.write_text('#!/bin/sh\n'+body+'\n')
        p.chmod(0o755)

    def run_boot(self):
        # Delayed power worker isolated from the real /init process.
        (self.root/'attempted').touch(exist_ok=True)
        result = subprocess.run(['/bin/sh',str(self.mock),'--charge-worker'],
                                env=self.env, capture_output=True, text=True, timeout=5)
        return result, (self.root/'loads').read_text()

    def run_init(self):
        result = subprocess.run(['/bin/sh',str(self.mock)], env=self.env,
                                capture_output=True, text=True, timeout=5)
        return result, (self.root/'loads').read_text()

    def test_post_usb_stability_and_eligible_window_charge_once(self):
        result, calls = self.run_boot()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('USB_POST_ENUMERATION_STABILITY_CONFIRMED',result.stdout)
        self.assertIn('N71_SAFE_CHARGE_WINDOW_CONFIRMED',result.stdout)
        self.assertIn('CHARGER_LOAD_RC=0',result.stdout)
        self.assertEqual(calls.count('n71-sn2400-input-trial.ko'),1)
        self.assertIn('input_ua=300000 lease_seconds=3600',calls)

    def test_full_battery_above_4150000_never_arms(self):
        (self.bat/'capacity').write_text('100\n')
        (self.bat/'voltage_now').write_text('4228000\n')
        result, calls = self.run_boot()
        self.assertEqual(result.returncode,0)
        self.assertIn('HIGH_SOC_WINDOW_TIMEOUT_SKIP_CHARGER',result.stdout)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_thermal_or_low_capacity_refuses_charger(self):
        for field,val in [('temp','375'),('capacity','34'),('health','Unknown'),
                          ('voltage_now','3499999')]:
            with self.subTest(field=field,val=val):
                old=(self.bat/field).read_text()
                (self.bat/field).write_text(val+'\n')
                result, calls = self.run_boot()
                self.assertEqual(result.returncode,0)
                self.assertIn('BATTERY_GUARD_SKIP_CHARGER',result.stdout)
                self.assertNotIn('n71-sn2400-input-trial.ko',calls)
                (self.bat/field).write_text(old)
                (self.root/'attempted').unlink()
                (self.root/'worker-attempted').rmdir()
                (self.root/'loads').write_text('')

    def test_preexisting_module_never_double_arms(self):
        (self.root/'modules').write_text('n71_sn2400_input_trial 49152 0 - Live\n')
        result,calls=self.run_boot()
        self.assertEqual(result.returncode,0)
        self.assertIn('CHARGER_MODULE_ALREADY_PRESENT_NO_REARM',result.stdout)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_gadget_not_configured_refuses_all_modules(self):
        (self.root/'udc').write_text('not attached\n')
        result,calls=self.run_init()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('USB_NOT_CONFIGURED',result.stdout)
        self.assertNotIn('gpio-apple-pmic.ko',calls)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_glitch_resets_stability_consecutive_samples(self):
        self._make('cat', '''if [ "$1" = "$MOCK_UDC" ]; then
            n=$(/bin/cat "$MOCK_UDC_COUNT" 2>/dev/null || echo 0)
            n=$((n+1)); echo "$n" > "$MOCK_UDC_COUNT"
            if [ "$n" -eq 8 ]; then echo 'not attached'; else echo configured; fi
        else exec /bin/cat "$@"; fi''')
        result,calls=self.run_boot()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        count=int((self.root/'udc-count').read_text())
        self.assertGreaterEqual(count,23) # one glitch forces fresh 15 samples
        self.assertIn('USB_POST_ENUMERATION_STABILITY_CONFIRMED',result.stdout)
        self.assertEqual(calls.count('n71-sn2400-input-trial.ko'),1)

    def test_configured_usb_before_45s_never_arms(self):
        (self.root/'uptime').write_text('30.000 60.000\n')
        result,calls=self.run_boot()
        self.assertEqual(result.returncode,0)
        self.assertIn('USB_STABILITY_TIMEOUT_SKIP_CHARGER',result.stdout)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_corrupt_firmware_manifest_never_loads_module(self):
        self._make('sha256sum', 'exit 1')
        result,calls=self.run_init()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('HASH_CHECK_FAILED',result.stdout)
        self.assertEqual(calls,'')

    def test_pmic_loader_error_does_not_arm_charger(self):
        self._make('module-once', 'exit 1')
        result,calls=self.run_init()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('PMIC_GPIO_LOAD_FAILED_SKIP_CHARGER',result.stdout)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_main_init_starts_charge_worker_without_waiting(self):
        result,calls=self.run_init()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('CHARGER_WORKER_SPAWNED', result.stdout)
        self.assertIn('RUNTIME_STARTUP_FINISHED_PCIE_NOT_ACTIVATED',result.stdout)
        self.assertIn('gpio-apple-pmic.ko',calls)
        self.assertIn('CHARGER_WORKER_LAUNCH_REQUESTED',calls)
        self.assertNotIn('n71-sn2400-input-trial.ko',calls)

    def test_source_does_not_disable_hardware_vbus_rollback(self):
        self.assertIn('stable=0', SOURCE)
        self.assertIn('"$uptime_s" -ge 45', SOURCE)
        self.assertIn('"$stable" -lt 15', SOURCE)
        self.assertIn('"$temp" -ge 375', SOURCE)
        self.assertIn('"$voltage" -lt 4150000', SOURCE)
        self.assertIn('CHARGE_INPUT_UA=300000', SOURCE)
        self.assertIn('CHARGE_LEASE_SECONDS=3600', SOURCE)
        self.assertIn('input_ua=$CHARGE_INPUT_UA lease_seconds=$CHARGE_LEASE_SECONDS', SOURCE)
        self.assertNotIn('modprobe n71_s3e', SOURCE)
        self.assertNotIn('writel(', SOURCE)
        driver = (ROOT/'experimental/power/n71-sn2400-input-trial.c').read_text()
        self.assertIn('uv < 4400000 || uv > 5500000', driver)
        self.assertIn('restore_input("monitor-stop")', driver)
        self.assertIn('schedule_delayed_work(&monitor', driver)

    def test_explicit_two_hour_profile_can_charge_low_reserve_without_lowering_native_guards(self):
        (self.root/'two-hour-profile').write_text('n71-owner-two-hour-500ma-v1\n')
        (self.bat/'capacity').write_text('12\n')
        (self.bat/'voltage_now').write_text('3350000\n')
        result,calls=self.run_boot()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(calls.count('n71-sn2400-input-trial.ko'),1)
        self.assertIn('input_ua=500000 lease_seconds=7200',calls)

    def test_unknown_two_hour_optin_refuses_every_module(self):
        (self.root/'two-hour-profile').write_text('unqualified-profile\n')
        result,calls=self.run_init()
        self.assertEqual(result.returncode,2)
        self.assertIn('UNKNOWN_CHARGE_PROFILE_REFUSED',result.stdout)
        self.assertEqual(calls,'')

if __name__ == '__main__':
    unittest.main()
