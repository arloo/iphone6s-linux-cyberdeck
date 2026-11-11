"""Synthetic ARM64/unit-memory regression of S8000 constructor hierarchy.

No Apple Mach-O, original code body, private ADT or device data is embedded.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s8000_constructor_chain_gate.py"
spec=importlib.util.spec_from_file_location("n71_ctor_gate",SCRIPT)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def adr_x8(pc:int, dest_page:int)->int:
    assert dest_page%4096==0
    pages=(dest_page-(pc&~4095))//4096
    assert -(1<<20)<=pages<(1<<20)
    bits=pages&0x1fffff
    return 0x90000008 | ((bits&3)<<29) | (((bits>>2)&0x7ffff)<<5)

def vptr_add_x8(n:int)->int:
    assert 0<=n<4096
    return 0x91000108 | (n<<10)

def synthetic_code():
    # Fabricate individual ARM64 branch/guard instructions only.
    code=bytearray(0x300)
    for off,value in {
        0x288:0xaa0003f3, 0x29c:0x71000c1f,
        0x2a0:0x54000081, 0x2a4:0xb940aa68,
        0x2a8:0x71000d1f, 0x2ac:0x54000100,
        0x2b8:0xf9439501, 0x2bc:0xaa1303e0,
        0x2c8:0xd61f0020,
    }.items():
        struct.pack_into("<I",code,off,value)
    return code

def synthetic_segment():
    buf=bytearray(0x6000)
    # The data segment maps at 0x2000, stored at offset 0x800.
    main={"__PLK_DATA_CONST":{"vm":0x2000,"offset":0x800,
                              "filesize":0x3000}}
    return buf,main

def pointer(blob,main,addr,value):
    d=main["__PLK_DATA_CONST"]
    struct.pack_into("<Q",blob,d["offset"]+addr-d["vm"],value)

class TestS8000ConstructorChain(unittest.TestCase):
    def test_constructor_call_forward(self):
        pc=0x11000
        self.assertEqual(
            gate.bl_destination(pc,0x94000000 | (0x80//4)),pc+0x80)

    def test_constructor_call_backward_sign_extended(self):
        pc=0x11000
        self.assertEqual(gate.bl_destination(
            pc,0x94000000|((-0x100//4)&0x3ffffff)),pc-0x100)

    def test_non_bl_rejected(self):
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.bl_destination(0x11000,0x14000000)

    def test_vtable_register_assignment(self):
        pc=0x14004
        addr=0x160d0
        self.assertEqual(gate.adrp_add_str_vptr(
            pc,adr_x8(pc,addr&~4095),vptr_add_x8(addr&4095),
            0xf9000008),addr)

    def test_vtable_adrp_backward_signed(self):
        pc=0x40004
        addr=0x28020
        self.assertEqual(gate.adrp_add_str_vptr(
            pc,adr_x8(pc,addr&~4095),vptr_add_x8(addr&4095),
            0xf9000008),addr)

    def test_vptr_unexpected_dest_register_fails(self):
        pc=0x11000
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.adrp_add_str_vptr(
                pc,0x90000009,vptr_add_x8(0),0xf9000008)

    def test_vptr_wrong_object_store_fails(self):
        pc=0x11000
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.adrp_add_str_vptr(
                pc,adr_x8(pc,0x11000),vptr_add_x8(0),0xf9000268)

    def test_vtable_delta_is_deterministic(self):
        data,main=synthetic_segment()
        first=0x2400
        second=0x3000
        for slot in range(0,2048,8):
            pointer(data,main,first+slot,0x10000+slot)
            pointer(data,main,second+slot,0x10000+slot)
        for slot in gate.EXPECTED_CHANGED:
            pointer(data,main,second+slot,0x20000+slot)
        self.assertEqual(
            gate.vtable_differences(bytes(data),main,first,second),
            list(gate.EXPECTED_CHANGED))

    def test_vtable_unexpected_difference_detected(self):
        data,main=synthetic_segment()
        first=0x2400
        second=0x3000
        for slot in range(0,2048,8):
            pointer(data,main,first+slot,0x10000+slot)
            pointer(data,main,second+slot,0x10000+slot)
        pointer(data,main,second+1840,0x20200)
        differences=gate.vtable_differences(bytes(data),main,first,second)
        self.assertNotEqual(tuple(differences),gate.EXPECTED_CHANGED)
        self.assertIn(1840,differences)

    def test_port3_specific_conditional_shape(self):
        gate.port3_check(bytes(synthetic_code()))

    def test_port3_bne_guard_cannot_be_removed(self):
        data=synthetic_code()
        struct.pack_into("<I",data,0x2a0,0x14000008)
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.port3_check(bytes(data))

    def test_port3_second_check_cannot_be_removed(self):
        data=synthetic_code()
        struct.pack_into("<I",data,0x2a8,0x7100091f)
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.port3_check(bytes(data))

    def test_port3_parent_fallback_resolves_inherited_slot(self):
        data,main=synthetic_segment()
        code=synthetic_code()
        pc=0x10000+0x2b0
        global_ptr=0x2800
        struct.pack_into("<I",code,0x2b0,adr_x8(pc,0x2000))
        struct.pack_into("<I",code,0x2b4,
                         0xf9400108 | (((global_ptr&4095)//8)<<10))
        parent_vptr=0x3000
        pointer(data,main,global_ptr,parent_vptr-16)
        pointer(data,main,parent_vptr+1816,0x40000)
        self.assertTrue(gate.static_inherited_fallback(
            bytes(data),main,bytes(code),0x10000,parent_vptr))

    def test_wrong_vtable_parent_pointer_detected(self):
        data,main=synthetic_segment()
        code=synthetic_code()
        pc=0x10000+0x2b0
        global_ptr=0x2800
        struct.pack_into("<I",code,0x2b0,adr_x8(pc,0x2000))
        struct.pack_into("<I",code,0x2b4,
                         0xf9400108 | (((global_ptr&4095)//8)<<10))
        pointer(data,main,global_ptr,0x3000)
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.static_inherited_fallback(
                bytes(data),main,bytes(code),0x10000,0x3000)

    def test_truncated_pointer_table_fails_closed(self):
        data,main=synthetic_segment()
        with self.assertRaises(gate.UnqualifiedHardware):
            gate.read_data_pointer(bytes(data),main,0x4fff)

    def test_invalid_input_cli_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"fake.macho"
            p.write_bytes(b"broken image")
            r=subprocess.run([sys.executable,str(SCRIPT),str(p)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_no_binary_dump_or_mmio_permissions(self):
        src=SCRIPT.read_text()
        for prohibited in ("write_bytes(", "subprocess.run(",
                           "mmap(", "open('/dev/mem", "writel(",
                           "readl(","os.system(", "export_kernelcache"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited,src)

    def test_success_disclaims_runtime_and_dma(self):
        src=SCRIPT.read_text()
        for required in ("HARDWARE_BLOCKED", "RUNTIME_PCIE_INIT_AND_WLAN_ASSOCIATION_PROVEN=NO",
                         "NON_PORT3_SHARED_METHOD_FALLBACK=VERIFIED_STATIC"):
            self.assertIn(required,src)

if __name__=="__main__":
    unittest.main()
