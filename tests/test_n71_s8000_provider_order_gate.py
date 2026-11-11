"""Synthetic-only AppleARMIODevice IODeviceMemory provenance/order gates.

No authentic iPhone IOServices, copyrighted code or sensitive IOKit data.
"""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s8000_provider_order_gate.py"
spec=importlib.util.spec_from_file_location("n71_provider_array_gate",SCRIPT)
m=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

# Fabricated physical ranges only; never use the real hardware address map
# to make a passing synthetic runtime snapshot.
MOCK = [(0x10000000+i*0x20000,0x1000) for i in range(11)]

def snapshot(rows=None):
    return {
      "schema":m.EXPECTED_SCHEMA,
      "source":m.SOURCE,
      "provider_class":m.EXPECTED_CLASS,
      "compatible":m.EXPECTED_COMPAT,
      "node_path":m.NODE_PATH,
      "IODeviceMemory":[
        {"address":hex(addr),"length":hex(length)}
        for addr,length in (MOCK if rows is None else rows)
      ],
    }

class TestOriginalIOSResourceOrder(unittest.TestCase):
    def match(self,entry):
        return m.inspect_snapshot(entry,list(MOCK))

    def rejects(self,entry):
        with self.assertRaises((m.UnverifiedResourceOrder,m.ADT.RejectedADT)):
            self.match(entry)

    def test_synthetic_order_match_only_conditional(self):
        v=self.match(snapshot())
        self.assertTrue(v["matches"])
        self.assertEqual(v["range_count"],11)
        self.assertFalse(v["capture_provenance_independently_verified"])

    def test_swapped_common_and_phy_fails(self):
        rows=list(MOCK)
        rows[9],rows[10]=rows[10],rows[9]
        self.rejects(snapshot(rows))

    def test_swapped_port_and_storage_fails(self):
        rows=list(MOCK)
        rows[1],rows[3]=rows[3],rows[1]
        self.rejects(snapshot(rows))

    def test_extra_range_fails(self):
        self.rejects(snapshot(MOCK+[(0x11000000,0x1000)]))

    def test_missing_range_fails(self):
        self.rejects(snapshot(MOCK[:10]))

    def test_shifted_common_base_fails(self):
        rows=list(MOCK)
        rows[9]=(0x12000000,0x1000)
        self.rejects(snapshot(rows))

    def test_corrupted_phy_length_fails(self):
        rows=list(MOCK)
        rows[10]=(rows[10][0],0x2000)
        self.rejects(snapshot(rows))

    def test_overlap_fails(self):
        rows=list(MOCK)
        rows[10]=(rows[9][0],rows[10][1])
        self.rejects(snapshot(rows))

    def test_zero_length_fails(self):
        rows=list(MOCK)
        rows[10]=(rows[10][0],0)
        self.rejects(snapshot(rows))

    def test_unaligned_range_fails(self):
        rows=list(MOCK)
        rows[10]=(rows[10][0]+1,rows[10][1])
        self.rejects(snapshot(rows))

    def test_boolean_address_fails(self):
        s=snapshot()
        s["IODeviceMemory"][0]["address"]=True
        self.rejects(s)

    def test_float_address_fails(self):
        s=snapshot()
        s["IODeviceMemory"][0]["address"]=float(MOCK[0][0])
        self.rejects(s)

    def test_string_leading_zero_fails(self):
        s=snapshot()
        s["IODeviceMemory"][0]["address"]="0x010000000"
        self.rejects(s)

    def test_unknown_provider_class_fails(self):
        s=snapshot()
        s["provider_class"]="SomeOtherController"
        self.rejects(s)

    def test_unknown_compatible_fails(self):
        s=snapshot()
        s["compatible"]="apcie,t8103"
        self.rejects(s)

    def test_untrusted_source_fails(self):
        s=snapshot()
        s["source"]="generated-from-adt"
        self.rejects(s)

    def test_extra_sensitive_property_fails(self):
        s=snapshot()
        s["device_serial"]="private-secret"
        self.rejects(s)

    def test_extra_element_property_fails(self):
        s=snapshot()
        s["IODeviceMemory"][0]["serial"]="private-secret"
        self.rejects(s)

    def test_duplicate_json_root_key_rejected(self):
        payload=(b'{"schema":"first","schema":"second"}')
        with self.assertRaises(m.UnverifiedResourceOrder):
            m.parse_snapshot(payload)

    def test_duplicate_json_range_key_rejected(self):
        payload=(b'{"IODeviceMemory":[{"address":"0x10000000",'
                 b'"address":"0x20000000"}]}')
        with self.assertRaises(m.UnverifiedResourceOrder):
            m.parse_snapshot(payload)

    def test_oversize_json_rejected(self):
        with self.assertRaises(m.UnverifiedResourceOrder):
            m.parse_snapshot(b' '*(m.MAX_JSON_BYTES+1))

    def test_integer_overflow_rejected(self):
        s=snapshot()
        s["IODeviceMemory"][0]["address"]="0xffffffffffffffff"
        self.rejects(s)

    def test_fake_input_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            adt=Path(td)/"fake.adt"
            adt.write_bytes(b"synthetic invalid ADT")
            result=subprocess.run([sys.executable,str(SCRIPT),str(adt)],
                                  capture_output=True,text=True,timeout=8)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("FAIL_CLOSED",result.stderr)

    def test_no_ios_capture_mode_never_claims_verified(self):
        code=SCRIPT.read_text()
        self.assertIn("PROVIDER_IODEVICE_MEMORY_ORDER_PROVEN=NO",code)
        self.assertIn("RUNTIME_IOS_PROVIDER_CAPTURE_MISSING=YES",code)
        self.assertIn("CAPTURE_PROVENANCE_INDEPENDENTLY_AUTHENTICATED=NO",code)
        self.assertIn("PROVIDER_RUNTIME_ORDER_PROVEN_FROM_TOOL_ALONE=NO",code)

    def test_no_hardware_effect_api_or_sensitive_serialization(self):
        code=SCRIPT.read_text()
        for forbidden in (
            "write_bytes(","mmap(", "subprocess.run(", "os.system(",
            "open('/dev/mem","writel(","readl(","ioremap(","socket.",
            "print(snap","print(snapshot","print(payload"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,code)

if __name__=="__main__":
    unittest.main()
