"""Synthetic-only N71 iOS IODeviceMemory provider ordering and privacy tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_ios_iodevicememory_order_gate.py"
spec=importlib.util.spec_from_file_location("ios_n71_memory",TOOL)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def make_doc():
    # Synthetic fixture: hardware constant window values only, no phone data.
    return {"IORegistry":{
        "compatible":b"apcie,s8000\0",
        "IOPCIConfigured":True,
        "#ports":struct.pack("<I",4),
        "reg":b"".join(struct.pack("<QQ",a,n)
                        for a,n in gate.HOST_LAYOUT),
        "IODeviceMemory":[[{"address":a,"length":n}]
                          for a,n in gate.HOST_LAYOUT],
        "serial-number":"SYNTHETIC_SECRET_NOT_FOR_OUTPUT",
        "personal-sensitive-field":b"SYNTHETIC_SECRET",
    }}

def encode(doc):
    return plistlib.dumps(doc,fmt=plistlib.FMT_XML)

class TestLiveN71MemoryOrder(unittest.TestCase):
    def reject(self,doc):
        with self.assertRaises(gate.RegistryNotVerified):
            gate.validate_live_registry(encode(doc))

    def test_all_eleven_exact_provider_indices(self):
        values=gate.validate_live_registry(encode(make_doc()))
        self.assertEqual(len(values),11)
        self.assertEqual(values,gate.HOST_LAYOUT)

    def test_common_index_nine(self):
        self.assertEqual(gate.validate_live_registry(
            encode(make_doc()))[9],(0x600000000,0x8000))

    def test_additional_index_ten(self):
        self.assertEqual(gate.validate_live_registry(
            encode(make_doc()))[10],(0x600008000,0x4000))

    def test_index_zero_is_config_range(self):
        self.assertEqual(gate.validate_live_registry(
            encode(make_doc()))[0],(0x610000000,0x1000000))

    def test_reordered_provider_resources_rejected(self):
        doc=make_doc()
        x=doc["IORegistry"]["IODeviceMemory"]
        x[9],x[10]=x[10],x[9]
        self.reject(doc)

    def test_missing_provider_resource_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"].pop()
        self.reject(doc)

    def test_duplicate_provider_range_rejected(self):
        doc=make_doc()
        x=doc["IORegistry"]["IODeviceMemory"]
        x[1]=x[0]
        self.reject(doc)

    def test_corrupt_address_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"][9][0]["address"]+=4096
        self.reject(doc)

    def test_corrupt_length_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"][10][0]["length"]+=4096
        self.reject(doc)

    def test_modified_raw_adt_reg_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["reg"]=b"\0"*176
        self.reject(doc)

    def test_modified_compatibility_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["compatible"]=b"apcie,t8103\0"
        self.reject(doc)

    def test_not_four_ports_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["#ports"]=struct.pack("<I",3)
        self.reject(doc)

    def test_root_unconfigured_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IOPCIConfigured"]=False
        self.reject(doc)

    def test_noninteger_address_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"][3][0]["address"]="0x602000000"
        self.reject(doc)

    def test_boolean_address_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"][3][0]["address"]=True
        self.reject(doc)

    def test_unexpected_element_shape_rejected(self):
        doc=make_doc()
        doc["IORegistry"]["IODeviceMemory"][3]=[{"address":1,
                                                    "length":4096},
                                                   {"address":2,"length":4096}]
        self.reject(doc)

    def test_bad_binary_input_rejected(self):
        with self.assertRaises(gate.RegistryNotVerified):
            gate.validate_live_registry(b"NOT-A-PLIST")

    def test_too_large_registry_rejected(self):
        with self.assertRaises(gate.RegistryNotVerified):
            gate.validate_live_registry(b"z"*(gate.MAX_REGISTRY_BYTES+1))

    def test_private_property_not_interpreted(self):
        doc=make_doc()
        doc["IORegistry"]["serial-number"]="INTENTIONALLY_UNTRUSTED_PRIVATE"
        self.assertEqual(gate.validate_live_registry(
            encode(doc)),gate.HOST_LAYOUT)

    def test_corrupt_private_adt_fails_closed(self):
        with patch.object(gate.ADT_GATE,"audit_bytes",
                          side_effect=gate.ADT_GATE.RejectedADT("BAD")):
            with self.assertRaises(gate.RegistryNotVerified):
                gate.compare_private_inputs(encode(make_doc()),b"faked")

    def test_mocked_valid_adt_passes(self):
        with patch.object(gate.ADT_GATE,"audit_bytes",
                          return_value="S8000_ADT_METADATA_GATE_PASS\n"
                          "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED"):
            self.assertEqual(gate.compare_private_inputs(
                encode(make_doc()),b"synthetic"),gate.HOST_LAYOUT)

    def test_invalid_cli_fails_without_dumping_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            reg=Path(folder)/"bad_ioreg.plist"
            adt=Path(folder)/"bad_adt"
            reg.write_bytes(b"SYNTHETIC_PRIVATE_SECRET_BAD_REGISTRY")
            adt.write_bytes(b"NOT_AN_ADT")
            p=subprocess.run([sys.executable,str(TOOL),str(reg),str(adt)],
                             text=True,capture_output=True,timeout=7)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("FAIL_CLOSED",p.stderr)
            self.assertNotIn("SYNTHETIC_PRIVATE_SECRET",p.stdout+p.stderr)

    def test_no_apple_binary_export_or_device_writes(self):
        src=TOOL.read_text()
        for bad in ("write_bytes(", "subprocess.run(", "os.system(",
                    "open('/dev/mem", "ioremap(", "readl(", "writel(",
                    "print(root)", "print(doc)", "print(data)",
                    "idevicepair unpair", "idevicediagnostics restart"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad,src)

    def test_hardware_remains_blocked(self):
        src=TOOL.read_text()
        self.assertIn("HARDWARE_BLOCKED",src)
        self.assertIn("ALL_11_PROVIDER_RESOURCES_MATCH_PRIVATE_ADT_IN_ORDER=YES",src)
        self.assertIn("IOS_IOREGISTRY_RAW_VALUES_EXPORTED=NO",src)

if __name__=="__main__":
    unittest.main()
