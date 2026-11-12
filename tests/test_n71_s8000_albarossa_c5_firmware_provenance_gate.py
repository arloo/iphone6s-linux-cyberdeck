"""Synthetic privacy-safe N71 BCM4350C5 'albarossa' firmware source tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import plistlib
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_albarossa_c5_firmware_provenance_gate.py"
SP=importlib.util.spec_from_file_location("n71_albarossa_c5_gate",SRC)
assert SP and SP.loader
M=importlib.util.module_from_spec(SP)
sys.modules[SP.name]=M
SP.loader.exec_module(M)

PROFILES=[
 f"P-albarossa_M-BLMA_V-{vendor}__m-{version}.txt"
 for vendor,versions in (
   ("m",("2.1","2.5","3.1","4.1","5.1","5.5")),
   ("u",("2.1","2.5","3.1","4.1","5.1","5.3")),
   ("t",("2.1","2.5")),
 ) for version in versions
]
assert len(PROFILES)==14

def specimen():
    original={n:(n.encode()+b"a"*180) for n in M.ORIG_TO_LINUX}
    original.update({n:(n.encode()+b"b"*180) for n in PROFILES})
    stage={target:original[src] for src,target in M.ORIG_TO_LINUX.items()}
    stage.update({M.validate_profile_name(src):original[src] for src in PROFILES})
    live=plistlib.dumps({"IORegistry":{"module-instance":b"albarossa\x00",
               "local-mac-address":b"PRIVATE_MAC_NOT_TO_SHOW"}})
    return live,original,stage

class TestN71C5OriginalFirmwareProvenance(unittest.TestCase):
    def test_exact_original_firmware_set(self):
        self.assertTrue(M.verify_sources(*specimen()))
    def test_original_c5_components_count(self):
        self.assertEqual(len(M.ORIG_TO_LINUX),3)
    def test_original_otp_profile_set_count(self):
        self.assertEqual(len(PROFILES),14)
    def test_private_n71_module_instance_must_be_albarossa(self):
        live,original,stage=specimen()
        live=plistlib.dumps({"IORegistry":{"module-instance":b"other\0"}})
        with self.assertRaises(M.UnprovenFirmware):
            M.verify_sources(live,original,stage)
    def test_missing_original_trx_rejected(self):
        live,original,stage=specimen();original.pop("albarossa.trx")
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_missing_original_clmb_rejected(self):
        live,original,stage=specimen();original.pop("albarossa.clmb")
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_missing_original_txcb_rejected(self):
        live,original,stage=specimen();original.pop("albarossa.txcb")
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_original_firmware_different_from_staged_fails_closed(self):
        live,original,stage=specimen()
        stage[M.LINUX_PREFIX+".bin"]+=b"CHANGED"
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_staged_clm_change_fails_closed(self):
        live,original,stage=specimen()
        stage[M.LINUX_PREFIX+".clm_blob"]=b"CORRUPT"+stage[M.LINUX_PREFIX+".clm_blob"]
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_missing_staged_nvram_rejected(self):
        live,original,stage=specimen();stage.pop(M.validate_profile_name(PROFILES[0]))
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_extra_unapproved_profile_rejected(self):
        live,original,stage=specimen();stage["private-serial-calibration.bin"]=b"x"*200
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_wrong_module_profile_rejected(self):
        for label in ("P-false_M-BLMA_V-m__m-5.1.txt",
                      "P-albarossa_M-OTHER_V-m__m-5.1.txt",
                      "P-albarossa_M-BLMA_V-z__m-5.1.txt",
                      "P-albarossa_M-BLMA_V-m__m-x.y.txt"):
            with self.subTest(label=label):
                with self.assertRaises(M.UnprovenFirmware):
                    M.validate_profile_name(label)
    def test_expected_linux_profile_filename_construction(self):
        self.assertEqual(M.validate_profile_name("P-albarossa_M-BLMA_V-m__m-5.1.txt"),
                         M.LINUX_PREFIX+"-BLMA-m-5.1.txt")
    def test_source_profile_duplicate_version_rejected(self):
        live,original,stage=specimen()
        original["P-albarossa_M-BLMA_V-m__m-5.1.TXT"]=b"X"*200
        with self.assertRaises(M.UnprovenFirmware):M.verify_sources(live,original,stage)
    def test_wrong_ios_plist_schema_rejected(self):
        _,original,stage=specimen()
        for bad in (b"not-plist",plistlib.dumps({"something":{}})):
            with self.assertRaises(M.UnprovenFirmware):
                M.verify_sources(bad,original,stage)
    def test_never_output_source_private_mac_nvrams_or_fw(self):
        source=SRC.read_text()
        for bad in ("print(live)","print(original)","print(staged)",
                    "print(registry)","print(value)","print(sha(",
                    "insmod","writel","ioremap","modprobe","flash_erase"):
            self.assertNotIn(bad,source)
        self.assertIn("N71_SPECIFIC_DEVICE_OTP_VENDOR_VERSION_SELECTED=NO",source)
        self.assertIn("N71_REAL_PCIE_DART_DMA_WIFI_LINK_STILL_UNPROVEN=YES",source)

if __name__=="__main__":
    unittest.main()
