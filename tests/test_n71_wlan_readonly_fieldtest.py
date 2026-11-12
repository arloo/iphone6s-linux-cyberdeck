"""Real shell execution tests for the safe N71 RAM-only WLAN baseline."""
from __future__ import annotations
from pathlib import Path
import os, subprocess, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/n71_wlan_readonly_fieldtest.sh"

class TestN71WiFiReadOnlyFieldtest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        dt=self.root/"proc/device-tree"
        dt.mkdir(parents=True)
        (dt/"compatible").write_bytes(b"apple,n71\0apple,s8000\0")
        (self.root/"sys/bus/pci/devices").mkdir(parents=True)
        (self.root/"sys/kernel/iommu_groups").mkdir(parents=True)
        (self.root/"sys/class/net").mkdir(parents=True)
        (self.root/"sys/bus/platform/devices").mkdir(parents=True)

    def run_script(self,root=None):
        env={**os.environ,"N71_READONLY_FIXTURE_ROOT":
             str(root if root is not None else self.root)}
        return subprocess.run(["/bin/sh",str(SCRIPT)],text=True,
                              capture_output=True,timeout=15,env=env)

    def test_real_shell_syntax(self):
        subprocess.run(["/bin/sh","-n",str(SCRIPT)],check=True,timeout=5)

    def test_only_apple_n71_and_s8000_allowed(self):
        p=self.run_script()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("N71_WLAN_FIELDTEST_BOARD_N71_S8000_PASS",p.stdout)
        self.assertIn("N71_WLAN_FIELDTEST_TEST_FINISHED",p.stdout)

    def test_missing_board_fails_closed(self):
        (self.root/"proc/device-tree/compatible").unlink()
        self.assertNotEqual(self.run_script().returncode,0)

    def test_wrong_n71m_fails_closed(self):
        (self.root/"proc/device-tree/compatible").write_bytes(
            b"apple,n71m\0apple,s8003\0")
        self.assertNotEqual(self.run_script().returncode,0)

    def test_other_soc_fails_closed(self):
        (self.root/"proc/device-tree/compatible").write_bytes(
            b"apple,n71\0apple,s8003\0")
        self.assertNotEqual(self.run_script().returncode,0)

    def test_actual_synthetic_sysfs_pci_and_wlan(self):
        for path in ("sys/bus/pci/devices/0000:00:00.0",
                     "sys/bus/pci/devices/0000:01:00.0",
                     "sys/kernel/iommu_groups/0",
                     "sys/bus/platform/devices/602008000.dart",
                     "sys/bus/platform/devices/602000000.pcie",
                     "sys/class/net/wlan0"):
            p=self.root/path;p.touch()
        result=self.run_script()
        self.assertEqual(result.returncode,0,result.stderr)
        for token in ("PCI_DEVICES_COUNT=2","IOMMU_GROUPS_COUNT=1",
                      "N71_DART1_PLATFORM_NODES_MATCHED=1",
                      "N71_PCIE_PORT1_PLATFORM_NODES_MATCHED=1",
                      "WLAN_INTERFACES_COUNT=1",
                      "WLAN_NETWORK_ASSOCIATION_NOT_TESTED"):
            self.assertIn(token,result.stdout)
        self.assertNotIn("NATIVE_WIFI_ASSOCIATED=YES",result.stdout)

    def test_no_pci_devices_not_treated_as_wifi_success(self):
        result=self.run_script()
        self.assertIn("PCI_DEVICES_COUNT=0",result.stdout)
        self.assertIn("WLAN_NATIVE_NOT_ENUMERATED_OR_NOT_NAMED",
                      result.stdout)

    def test_unrelated_storage_modem_platform_nodes_not_pcie1(self):
        for path in ("sys/bus/platform/devices/601000000.storage",
                     "sys/bus/platform/devices/603000000.modem",
                     "sys/bus/platform/devices/600000000.pcie-root"):
            (self.root/path).touch()
        result=self.run_script()
        self.assertIn("N71_PCIE_PORT1_PLATFORM_NODES_MATCHED=0",result.stdout)
        self.assertIn("N71_DART1_PLATFORM_NODES_MATCHED=0",result.stdout)

    def test_solely_readonly_functions_no_hardware_writes(self):
        s=SCRIPT.read_text()
        for token in ("dd if=/dev/mem","devmem ","ioremap","insmod ",
                      "modprobe ","ifconfig ","ip link set","nmcli",
                      "iw dev","wpa_supplicant","reboot","shutdown",
                      "palera1n","/dev/i2c-","/dev/spidev",
                      "mmio","mount "):
            # Some tokens may occur in comments; check executable lines only
            lines="\n".join(x for x in s.splitlines()
                            if not x.strip().startswith("#"))
            self.assertNotIn(token,lines)

    def test_no_mac_password_or_imei_in_source(self):
        s=SCRIPT.read_text().lower()
        self.assertNotIn("password=",s)
        self.assertNotIn("serial-number",s)
        self.assertNotIn("imei=",s)

    def test_rejects_relative_fixture_without_hardware_access(self):
        e={**os.environ,"N71_READONLY_FIXTURE_ROOT":"relative"}
        p=subprocess.run(["/bin/sh",str(SCRIPT)],env=e,text=True,
                         capture_output=True,timeout=10)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("REJECTED_RELATIVE_FIXTURE",p.stdout)

if __name__=="__main__": unittest.main()
