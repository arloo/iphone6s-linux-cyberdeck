"""Synthetic-only N71 S8000 ROOT controller resource-index regression tests.

No Apple copyrighted executable body, IPSW, per-device ADT or firmware.
All ARM64 instruction words in fixtures are individually constructed patterns.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s8000_root_resource_gate.py"
spec=importlib.util.spec_from_file_location("a9root",SCRIPT)
g=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)

def adrp_x8(pc:int,page:int)->int:
    assert page%4096==0
    delta=(page-(pc&~4095))//4096
    assert -(1<<20)<=delta<(1<<20)
    value=delta&0x1fffff
    return 0x90000008|((value&3)<<29)|(((value>>2)&0x7ffff)<<5)

def ldr_x8_from_x8(offset:int)->int:
    assert offset%8==0 and offset<32768
    return 0xF9400108|((offset//8)<<10)

def put32(b:bytearray,at:int,value:int):
    struct.pack_into("<I",b,at,value)

def synthetic_controller():
    main={"__PLK_DATA_CONST":{"vm":0x40000,"offset":0,"filesize":0x8000}}
    blob=bytearray(0x8000)
    modules={
       "embedded":{"vm":0x100000,"vptr":0x41000,"code":bytearray(46924)},
       "shared":{"vm":0x110000,"vptr":0x42000,"code":bytearray(18552)},
       "a9":{"vm":0x120000,"vptr":0x43000,"code":bytearray(2928)},
    }
    def ptr(mod,slot,target):
        addr=modules[mod]["vptr"]+slot
        struct.pack_into("<Q",blob,addr-0x40000,target)
    base=modules["embedded"];common=modules["shared"];a9=modules["a9"]
    ptr("embedded",688,base["vm"]+0x1A58)
    ptr("shared",688,common["vm"]+0x130)
    ptr("a9",688,common["vm"]+0x130)
    ptr("shared",1496,common["vm"]+0x218)
    ptr("a9",1496,a9["vm"]+0x510)
    ptr("a9",2016,a9["vm"]+0x7D8)
    ptr("a9",1856,base["vm"]+0x2CC4)
    ptr("a9",1880,common["vm"]+0xE8)
    ptr("a9",1888,common["vm"]+0x108)
    put32(base["code"],0x2CC4,0x52800000)
    put32(base["code"],0x2CC8,0xD65F03C0)
    for at,word in {
        0xE8:0xA9BF7BFD,0xF0:0x94001287,
        0xF4:0x52800028,0xF8:0x331F7808,
        0xFC:0xAA0803E0,0x104:0xD65F03C0,
        0x114:0xAA0103F3,0x118:0x9400127D,
        0x11C:0x0B000668,0x120:0x11000900,0x12C:0xD65F03C0,
        0x1EC:adrp_x8(common["vm"]+0x1EC,0x40000),
        0x1F0:ldr_x8_from_x8(0x200),
        0x1F4:ldr_x8_from_x8(704),
        0x1F8:0xAA1403E0,
        0x1FC:0xAA1303E1,
        0x200:0xD63F0100,
    }.items():put32(common["code"],at,word)
    struct.pack_into("<Q",blob,0x200,base["vptr"]-16)
    for at,word in {
        0x52C:0xF9400008,0x530:ldr_x8_from_x8(1888),
        0x534:0x52800001,0x538:0xD63F0100,
        0x53C:0xAA0003E1,0x540:0xF9400268,
        0x544:ldr_x8_from_x8(976),0x548:0xAA1303E0,
        0x54C:0x52800002,0x550:0xD63F0100,
        0x554:0xF900E280,
    }.items():put32(a9["code"],at,word)
    for mod in modules.values():
        mod["code"]=bytes(mod["code"])
    return bytes(blob),main,modules

class TestA9RootResourceAudit(unittest.TestCase):
    def test_four_port_resource_indices(self):
        self.assertEqual(g.root_resource_indices(4),(0,9,10))

    def test_second_phy_resource_formula(self):
        self.assertEqual(g.root_resource_indices(4,1),(0,9,11))

    def test_reject_other_port_count(self):
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.root_resource_indices(3)

    def test_reject_invalid_phy_argument(self):
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.root_resource_indices(4,8)

    def test_decode_arm64_ldr(self):
        self.assertEqual(g.ldr_from_reg(ldr_x8_from_x8(1888),8,8),1888)
        self.assertEqual(g.ldr_from_reg(ldr_x8_from_x8(976),8,8),976)

    def test_wrong_ldr_base_rejected(self):
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.ldr_from_reg(0xF9400008,8,8)

    def test_wrong_ldr_destination_rejected(self):
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.ldr_from_reg(0xF9400101,8,8)

    def test_root_start_chain_synthetic(self):
        blob,main,mods=synthetic_controller()
        g.checked_root_start(blob,main,mods)

    def test_original_resource_formula_shapes_synthetic(self):
        blob,main,mods=synthetic_controller()
        g.verify_index_methods(blob,main,mods)

    def test_s8000_has_distinct_root_configuration_override(self):
        blob,main,mods=synthetic_controller()
        ptr=lambda name,slot:g.G.read_data_pointer(
            blob,main,mods[name]["vptr"]+slot)
        self.assertNotEqual(ptr("a9",1496),ptr("shared",1496))
        self.assertEqual(ptr("a9",688),ptr("shared",688))

    def test_wrong_super_start_vtable_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(blob)
        struct.pack_into("<Q",b,0x200,mods["a9"]["vptr"]-16)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.checked_root_start(bytes(b),main,mods)

    def test_wrong_root_start_dispatch_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(blob)
        struct.pack_into("<Q",b,mods["a9"]["vptr"]+688-0x40000,
                         mods["a9"]["vm"]+0x510)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.checked_root_start(bytes(b),main,mods)

    def test_wrong_phy_selector_offset_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(mods["a9"]["code"])
        put32(b,0x530,ldr_x8_from_x8(1880))
        mods["a9"]["code"]=bytes(b)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.verify_index_methods(blob,main,mods)

    def test_wrong_phy_map_provider_offset_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(mods["a9"]["code"])
        put32(b,0x544,ldr_x8_from_x8(984))
        mods["a9"]["code"]=bytes(b)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.verify_index_methods(blob,main,mods)

    def test_modified_common_port_count_formula_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(mods["shared"]["code"])
        put32(b,0xF8,0x331E7808)
        mods["shared"]["code"]=bytes(b)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.verify_index_methods(blob,main,mods)

    def test_changed_config_zero_index_method_rejected(self):
        blob,main,mods=synthetic_controller()
        b=bytearray(mods["embedded"]["code"])
        put32(b,0x2CC4,0x52800020)
        mods["embedded"]["code"]=bytes(b)
        with self.assertRaises(g.G.UnqualifiedHardware):
            g.verify_index_methods(blob,main,mods)

    def test_cli_invalid_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"fake.macho"
            f.write_bytes(b"not-a-kernel")
            r=subprocess.run([sys.executable,str(SCRIPT),str(f),str(f)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_output_fails_closed_for_physical_assumptions(self):
        src=SCRIPT.read_text()
        for token in (
           "ADT_RESOURCE_ORDER_EQUALS_PROVIDER_ORDER_PROVEN=NO",
           "S8000_PORT1_CLOCK_RESET_DART1_DMA_VERIFIED=NO",
           "HARDWARE_BLOCKED"):
            self.assertIn(token,src)

    def test_no_device_register_access_or_executable_export(self):
        src=SCRIPT.read_text()
        for forbidden in ("write_bytes(", "subprocess.run(", "mmap(",
                          "open('/dev/mem", "ioremap(", "readl(",
                          "writel(", "os.system(", "export_binary("):
            self.assertNotIn(forbidden,src)

if __name__=="__main__":
    unittest.main()
