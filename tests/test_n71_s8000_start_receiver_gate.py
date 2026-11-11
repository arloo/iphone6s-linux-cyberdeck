"""Synthetic AArch64 start receiver/provisioning tests; no Apple payload."""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_start_receiver_gate.py"
spec=importlib.util.spec_from_file_location("a9_start_rx",TOOL)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def fixture():
    data=bytearray(46924)
    def put(offset,value):
        struct.pack_into("<I",data,offset,value)
    put(gate.ENTRY,0xaa0103f4)
    put(gate.ENTRY+4,0xaa0003f3)
    for at,selector in gate.SELECTORS:
        expected=(
            0xf9400268,selector,0xaa1303e0,0xd63f0100,
            0xaa0003e1,0xf9400288,0xf941e908,0xaa1403e0,
            0x52800002,0xd63f0100,
        )
        for i,w in enumerate(expected):put(at+4*i,w)
    return data

class TestN71StartReceiver(unittest.TestCase):
    def reject(self,buf):
        with self.assertRaises(gate.ReceiverUnproven):
            gate.inspect_start_argument_flow(bytes(buf))

    def test_synthetic_self_and_provider_dispatch(self):
        self.assertEqual(gate.inspect_start_argument_flow(bytes(fixture())),2)

    def test_start_self_wrong_register_fails(self):
        b=fixture();struct.pack_into("<I",b,gate.ENTRY+4,0xaa0003f4)
        self.reject(b)

    def test_start_provider_wrong_register_fails(self):
        b=fixture();struct.pack_into("<I",b,gate.ENTRY,0xaa0103f3)
        self.reject(b)

    def test_selector_receives_provider_instead_of_self_fails(self):
        b=fixture();struct.pack_into("<I",b,0x1ee0,0xaa1403e0)
        self.reject(b)

    def test_selector_different_vtable_slot_fails(self):
        b=fixture();struct.pack_into("<I",b,0x1f50,0xf943b108)
        self.reject(b)

    def test_map_cannot_receive_controller_as_provider(self):
        b=fixture();struct.pack_into("<I",b,0x1ef4,0xaa1303e0)
        self.reject(b)

    def test_map_different_virtual_slot_fails(self):
        b=fixture();struct.pack_into("<I",b,0x1f64,0xf941e508)
        self.reject(b)

    def test_missing_return_to_resource_index_fails(self):
        b=fixture();struct.pack_into("<I",b,0x1ee8,0xaa1303e1)
        self.reject(b)

    def test_second_selector_missing_fails(self):
        b=fixture();struct.pack_into("<I",b,0x1f58,0xd503201f)
        self.reject(b)

    def test_truncated_code_fails(self):
        self.reject(fixture()[:0x1ed0])

    def test_duplicate_plist_keys_fails(self):
        d=ET.fromstring("<dict><key>IOClass</key><string>One</string>"
                         "<key>IOClass</key><string>Two</string></dict>")
        with self.assertRaises(gate.ReceiverUnproven):
            gate.plist_kv(d)

    def test_plist_personality_key_value_parsing(self):
        d=ET.fromstring("<dict><key>IOClass</key>"
                         "<string>AppleS8000PCIe</string></dict>")
        self.assertEqual(gate.plist_kv(d)["IOClass"].text,"AppleS8000PCIe")

    def test_invalid_cli_input_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"corrupt.macho"
            f.write_bytes(b"not a MachO")
            r=subprocess.run([sys.executable,str(TOOL),str(f),str(f)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_no_hardware_execution_or_proprietary_export(self):
        src=TOOL.read_text()
        for token in ("write_bytes(", "subprocess.run(", "open('/dev/mem",
                      "ioremap(", "writel(", "os.system(", "mmap(", "sendto("):
            with self.subTest(token=token):
                self.assertNotIn(token,src)

    def test_runtime_proof_qualified(self):
        src=TOOL.read_text()
        self.assertIn("S8000_RUNTIME_VTABLE_AT_CALLSITE_PROVEN=NO",src)
        self.assertIn("MMIO_RESOURCE_NUMBERS_AND_PHYSICAL_BASES_PROVEN=NO",src)

if __name__=="__main__":
    unittest.main()
