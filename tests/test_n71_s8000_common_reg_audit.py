"""Synthetic bounded AArch64 switch-table tests for S8000 six-register map.

Tests do NOT contain Apple binary images, proprietary function bodies, firmware,
or hardware addresses; they fabricate instruction encodings from ARM64 rules.
"""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"tools/n71_s8000_common_reg_audit.py"
spec=importlib.util.spec_from_file_location("s8000_regs", PATH)
audit=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(audit)

def fixture() -> bytearray:
    b=bytearray(0x900)
    def put(offset,value):
        struct.pack_into("<I",b,offset,value)
    # Synthetic ARM64 selector, with checked argument/port guards.
    for pos,insn in (
        (0x7e8,0xaa0203f3), (0x7ec,0xaa0103f4),
        (0x7f0,0x94000001), (0x7f4,0x6b13001f),
        (0x7f8,0x54000009), (0x7fc,0x7100169f),
        (0x800,0x54000008),
        (0x804,audit.a64_movz_w0(0x24)),
        (0x808,0x2a1403e8),
        (0x80c,0x90000009), (0x810,0x91223129),
        (0x814,0x1000000a), (0x818,0xb8a8792b),
        (0x81c,0x8b0b014a), (0x820,0xd61f0140),
        (0x824,audit.a64_movz_w0(0x2c)),
        (0x828,0x14000001),
        (0x864,0xd65f03c0),
    ):
        put(pos,insn)
    targets=(0x858,0x824,0x82c,0x838,0x844,0x850)
    struct.pack_into("<6i",b,0x88c,*[x-0x814 for x in targets])
    for case,base in zip(targets[2:],(0x100,0x114,0x124,0x12c)):
        put(case,audit.a64_lsl_w8_w19_7())
        put(case+4,audit.a64_add_w0_w8_imm(base))
        if case!=0x850:put(case+8,0x14000001)
    return b


class TestA9S8000CommonRegs(unittest.TestCase):
    def reject(self,b):
        with self.assertRaises(audit.UnverifiedCode):
            audit.extract_pinned_common_offset_map(bytes(b))

    def test_six_cases_accept_original_s8000_formulas(self):
        results=audit.extract_pinned_common_offset_map(bytes(fixture()))
        self.assertEqual(results,((0x24,0),(0x2c,0),
                         (0x100,0x80),(0x114,0x80),
                         (0x124,0x80),(0x12c,0x80)))

    def test_port1_has_four_separate_offsets(self):
        regs=audit.extract_pinned_common_offset_map(bytes(fixture()))
        self.assertEqual([x+y for x,y in regs],
                         [0x24,0x2c,0x180,0x194,0x1a4,0x1ac])

    def test_truncated_code_rejected(self):
        self.reject(fixture()[:0x808])

    def test_wrong_port_argument_register_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x7e8,0xaa0303f3)
        self.reject(b)

    def test_missing_port_count_check_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x7f0,0xd503201f)
        self.reject(b)

    def test_changed_port_guard_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x7f4,0x6b13003f)
        self.reject(b)

    def test_changed_register_id_bounds_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x7fc,0x71001a9f)
        self.reject(b)

    def test_modified_jump_table_target_rejected(self):
        b=fixture()
        struct.pack_into("<i",b,0x88c+4*3,0x838-0x814+4)
        self.reject(b)

    def test_modified_shared_fixed_offset_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x824,audit.a64_movz_w0(0x34))
        self.reject(b)

    def test_modified_port_stride_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x838,0x53186268)
        self.reject(b)

    def test_modified_port_relative_base_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x848,audit.a64_add_w0_w8_imm(0x130))
        self.reject(b)

    def test_wrong_epilogue_rejected(self):
        b=fixture()
        struct.pack_into("<I",b,0x864,0xd503201f)
        self.reject(b)

    def test_invalid_private_input_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"not_kernelcache.bin"
            path.write_bytes(bytes(fixture()))
            r=subprocess.run([sys.executable,str(PATH),str(path)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("AUDIT_BLOCKED",r.stderr)

    def test_no_memory_access_or_binary_export_capability(self):
        source=PATH.read_text()
        for forbidden in ("write_bytes(","f.write(","os.system(",
                          "subprocess.run(", "ioremap(","/dev/mem",
                          "print(hex(data", "export_apple_code"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,source)

if __name__=="__main__":
    unittest.main()
