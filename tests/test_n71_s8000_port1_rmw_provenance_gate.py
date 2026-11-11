"""Synthetic-only N71/S8000 shared-root register RMW operation tests.

Constructs artificial AArch64 instruction words from independent instruction
helpers and expected operation relationships. No original Apple executable
bytes are included; the original Mach-O is read only by the separate gate.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"tools/n71_s8000_port1_rmw_provenance_gate.py"
s=importlib.util.spec_from_file_location("n71_rmw_tested",PATH)
m=importlib.util.module_from_spec(s)
assert s and s.loader
s.loader.exec_module(m)

def synthetic_ldr_x(dst:int,base:int,offset:int)->int:
    assert offset%8==0 and offset<32768
    return 0xF9400000|((offset//8)<<10)|(base<<5)|dst

def synthetic_mov_w(dst:int,imm:int)->int:
    assert 0<=imm<65536
    return 0x52800000 | (imm<<5) | dst

def branch(at:int,to:int,opcode:int)->int:
    assert (to-at)%4==0
    return opcode | (((to-at)//4)&0x3ffffff)

def cbz(at:int,to:int,reg:int)->int:
    return 0x34000000 | ((((to-at)//4)&0x7ffff)<<5)|reg

def tbnz(at:int,to:int,reg:int,bit:int)->int:
    return 0x37000000 | (bit<<19) | ((((to-at)//4)&0x3fff)<<5)|reg

def fake_shared_root_code()->bytes:
    x=bytearray(18552)
    def write(at:int,value:int)->None:struct.pack_into("<I",x,at,value)
    setup=[
       # method, ID, selector, read, write, masked bit, combine
       (1968,4,0x6ac,0x6bc,0x6dc,0x121F7808,0x2A090102),
       (1984,3,0x5f4,0x608,0x624,0x121F7808,0x2A150102),
       (1992,2,0x48c,0x49c,0x4c4,0x12177808,0x2A090102),
       (2000,2,0x504,0x514,0x53c,0x120B7808,0x2A090102),
    ]
    mask_site={1968:0x6cc,1984:0x618,1992:0x4ac,2000:0x524}
    comb_site={1968:0x6d4,1984:0x61c,1992:0x4bc,2000:0x534}
    for slot,regid,select,read,wr,mask,compose in setup:
        write(select,synthetic_mov_w(1,regid))
        write(select-4,synthetic_ldr_x(8,8,2016))
        write(read,synthetic_ldr_x(8,8,1808))
        write(wr,synthetic_ldr_x(8 if slot==1984 else 3,8,1816))
        write(mask_site[slot],mask)
        write(comb_site[slot],compose)
    write(0x6d0,0x52000269)
    write(0x5e0,0xAA0203F5)
    write(0x634,cbz(0x634,0x678,21))
    write(0x644,synthetic_mov_w(1,1))
    write(0x63c,synthetic_ldr_x(8,8,2016))
    write(0x658,synthetic_ldr_x(8,8,1808))
    write(0x668,tbnz(0x668,0x678,0,4))
    write(0x66c,synthetic_mov_w(0,10))
    write(0x674,branch(0x674,0x654,0x14000000))
    write(0x670,branch(0x670,0x4878,0x94000000))
    write(0x1264,branch(0x1264,0x4878,0x94000000))
    write(0x4b0,0x7100027F)
    write(0x4b4,synthetic_mov_w(9,0x100))
    write(0x4b8,0x1A9F1129)
    write(0x528,0x7100027F)
    write(0x52c,0x52A00209)
    write(0x530,0x1A9F1129)
    write(0x5f8,0xAA1403E2)
    return bytes(x)

def alter(source:bytes,site:int,word:int)->bytes:
    b=bytearray(source)
    struct.pack_into("<I",b,site,word)
    return bytes(b)

class TestN71OriginalA9Port1RMW(unittest.TestCase):
    def setUp(self):
        self.data=fake_shared_root_code()

    def bad(self,off,insn):
        with self.assertRaises(m.UnprovenPortRegisters):
            m.audit_rmw_methods(alter(self.data,off,insn))

    def test_synthetic_method_collection_validates(self):
        r=m.audit_rmw_methods(self.data)
        self.assertEqual(r["rmw_slots"],(1968,1984,1992,2000))
        self.assertEqual(r["selector_ids"],(4,3,2,2))
        self.assertEqual(r["bit_indices"],(0,0,8,20))
        self.assertEqual(r["shared_status_bit"],4)
        self.assertFalse(r["hardware_safe"])

    def test_first_bit0_operation_wrong_regid(self):
        self.bad(0x6ac,synthetic_mov_w(1,3))

    def test_second_bit0_operation_wrong_regid(self):
        self.bad(0x5f4,synthetic_mov_w(1,2))

    def test_third_bit8_operation_wrong_regid(self):
        self.bad(0x48c,synthetic_mov_w(1,5))

    def test_fourth_bit20_operation_wrong_regid(self):
        self.bad(0x504,synthetic_mov_w(1,4))

    def test_wrong_root_register_id_selector(self):
        self.bad(0x6a8,synthetic_ldr_x(8,8,1888))

    def test_wrong_root_read32_target(self):
        self.bad(0x49c,synthetic_ldr_x(8,8,1816))

    def test_wrong_root_write32_target(self):
        self.bad(0x53c,synthetic_ldr_x(3,8,1808))

    def test_slot1968_wrong_bit_mask(self):
        self.bad(0x6cc,0x12177808)

    def test_slot1984_wrong_bit_mask(self):
        self.bad(0x618,0x120B7808)

    def test_slot1992_wrong_bit_mask(self):
        self.bad(0x4ac,0x121F7808)

    def test_slot2000_wrong_bit_mask(self):
        self.bad(0x524,0x12177808)

    def test_slot1968_changed_bit_polarity(self):
        self.bad(0x6d0,0)

    def test_slot1984_changed_value_forwarding(self):
        self.bad(0x5e0,0)

    def test_slot1984_global_gate_disabled(self):
        self.bad(0x634,cbz(0x634,0x634,21))

    def test_slot1984_global_selector_not_id1(self):
        self.bad(0x644,synthetic_mov_w(1,0))

    def test_slot1984_global_status_bit_changed(self):
        self.bad(0x668,tbnz(0x668,0x678,0,5))

    def test_slot1984_global_poll_exit_changed(self):
        self.bad(0x668,tbnz(0x668,0x66c,0,4))

    def test_slot1984_global_poll_backedge_changed(self):
        self.bad(0x674,branch(0x674,0x650,0x14000000))

    def test_slot1984_wrong_delay_constant(self):
        self.bad(0x66c,synthetic_mov_w(0,20))

    def test_slot1984_different_delay_helper(self):
        self.bad(0x670,branch(0x670,0x4874,0x94000000))

    def test_slot1992_changed_set_bit(self):
        self.bad(0x4b4,synthetic_mov_w(9,1))

    def test_slot2000_changed_set_bit(self):
        self.bad(0x52c,synthetic_mov_w(9,1))

    def test_slot1992_wrong_boolean_check(self):
        self.bad(0x4b0,0)

    def test_slot2000_wrong_boolean_select(self):
        self.bad(0x530,0)

    def test_wrong_binary_extent_rejected(self):
        with self.assertRaises(m.UnprovenPortRegisters):
            m.audit_rmw_methods(self.data[:1000])

    def test_original_a9_root_vtable_targets_must_be_valid(self):
        text=PATH.read_text()
        self.assertIn("CTOR.read_data_pointer(blob,main,root",text)
        self.assertIn("COMMON.inspect_macho(blob)",text)
        self.assertIn("STAT.inspect(blob,adt)",text)

    def test_physical_mmio_and_bluetooth_not_implied(self):
        text=PATH.read_text()
        self.assertIn("PROVIDER_MEMORY_ORDER_AND_GLOBAL_CROSS_PORT_EFFECTS_PROVEN=NO",text)
        self.assertIn("S8000_PCIE_DART1_AND_WIFI_HARDWARE_INIT_AUTHORIZED=NO",text)

    def test_untrusted_private_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"fake.macho";a.write_bytes(self.data)
            b=Path(tmp)/"fake.adt";b.write_bytes(b"fake")
            proc=subprocess.run([sys.executable,str(PATH),str(a),str(b)],
                                capture_output=True,text=True,timeout=10)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn("FAIL_CLOSED",proc.stderr)

    def test_no_live_hardware_paths_or_private_apple_code_export(self):
        text=PATH.read_text()
        for dangerous in ("write_bytes(","subprocess.run(","mmap(","readl(",
                          "writel(","ioremap(","insmod ","modprobe ",
                          "socket.","/dev/mem","git push"):
            self.assertNotIn(dangerous,text)

if __name__=="__main__":
    unittest.main()
