"""Synthetic-only AArch64 vtable-dispatch return tests (no Apple binaries)."""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_vtable_selector_audit.py"
spec=importlib.util.spec_from_file_location("a9_vtable_resolver",TOOL)
audit=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(audit)

def encode_adrp_x8(pc:int, page:int)->int:
    assert page%4096==0
    displacement=(page-(pc&~4095))//4096
    assert -(1<<20)<=displacement<(1<<20)
    imm=displacement&((1<<21)-1)
    return 0x90000008 | ((imm&3)<<29) | (((imm>>2)&0x7ffff)<<5)

def encode_add_x8(imm:int)->int:
    assert 0<=imm<4096
    return 0x91000108 | (imm<<10)

class TestS8000VtableGate(unittest.TestCase):
    def test_vtable_forward_page_and_add(self):
        pc=0x10080
        target=0x135a0
        self.assertEqual(audit.calculate_vtable(
            pc,encode_adrp_x8(pc,target&~4095),
            encode_add_x8(target&4095),0xf9000008),target)

    def test_vtable_backward_signed_adrp(self):
        pc=0x40040
        target=0x2e3a0
        self.assertEqual(audit.calculate_vtable(
            pc,encode_adrp_x8(pc,target&~4095),
            encode_add_x8(target&4095),0xf9000008),target)

    def test_reject_adrp_wrong_register(self):
        with self.assertRaises(audit.VtableAuditBlocked):
            audit.calculate_vtable(0x4000,0x90000009,
                                   encode_add_x8(0),0xf9000008)

    def test_reject_add_wrong_target_register(self):
        with self.assertRaises(audit.VtableAuditBlocked):
            audit.calculate_vtable(0x4000,encode_adrp_x8(0x4000,0x4000),
                                   0x91000109,0xf9000008)

    def test_reject_wrong_object_store(self):
        with self.assertRaises(audit.VtableAuditBlocked):
            audit.calculate_vtable(0x4000,encode_adrp_x8(0x4000,0x4000),
                                   encode_add_x8(0),0xf9000408)

    def test_constant_zero_is_not_a_physical_address(self):
        b=struct.pack("<2I",0xd2800000,0xd65f03c0)
        self.assertEqual(audit.classify_direct_return(b),"constant_zero")

    def test_unsupported_error_was_prelinked_not_an_index(self):
        b=struct.pack("<3I",0x528058e0,0x72bc0000,0xd65f03c0)
        self.assertEqual(audit.classify_direct_return(b),
                         "iokit_unsupported_status")
        self.assertEqual(audit.UNSUPPORTED,0xe00002c7)

    def test_different_immediate_not_misclassified(self):
        b=struct.pack("<3I",0x52800020,0x72bc0000,0xd65f03c0)
        self.assertEqual(audit.classify_direct_return(b),
                         "not_an_established_constant")

    def test_missing_ret_not_misclassified(self):
        b=struct.pack("<3I",0x528058e0,0x72bc0000,0xd503201f)
        self.assertEqual(audit.classify_direct_return(b),
                         "not_an_established_constant")

    def test_truncated_original_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"synthetic.bad.macho"
            p.write_bytes(bytes(256))
            r=subprocess.run([sys.executable,str(TOOL),str(p)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_gates_must_disclaim_dynamic_dispatch(self):
        text=TOOL.read_text()
        for item in ("RUNTIME_DISPATCH_OBJECT_PROVEN=NO",
                     "COMMON_MMIO_RESOURCE_INDEX_RESOLVED=NO",
                     "HARDWARE_BLOCKED",
                     "S8000_CTOR_SLOT_1880"):
            self.assertIn(item,text)

    def test_no_original_apple_code_export_or_mmio(self):
        text=TOOL.read_text()
        for term in ("write_bytes(", "open('/dev/mem",
                     "ioremap(", "writel(", "subprocess.run(",
                     "print(hex(ptr", "os.system("):
            self.assertNotIn(term,text)

if __name__=="__main__":
    unittest.main()
