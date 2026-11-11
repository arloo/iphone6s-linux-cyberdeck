"""Synthetic-only ARM64 A9 port-1 inherited virtual-sequence regression tests.

Generates fabricated ARM64 LOAD/BLR/CBZ encodings, NOT original Apple
executable bytes. Never opens any original kernelcache or accesses a phone.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
TOOL=REPO/"tools/n71_s8000_port1_inherited_sequence_gate.py"
spec=importlib.util.spec_from_file_location("n71_shared_port_sequence",TOOL)
s=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(s)

def ldr_x(dst:int,base:int,offset:int)->int:
    assert offset%8==0
    return 0xF9400000|((offset//8)<<10)|(base<<5)|dst

def ldr_w(dst:int,base:int,offset:int)->int:
    assert offset%4==0
    return 0xB9400000|((offset//4)<<10)|(base<<5)|dst

def mov_w(dst:int,value:int)->int:
    return 0x52800000|(value<<5)|dst

def blr(reg:int=8)->int:
    return 0xD63F0000|(reg<<5)

def direct_bl(at:int,target:int)->int:
    assert (target-at)%4==0
    return 0x94000000|(((target-at)//4)&0x3ffffff)

def cond(at:int,target:int,reg:int=0,not_zero:bool=False)->int:
    assert (target-at)%4==0
    op=0x35000000 if not_zero else 0x34000000
    return op|((((target-at)//4)&0x7ffff)<<5)|reg

def fake_shared_port_method()->bytes:
    data=bytearray(s.SHARED_TEXT_LENGTH)
    def setword(off:int,value:int):
        struct.pack_into("<I",data,off,value)
    setword(s.METHOD_START,0xD100C3FF)
    setword(s.METHOD_END-4,0xD65F03C0)
    for (obj,base,idx,vptr,slot_at,slot,val_at,val,call) in s.ROOT_CALLS:
        setword(obj,ldr_x(0,base,2904))
        setword(idx,ldr_w(1,19,168))
        setword(vptr,ldr_x(8,0,0))
        setword(slot_at,ldr_x(8,8,slot))
        if val_at is not None:
            setword(val_at,mov_w(2,val))
        setword(call,blr())
    setword(0x12ac,ldr_x(0,19,2904))
    setword(0x12b8,ldr_w(1,19,168))
    setword(0x12bc,ldr_x(8,0,0))
    setword(0x12c0,ldr_x(8,8,2000))
    setword(0x12c4,mov_w(2,1))
    setword(0x12c8,blr())
    for site,slot in s.OTHER_PORT_VTABLE_CALLS:
        setword(site,ldr_x(8,8,slot))
    setword(0x1290,cond(0x1290,0x127c,0))
    setword(0x12b4,cond(0x12b4,0x12cc,8))
    setword(0x1310,cond(0x1310,0x1328,8,True))
    setword(0x1260,mov_w(0,100))
    setword(0x12cc,ldr_w(0,19,416))
    target=s.SHARED_TEXT_LENGTH
    setword(0x1264,direct_bl(0x1264,target))
    setword(0x12d0,direct_bl(0x12d0,target))
    return bytes(data)

def altered(original:bytes,offset:int,newword:int)->bytes:
    b=bytearray(original)
    struct.pack_into("<I",b,offset,newword)
    return bytes(b)

class TestN71A9Port1OriginalSequence(unittest.TestCase):
    def setUp(self):
        self.code=fake_shared_port_method()

    def rejects(self,new:bytes):
        with self.assertRaises(s.UnverifiedOriginalSequence):
            s.analyze_method(new)

    def test_synthetic_original_order_accepted(self):
        r=s.analyze_method(self.code)
        self.assertEqual(r["root_virtual_slots_in_program_order"],
                         (1968,1984,2008,1992,2000,1968))
        self.assertFalse(r["hardware_register_meanings_proven"])
        self.assertFalse(r["safe_for_writes_or_dma"])

    def test_original_status_poll_back_edge_points_to_same_query(self):
        self.assertEqual(s.target_branch(self.code,0x1290,"cbz",0),0x127c)

    def test_wrong_status_branch_destination_rejected(self):
        self.rejects(altered(self.code,0x1290,cond(0x1290,0x1294,0)))

    def test_wrong_status_branch_register_rejected(self):
        self.rejects(altered(self.code,0x1290,cond(0x1290,0x127c,1)))

    def test_wrong_status_branch_kind_rejected(self):
        self.rejects(altered(self.code,0x1290,cond(0x1290,0x127c,0,True)))

    def test_controller_first_virtual_slot_changed_rejected(self):
        self.rejects(altered(self.code,0x123c,ldr_x(8,8,1976)))

    def test_controller_second_virtual_slot_changed_rejected(self):
        self.rejects(altered(self.code,0x1254,ldr_x(8,8,2008)))

    def test_controller_query_virtual_slot_changed_rejected(self):
        self.rejects(altered(self.code,0x1288,ldr_x(8,8,2016)))

    def test_wrong_port_index_provenance_rejected(self):
        self.rejects(altered(self.code,0x1280,ldr_w(1,19,172)))

    def test_wrong_port_object_rejected(self):
        self.rejects(altered(self.code,0x1248,ldr_x(0,20,2904)))

    def test_wrong_root_pointer_field_rejected(self):
        self.rejects(altered(self.code,0x12d4,ldr_x(0,19,2912)))

    def test_initial_virtual_bool_changed_rejected(self):
        self.rejects(altered(self.code,0x1240,mov_w(2,0)))

    def test_final_virtual_bool_changed_rejected(self):
        self.rejects(altered(self.code,0x12e4,mov_w(2,1)))

    def test_original_fixed_callback_argument_changed_rejected(self):
        self.rejects(altered(self.code,0x1260,mov_w(0,80)))

    def test_original_dynamic_callback_field_changed_rejected(self):
        self.rejects(altered(self.code,0x12cc,ldr_w(0,19,420)))

    def test_second_callback_target_mismatch_rejected(self):
        self.rejects(altered(self.code,0x12d0,direct_bl(0x12d0,s.SHARED_TEXT_LENGTH+4)))

    def test_first_callback_is_not_direct_bl_rejected(self):
        self.rejects(altered(self.code,0x1264,blr()))

    def test_wrong_conditional_controller_skip_rejected(self):
        self.rejects(altered(self.code,0x12b4,cond(0x12b4,0x12d0,8)))

    def test_unexpected_optional_port_call_branch_rejected(self):
        self.rejects(altered(self.code,0x1310,cond(0x1310,0x1320,8,True)))

    def test_extra_or_truncated_executable_rejected(self):
        self.rejects(self.code[:1000])
        self.rejects(self.code+b"\x00\x00\x00\x00")

    def test_ret_and_boundary_provenance_rejected(self):
        self.rejects(altered(self.code,s.METHOD_END-4,0))

    def test_broken_indirect_branch_rejected(self):
        self.rejects(altered(self.code,0x1244,0xD65F03C0))

    def test_single_port_vtable_override_is_static_only(self):
        self.assertIn("CTOR.audit(blob)",TOOL.read_text())
        self.assertIn("non_port3_parent_method_fallback",TOOL.read_text())

    def test_public_tool_requires_private_input_no_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"synthetic.bin"
            p.write_bytes(self.code)
            r=subprocess.run([sys.executable,str(TOOL),str(p)],
                             text=True,capture_output=True,timeout=15)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_no_private_code_dump_or_hardware_io(self):
        text=TOOL.read_text()
        for invalid in ("write_bytes(", "open('/dev/", "ioremap(",
                        "subprocess.run(", "mmap(", "modprobe ",
                        "insmod ", "socket.", "git push", "writel("):
            self.assertNotIn(invalid,text)
        self.assertIn("CALLER_LEVEL_EXPLICIT_POLL_TIMEOUT_PROVEN=NO",text)

if __name__=="__main__":
    unittest.main()
