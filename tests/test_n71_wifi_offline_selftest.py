"""Offline-only N71 Wi-Fi integrated preflight smoke/safety tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest

R=Path(__file__).resolve().parents[1]
SCRIPT=R/"scripts/n71_wifi_offline_selftest.sh"

class TestN71OfflineWiFiIntegratedPreflight(unittest.TestCase):
    def call(self,*args):
        return subprocess.run(["bash",str(SCRIPT),*map(str,args)],
                              capture_output=True,text=True,timeout=10)

    def test_shell_syntax(self):
        r=subprocess.run(["bash","-n",str(SCRIPT)],
                         capture_output=True,text=True,timeout=8)
        self.assertEqual(r.returncode,0)

    def test_requires_eight_private_inputs(self):
        r=self.call()
        self.assertEqual(r.returncode,2)
        self.assertIn("Usage:",r.stderr)

    def test_missing_required_file_fails_before_probing(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty=Path(tmp)/"absent"
            r=self.call(*([empty]*8))
            self.assertNotEqual(r.returncode,0)
            self.assertIn("BLOCKED_MISSING_FILE",r.stderr)

    def test_wrong_private_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            files=[p/f"f{i}" for i in range(5)]
            for f in files:f.write_text("synthetic")
            r=self.call(*files,*([p/"not-a-dir"]*3))
            self.assertNotEqual(r.returncode,0)
            self.assertIn("BLOCKED_MISSING_PRIVATE_DIR",r.stderr)

    def test_all_required_static_auditors_are_wired(self):
        text=SCRIPT.read_text()
        for name in (
            "n71_s8000_adt_window_gate.py",
            "n71_s8000_root_resource_gate.py",
            "n71_s8000_provider_order_gate.py",
            "n71_wifi_kernel_baseline_gate.py",
            "n71_bcm4350_firmware_integrity_gate.py",
            "n71_wifi_kernel_symbol_gate.py",
        ):
            with self.subTest(name=name):self.assertIn(name,text)

    def test_real_ko_architecture_guard(self):
        text=SCRIPT.read_text()
        self.assertIn("aarch64-linux-gnu-readelf",text)
        self.assertIn("modinfo -F vermagic",text)
        self.assertIn('"$EXPECTED "*',text)
        self.assertIn("gpio-apple-pmic.ko",text)
        self.assertIn("brcmutil.ko",text)

    def test_explicit_single_pkcs7_blocker_no_false_wifi_claim(self):
        s=SCRIPT.read_text()
        self.assertIn("SINGLE_KNOWN_PKCS7_BLOCKER",s)
        self.assertIn("STILL_BLOCKED",s)
        self.assertIn("DART1_DMA",s)
        self.assertIn("NO_HARDWARE_ACCESS_NO_WIFI_CLAIM",s)

    def test_no_device_access_or_firmware_transfer(self):
        s=SCRIPT.read_text()
        for forbidden in (
            "lsusb ","ssh ","scp ","curl ","wget ","insmod ",
            "modprobe ","rmmod ","dd if=", "mount ","ioremap(",
            "write_bytes(", "/dev/mem", "/dev/i2c-", "git push",
            "ping ","iw dev","ip link set","socat "):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,s)

    def test_silent_tool_output_no_proprietary_extraction(self):
        s=SCRIPT.read_text()
        self.assertIn('root_resource_gate.py" "$KERNEL" "$ADT" >/dev/null',s)
        self.assertIn("FIRMWARE_SOURCE",s)
        self.assertIn("FIRMWARE_STAGE",s)
        self.assertNotIn("sha256sum ",s)
        self.assertNotIn("head -c ",s)

if __name__=="__main__":
    unittest.main()
