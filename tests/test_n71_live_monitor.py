"""Offline checks for the privacy-filtered USB monitor."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("n71_live_monitor", HERE / "scripts/n71_live_monitor.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

SAMPLE = """kernel=7.3.0-rc1-n71-batt2-g68aadac820d0-dirty
capacity=71
status=Not charging
cell_uV=4042000
current_uA=-32000
temp_tenths=358
usb=configured
wlan=1
wifi_ip=192.168.1.7
bluetooth=present
nvme_module=loaded
nand_reset=asserted_low
ui=running
charge_supervisor=running
ram_available_kb=1729900
"""

class LiveMonitor(unittest.TestCase):
    def test_exact_qualified_sample(self):
        x=monitor.parse_status(SAMPLE)
        self.assertEqual(x["status"], "Not charging")
        self.assertEqual(int(x["current_uA"]), -32000)
        self.assertEqual(x["wifi_ip"], "192.168.1.7")

    def test_fail_closed_on_missing_metric(self):
        with self.assertRaises(ValueError):
            monitor.parse_status(SAMPLE.replace("capacity=71\n", ""))

    def test_private_values_not_admitted(self):
        row=monitor.parse_status(SAMPLE+"secret=/root/.ssh/id_ed25519\n")
        self.assertNotIn("secret", row)
        self.assertNotIn("id_ed25519", str(row))
        with self.assertRaises(ValueError):
            monitor.parse_status(SAMPLE.replace("kernel=7.3.0-rc1-n71-batt2-g68aadac820d0-dirty",
                                              "kernel=unexpected-version"))

    def test_probe_has_no_mutating_commands(self):
        p=monitor.PROBE
        for forbidden in ("rmmod", "insmod", "kill -9", "writel", "echo >",
                          "dd ", "mount ", "ip link set", "chmod", "chown",
                          "sed -i", "rm -", "ssh-keyscan"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, p)
        self.assertIn("charge_supervisor=",p)
        self.assertIn("gpio-160",p)

if __name__=="__main__":
    unittest.main()
