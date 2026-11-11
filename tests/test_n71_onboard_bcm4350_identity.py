"""Synthetic-only PCIe onboard BCM4350 identity acceptance regressions.

All fake sysfs trees are local temporary directories. No actual radio,
original Apple firmware, hardware identity or private device data is read.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GATE=ROOT/"scripts/n71_onboard_bcm4350_identity.sh"
ACCEPT=ROOT/"scripts/n71_native_wifi_acceptance.sh"

def synthetic_pci_sysfs(root:Path, *, vendor="0x14e4", device="0x43a3",
                       driver="brcmfmac", is_pci=True, has_phy=True):
    sys=root/"sys"
    net=sys/"class/net/wlan0"
    net.mkdir(parents=True)
    pci_device=sys/"devices/pci0000:00/0000:01:00.0"
    pci_device.mkdir(parents=True)
    if has_phy:
        (net/"phy80211").symlink_to("phy-wireless")
        (net/"phy-wireless").write_text("synthesized phy")
    (pci_device/"vendor").write_text(vendor)
    (pci_device/"device").write_text(device)
    driver_dir=sys/"bus/pci/drivers"/driver
    driver_dir.mkdir(parents=True)
    (pci_device/"driver").symlink_to(driver_dir)
    (net/"device").symlink_to(pci_device,target_is_directory=True)
    (sys/"bus/pci/devices").mkdir(parents=True)
    if is_pci:
        (sys/"bus/pci/devices/0000:01:00.0").symlink_to(
            pci_device,target_is_directory=True)
    return sys,pci_device,net

class TestA9OnboardBCM4350Identity(unittest.TestCase):
    def check(self,sysroot:Path,iface="wlan0"):
        return subprocess.run(["sh",str(GATE),iface,str(sysroot)],
                              capture_output=True,text=True,timeout=8)

    def test_actual_pci_broadcom_fixture_only(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td))
            r=self.check(sys)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("N71_ONBOARD_BCM4350_PCIE_IDENTITY_PASS",r.stdout)

    def test_usb_wlan_adapter_is_not_pci(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td),is_pci=False)
            r=self.check(sys)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("not_pci_endpoint",r.stdout)

    def test_wrong_vendor_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td),vendor="0x8086")
            self.assertIn("not_broadcom_vendor",self.check(sys).stdout)

    def test_wrong_broadcom_model_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td),device="0x43a4")
            self.assertIn("not_bcm4350",self.check(sys).stdout)

    def test_usb_chipset_rejected_even_same_name(self):
        with tempfile.TemporaryDirectory() as td:
            sys,dev,net=synthetic_pci_sysfs(Path(td))
            (sys/"bus/pci/devices/0000:01:00.0").unlink()
            usb_device=sys/"devices/usb1/1-1"
            usb_device.mkdir(parents=True)
            (usb_device/"vendor").write_text("0x14e4")
            (usb_device/"device").write_text("0x43a3")
            (usb_device/"driver").symlink_to(sys/"bus/pci/drivers/brcmfmac")
            (net/"device").unlink()
            (net/"device").symlink_to(usb_device)
            self.assertIn("not_pci_endpoint",self.check(sys).stdout)

    def test_missing_wiphy_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td),has_phy=False)
            self.assertIn("ieee80211_phy_absent",self.check(sys).stdout)

    def test_missing_driver_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,dev,_=synthetic_pci_sysfs(Path(td))
            (dev/"driver").unlink()
            self.assertIn("missing_driver",self.check(sys).stdout)

    def test_wrong_driver_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td),driver="other")
            self.assertIn("not_brcmfmac",self.check(sys).stdout)

    def test_unresolvable_interface_parent_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,dev,net=synthetic_pci_sysfs(Path(td))
            (net/"device").unlink()
            (net/"device").symlink_to("missing-device")
            self.assertIn("parent_device_absent",self.check(sys).stdout)

    def test_unexpected_pci_path_outside_sysroot_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,net=synthetic_pci_sysfs(Path(td))
            (net/"device").unlink()
            (net/"device").symlink_to("/etc")
            self.assertIn("device_outside_sysfs_root",self.check(sys).stdout)

    def test_missing_pci_bus_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td))
            shutil.rmtree(sys/"bus/pci/devices")
            self.assertIn("pci_bus_absent",self.check(sys).stdout)

    def test_invalid_interface_argument_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sys,_,_=synthetic_pci_sysfs(Path(td))
            self.assertIn("invalid_interface",
                          self.check(sys,"../../etc/passwd").stdout)

    def test_bad_arguments_rejected(self):
        r=subprocess.run(["sh",str(GATE)],capture_output=True,text=True,timeout=8)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("usage_interface",r.stdout)

    def test_no_hardware_writes_or_network_operations(self):
        text=GATE.read_text()
        for forbidden in ("ip link set","iw dev","modprobe ",
                          "insmod ","echo 1 >","dd if=",
                          "writel(", "/dev/mem","ping -I"):
            self.assertNotIn(forbidden,text)

    def test_actual_acceptance_requires_onboard_checker(self):
        text=ACCEPT.read_text()
        self.assertIn('n71_onboard_bcm4350_identity.sh',text)
        self.assertIn('"$IFACE" /sys',text)
        self.assertIn('fail "not_n71_onboard_bcm4350_pcie"',text)
        self.assertIn("ping -I",text)

    def test_acceptance_must_fail_offline_without_phone(self):
        r=subprocess.run(["sh",str(ACCEPT),"wlan0",
                          "offline-test","192.0.2.1","192.0.2.2"],
                         capture_output=True,text=True,timeout=8)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("N71_NATIVE_WIFI_FAIL",r.stdout)
        self.assertNotIn("N71_NATIVE_WIFI_ACCEPTANCE_PASS",r.stdout)

if __name__=="__main__":
    unittest.main()
