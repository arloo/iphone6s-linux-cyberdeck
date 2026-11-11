"""Synthetic-only tests for pinned Apple A9 PCIe resource-index-0 gate.

All instruction sequences are small constructed ARM64 test fixtures; no real
IPSW, original Apple KEXT, per-device firmware or private ADT is used.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s8000_phy_resource_gate.py"
spec=importlib.util.spec_from_file_location("phy_resource_gate",SCRIPT)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def example(at=gate.SHARED_AT, length=18552):
    buf=bytearray(length)
    for offset,value in gate.EXPECTED.items():
        struct.pack_into("<I",buf,at+offset,value)
    # Synthetic nonzero CBZ displacement and synthetic BL displacement.
    struct.pack_into("<I",buf,at+0x24,0xb4000120)
    struct.pack_into("<I",buf,at+0x3c,0x94000004)
    return buf

class TestN71PhyResourceGate(unittest.TestCase):
    def reject(self,b,at):
        with self.assertRaises(gate.MappingNotVerified):
            gate.validated_resource_zero_sequence(bytes(b),at)

    def test_shared_s800x_fixture_passes(self):
        self.assertTrue(gate.validated_resource_zero_sequence(
            bytes(example()),gate.SHARED_AT))

    def test_specialized_s8000_fixture_passes(self):
        self.assertTrue(gate.validated_resource_zero_sequence(
            bytes(example(gate.SPECIAL_AT,2928)),gate.SPECIAL_AT))

    def test_missing_index_zero_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT,0x52800021)
        self.reject(b,gate.SHARED_AT)

    def test_different_provider_mapping_slot_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x10,0xf941e508)
        self.reject(b,gate.SHARED_AT)

    def test_nonzero_mapping_options_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x18,0x52800022)
        self.reject(b,gate.SHARED_AT)

    def test_missing_map_null_guard_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x24,0xd503201f)
        self.reject(b,gate.SHARED_AT)

    def test_other_map_object_field_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x20,0xf900e680)
        self.reject(b,gate.SHARED_AT)

    def test_other_mapped_virtual_field_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x34,0xf900ea80)
        self.reject(b,gate.SHARED_AT)

    def test_missing_helper_call_rejected(self):
        b=example()
        struct.pack_into("<I",b,gate.SHARED_AT+0x3c,0xd503201f)
        self.reject(b,gate.SHARED_AT)

    def test_truncated_arm64_blob_rejected(self):
        self.reject(example()[:gate.SHARED_AT+0x32],gate.SHARED_AT)

    def test_two_synthetic_dynamic_common_selectors(self):
        b=bytearray(46924)
        for start,selector,store in gate.DYNAMIC_COMMON_SELECTORS:
            for offset,value in {
                0x00:0xf9400268,
                0x04:selector,
                0x08:0xaa1303e0,
                0x0c:0xd63f0100,
                0x10:0xaa0003e1,
                0x14:0xf9400288,
                0x18:0xf941e908,
                0x1c:0xaa1403e0,
                0x20:0x52800002,
                0x24:0xd63f0100,
                0x28:store,
            }.items():
                struct.pack_into("<I",b,start+offset,value)
        self.assertEqual(gate.validated_dynamic_common_sequences(bytes(b)),2)

    def test_modified_dynamic_selector_fails_closed(self):
        b=bytearray(46924)
        for start,selector,store in gate.DYNAMIC_COMMON_SELECTORS:
            for offset,value in {
                0x00:0xf9400268,0x04:selector,0x08:0xaa1303e0,
                0x0c:0xd63f0100,0x10:0xaa0003e1,0x14:0xf9400288,
                0x18:0xf941e908,0x1c:0xaa1403e0,0x20:0x52800002,
                0x24:0xd63f0100,0x28:store,
            }.items():struct.pack_into("<I",b,start+offset,value)
        struct.pack_into("<I",b,0x1f50,0xf943b108)
        with self.assertRaises(gate.MappingNotVerified):
            gate.validated_dynamic_common_sequences(bytes(b))

    def test_common_mapping_cannot_use_alternate_store(self):
        b=bytearray(46924)
        for start,selector,store in gate.DYNAMIC_COMMON_SELECTORS:
            for offset,value in {
                0x00:0xf9400268,0x04:selector,0x08:0xaa1303e0,
                0x0c:0xd63f0100,0x10:0xaa0003e1,0x14:0xf9400288,
                0x18:0xf941e908,0x1c:0xaa1403e0,0x20:0x52800002,
                0x24:0xd63f0100,0x28:store,
            }.items():struct.pack_into("<I",b,start+offset,value)
        struct.pack_into("<I",b,0x1f74,0xf9005a60)
        with self.assertRaises(gate.MappingNotVerified):
            gate.validated_dynamic_common_sequences(bytes(b))

    def test_common_dynamic_map_must_not_be_truncated(self):
        with self.assertRaises(gate.MappingNotVerified):
            gate.validated_dynamic_common_sequences(bytes(0x1f70))

    def test_invalid_or_missing_input_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"synthetic.bin"
            p.write_bytes(bytes(example()))
            r=subprocess.run([sys.executable,str(SCRIPT),str(p),str(p)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_safety_gate_reports_candidate_not_verified_base(self):
        s=SCRIPT.read_text()
        self.assertIn('PROVIDER_RESOURCE_ORDER_CONFIRMED=NO',s)
        self.assertIn('COMMON_REGISTER_BASE_CONFIRMED=NO',s)
        self.assertIn("HARDWARE_BLOCKED",s)

    def test_source_has_no_hardware_access_or_binary_export(self):
        s=SCRIPT.read_text()
        for token in ("mmap(","/dev/mem","writel(", "readl(",
                      "ioremap(", "subprocess.run(", "write_bytes(",
                      "open('/dev/","os.system("):
            with self.subTest(token=token):
                self.assertNotIn(token,s)

if __name__=="__main__":
    unittest.main()
