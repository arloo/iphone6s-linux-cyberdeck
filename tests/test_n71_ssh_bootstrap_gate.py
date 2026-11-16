"""Offline-only regression for USB-key-only recovery SSH in the RAM boot."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class USBSSHBootstrapGate(unittest.TestCase):
    def test_key_only_usb_listener_and_hash_pin(self):
        script = (ROOT / "scripts/n71_ssh_start.sh").read_text()
        self.assertIn("-p 172.16.42.1:22 -s -j -k", script)
        self.assertIn("sha256sum -c /usr/lib/cyberdeck/n71-ssh.sha256", script)
        self.assertIn("host_ed25519", script)
        self.assertNotIn("0.0.0.0:22", script)

    def test_bootstrap_fails_separately_from_connectivity(self):
        script = (ROOT / "scripts/n71_integrated_ram_startup.sh").read_text()
        self.assertEqual(script.count("/bin/sh /usr/bin/n71-ssh-provision-ram"), 1)
        self.assertIn("ip -4 addr show dev usb0", script)
        self.assertIn("n71-ssh-bootstrap-PRIVATE.log", script)
        self.assertLess(script.index("/bin/sh /usr/bin/n71-ssh-provision-ram"),
                        script.index("/bin/sh /usr/bin/n71-connectivity-autostart"))
        self.assertIn("if [ -x /usr/bin/n71-ssh-provision-ram ]; then", script)
        provision = (ROOT / "scripts/n71_ssh_provision_ram.sh").read_text()
        self.assertIn("dropbearkey -t ed25519", provision)
        self.assertIn("n71-ssh.sha256", provision)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", provision)


if __name__ == "__main__":
    unittest.main()
