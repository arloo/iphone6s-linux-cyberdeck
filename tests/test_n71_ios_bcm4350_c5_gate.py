"""Synthetic-only tests for live iOS N71 BCM4350 C5 request provenance."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_ios_bcm4350_c5_gate.py"
spec=importlib.util.spec_from_file_location("n71_ios_c5",SCRIPT)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def core_document(variant="C5"):
    return {"IORegistry":{
        "IOClass":"AppleBCMWLANCore",
        "IOProviderClass":"AppleBCMWLANBusInterfacePCIe",
        "ChipSet":4350,
        "FirmwareLoaded":True,
        "PlatformConfigFileName":"P-albarossa_M-SYNTHETIC.txt",
        "RequestedFiles":[{
            k:f"C-4350__s-{variant}/{k.lower()}{suffix}"
            for k,suffix in gate.EXPECTED.items()
        }],
        "IOMACAddress":b"PRIVATE_SYNTHETIC_NOT_FOR_OUTPUT",
        "serial-number":b"PRIVATE_SENTINEL_NOT_FOR_OUTPUT",
    }}

def document(data):
    return plistlib.dumps(data,fmt=plistlib.FMT_XML)

class TestN71LiveC5Gate(unittest.TestCase):
    def rejected(self,obj):
        with self.assertRaises(gate.RejectedFirmwareMetadata):
            gate.validate_core_plist(document(obj))

    def test_matching_live_c5_requests(self):
        result=gate.validate_core_plist(document(core_document()))
        self.assertEqual(set(result),set(gate.EXPECTED))

    def test_wrong_c2_variant_rejected(self):
        self.rejected(core_document("C2"))

    def test_missing_requested_file_rejected(self):
        o=core_document()
        del o["IORegistry"]["RequestedFiles"][0]["TxCap"]
        self.rejected(o)

    def test_extra_requested_file_rejected(self):
        o=core_document()
        o["IORegistry"]["RequestedFiles"][0]["Other"]="PRIVATE"
        self.rejected(o)

    def test_unexpected_chipset_rejected(self):
        o=core_document()
        o["IORegistry"]["ChipSet"]=4355
        self.rejected(o)

    def test_ignored_firmware_loaded_false_rejected(self):
        o=core_document()
        o["IORegistry"]["FirmwareLoaded"]=False
        self.rejected(o)

    def test_unsupported_core_class_rejected(self):
        o=core_document()
        o["IORegistry"]["IOClass"]="WrongCore"
        self.rejected(o)

    def test_wrong_platform_rejected(self):
        o=core_document()
        o["IORegistry"]["PlatformConfigFileName"]="not_albarossa"
        # A containing match still passes, so use a truly distinct family.
        o["IORegistry"]["PlatformConfigFileName"]="P-macbook"
        self.rejected(o)

    def test_traversal_filename_rejected(self):
        o=core_document()
        o["IORegistry"]["RequestedFiles"][0]["NVRAM"] = (
            "C-4350__s-C5/../nvram.txt")
        self.rejected(o)

    def test_valid_private_bundle_exactly_one_file_per_kind(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c5=root/"C-4350__s-C5"
            c5.mkdir()
            r=gate.validate_core_plist(document(core_document()))
            for name in r.values():
                (c5/name).write_bytes(b"synthetic-content")
            gate.verify_bundle_files(r,root)

    def test_missing_bundle_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c5=root/"C-4350__s-C5";c5.mkdir()
            r=gate.validate_core_plist(document(core_document()))
            for kind,name in r.items():
                if kind!="NVRAM":(c5/name).write_bytes(b"synthetic")
            with self.assertRaises(gate.RejectedFirmwareMetadata):
                gate.verify_bundle_files(r,root)

    def test_bundle_c2_only_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c2=root/"C-4350__s-C2";c2.mkdir()
            r=gate.validate_core_plist(document(core_document()))
            for filename in r.values():(c2/filename).write_bytes(b"fake")
            with self.assertRaises(gate.RejectedFirmwareMetadata):
                gate.verify_bundle_files(r,root)

    def test_duplicate_c5_filenames_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            one=root/"C-4350__s-C5";one.mkdir()
            alt=one/"duplicate";alt.mkdir()
            r=gate.validate_core_plist(document(core_document()))
            for name in r.values():(one/name).write_bytes(b"synthetic")
            (alt/r["Firmware"]).write_bytes(b"another")
            with self.assertRaises(gate.RejectedFirmwareMetadata):
                gate.verify_bundle_files(r,root)

    def test_empty_asset_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);c5=root/"C-4350__s-C5";c5.mkdir()
            r=gate.validate_core_plist(document(core_document()))
            for name in r.values():(c5/name).write_bytes(b"")
            with self.assertRaises(gate.RejectedFirmwareMetadata):
                gate.verify_bundle_files(r,root)

    def test_private_calibration_fields_not_interpreted(self):
        o=core_document()
        o["IORegistry"]["ChipOTP"]=b"PRIVATE_OTP_SENTINEL"
        r=gate.validate_core_plist(document(o))
        self.assertEqual(set(r),set(gate.EXPECTED))

    def test_fake_cli_input_fails_without_private_dump(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"private-input.plist"
            f.write_bytes(b"PRIVATE_SENTINEL_CORRUPT_PLIST")
            p=subprocess.run([sys.executable,str(SCRIPT),str(f),str(td)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("FAIL_CLOSED",p.stderr)
            self.assertNotIn("PRIVATE_SENTINEL",p.stdout+p.stderr)

    def test_no_hardware_access_or_apple_file_content_export(self):
        src=SCRIPT.read_text()
        for token in ("write_bytes(", "subprocess.run(", "mmap(",
                      "open('/dev/mem", "ioremap(", "writel(",
                      "os.system(", "print(core)", "print(data)",
                      "print(requests)", "idevicepair unpair"):
            self.assertNotIn(token,src)

    def test_blocked_status_explicit(self):
        text=SCRIPT.read_text()
        self.assertIn("HARDWARE_BLOCKED",text)
        self.assertIn("PRIVATE_FIRMWARE_OR_CALIBRATION_EXPORTED=NO",text)

if __name__=="__main__":
    unittest.main()
