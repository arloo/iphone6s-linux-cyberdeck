"""Synthetic ARM64 call/stub/GOT tests; no Apple firmware is required."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_kernelcache_pcie_callgate.py"
spec=importlib.util.spec_from_file_location("a9call",TOOL)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)


def encode_adrp_x16(pc: int, target_page: int) -> int:
    assert target_page % 4096 == 0
    delta=(target_page-(pc&~4095))//4096
    assert -(1<<20)<=delta<(1<<20)
    v=delta & 0x1fffff
    return 0x90000010 | ((v&3)<<29) | (((v>>2)&0x7ffff)<<5)


def encode_ldr_x16(offset: int) -> int:
    assert offset % 8 == 0 and 0<=offset<32768
    return 0xf9400210 | ((offset//8)<<10)


class TestA9PcieCallgate(unittest.TestCase):
    def test_bl_forward(self):
        pc=0x10000
        ins=0x94000000 | (0x80//4)
        self.assertEqual(gate.bl_destination(pc,ins),pc+0x80)

    def test_bl_backwards_sign_extension(self):
        pc=0x20000
        ins=0x94000000|((-0x100//4)&0x3ffffff)
        self.assertEqual(gate.bl_destination(pc,ins),pc-0x100)

    def test_other_opcodes_not_treated_as_calls(self):
        self.assertIsNone(gate.bl_destination(0x1000,0x14000001))
        self.assertIsNone(gate.bl_destination(0x1000,0xd65f03c0))

    def test_stub_forward_page_address_and_scaled_load(self):
        pc=0x100800
        target=0x102d40
        ins=encode_adrp_x16(pc,target&~4095)
        ldr=encode_ldr_x16(target&4095)
        self.assertEqual(gate.stub_got_address(pc,ins,ldr,0xd61f0200),
                         target)

    def test_stub_backward_page_signed_adrp(self):
        pc=0x300200
        target=0x2f0e10
        self.assertEqual(gate.stub_got_address(
            pc,encode_adrp_x16(pc,target&~4095),
            encode_ldr_x16(target&4095),0xd61f0200),target)

    def test_stub_wrong_register_fails(self):
        pc=0x10000
        with self.assertRaises(gate.RejectedGraph):
            gate.stub_got_address(
                pc,0x90000011,encode_ldr_x16(0),0xd61f0200)

    def test_stub_ldr_wrong_register_fails(self):
        pc=0x10000
        with self.assertRaises(gate.RejectedGraph):
            gate.stub_got_address(
                pc,encode_adrp_x16(pc,0x10000),0xf9400211,0xd61f0200)

    def test_stub_br_retarget_fails(self):
        pc=0x10000
        with self.assertRaises(gate.RejectedGraph):
            gate.stub_got_address(
                pc,encode_adrp_x16(pc,0x10000),
                encode_ldr_x16(0),0xd61f0000)

    def test_file_offset_rejects_out_of_bounds(self):
        main={"__PLK_DATA_CONST":{"vm":0x10000,"offset":0x1000,
                                   "filesize":0x1000}}
        self.assertEqual(gate.file_offset(
            main,"__PLK_DATA_CONST",0x10100,8,0x3000),0x1100)
        with self.assertRaises(gate.RejectedGraph):
            gate.file_offset(main,"__PLK_DATA_CONST",0x10fff,8,0x3000)

    def test_target_classification_is_aggregate_only(self):
        rs=[(gate.A9,0x1000,0x100),(gate.SHARED,0x2000,0x100),
            (gate.EMBEDDED,0x3000,0x100),
            (gate.IOPCI,0x4000,0x100)]
        main={"__TEXT_EXEC":{"vm":0x5000,"filesize":0x1000},
              "__PLK_TEXT_EXEC":{"vm":0x1000,"filesize":0x4000}}
        self.assertEqual(gate.target_category(0x2050,rs,main),
                         "a9_s800x_shared")
        self.assertEqual(gate.target_category(0x3030,rs,main),
                         "apple_embedded_pcie")
        self.assertEqual(gate.target_category(0x4080,rs,main),
                         "io_pci_family")
        self.assertEqual(gate.target_category(0x5080,rs,main),
                         "other_kernel_or_kext")
        with self.assertRaises(gate.RejectedGraph):
            gate.target_category(0x7000,rs,main)

    def test_short_invalid_kernelcache_fails_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            p=Path(dirname)/"fake.macho"
            p.write_bytes(bytes(100))
            r=subprocess.run([sys.executable,str(TOOL),str(p)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_reader_never_exports_code_or_addresses(self):
        src=TOOL.read_text()
        for forbidden in ("write_bytes(", "f.write(", "subprocess.",
                          "os.system(", "mmap(", "ptrace(", "/dev/mem",
                          "print(hex(", ".hexdigest(", "call_targets="):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
