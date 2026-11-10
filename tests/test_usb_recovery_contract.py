"""Host-only USB state classifier — synthetic fixtures; no physical USB writes."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/recovery_usb_readonly.sh"


class USBRecoveryObservationContract(unittest.TestCase):
    def run_mock(self, lsusb_output: str):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            mock = bin_dir / "lsusb"
            mock.write_text("#!/bin/sh\ncat <<'MOCK'\n" +
                            lsusb_output + "\nMOCK\n")
            mock.chmod(0o700)
            env = dict(os.environ)
            env["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
            return subprocess.run(["bash", str(SCRIPT)], env=env,
                                  capture_output=True, text=True, timeout=5)

    def test_linux_gadget(self):
        x = self.run_mock("Bus 001 Device 002: ID 05ac:4142 HoolockLinux")
        self.assertEqual(x.returncode, 0)
        self.assertIn("PHONE_STATE=LINUX_GADGET_ENUMERATED", x.stdout)

    def test_pongo_usb(self):
        x = self.run_mock("Bus 001 Device 002: ID 05ac:4141 PongoOS")
        self.assertEqual(x.returncode, 0)
        self.assertIn("PHONE_STATE=PONGOOS_USB_ENUMERATED", x.stdout)

    def test_apple_dfu(self):
        x = self.run_mock("Bus 001 Device 002: ID 05ac:1227 Apple")
        self.assertEqual(x.returncode, 0)
        self.assertIn("PHONE_STATE=APPLE_DFU_ENUMERATED", x.stdout)

    def test_no_phone(self):
        x = self.run_mock("Bus 001 Device 001: ID 1d6b:0002 Linux hub")
        self.assertEqual(x.returncode, 2)
        self.assertIn("PHONE_STATE=NOT_ENUMERATED", x.stdout)

    def test_unknown_apple_never_triggers_action(self):
        x = self.run_mock("Bus 001 Device 002: ID 05ac:9999 Unknown Apple")
        self.assertEqual(x.returncode, 2)
        self.assertIn("PHONE_STATE=APPLE_USB_DEVICE_OTHER", x.stdout)

    def test_generic_recovery_needs_manual_identity(self):
        x = self.run_mock("Bus 001 Device 002: ID 05ac:1281 Recovery")
        self.assertEqual(x.returncode, 2)
        self.assertIn("POSSIBLE_APPLE_RECOVERY_MODE", x.stdout)

    def test_readonly_contract_contains_no_host_mutation_command(self):
        source = SCRIPT.read_text()
        for forbidden in ("\nusbreset ", "\nirecovery ", "\nreboot ",
                          "\nshutdown ", "\nudevadm trigger",
                          "\nmodprobe ", "\nmount ", "\nsystemctl restart"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
