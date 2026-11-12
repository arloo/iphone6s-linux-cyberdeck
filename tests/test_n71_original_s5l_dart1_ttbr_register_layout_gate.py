"""Synthetic adversarial regression for original Apple N71 DART1 TTBR layout.

Never uses or redistributes private Apple Mach-O, original ADT, device
identifiers, WLAN calibration, radio firmware or original IORegistry.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_original_s5l_dart1_ttbr_register_layout_gate.py"
SPEC=importlib.util.spec_from_file_location("n71_original_ttbr_test",TOOL)
assert SPEC and SPEC.loader
G=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)

def original_code():
    b=bytearray(G.ORIGINAL.EXPECTED_LENGTHS[G.ORIGINAL.S5L])
    for offset,value in G.CLEAR_WORDS.items():
        struct.pack_into("<I",b,offset,value)
    return bytes(b)

def synthetic_linux_source():
    return r"""
#define DART_S5L8960X_TTBR 0x40
#define DART_S5L8960X_TCR 0xc
#define DART_TTBR(dart, sid, idx) ((dart)->hw->ttbr + \
                (((dart)->hw->ttbr_count * (sid)) << 2) + \
                ((idx) << 2))
static const struct apple_dart_hw apple_dart_hw_s5l8960x = {
 .type = DART_S5L8960X,
 .max_sid_count = 4,
 .ttbr = DART_S5L8960X_TTBR,
 .ttbr_count = 4,
};
static void apple_dart_hw_clear_ttbr(struct apple_dart_stream_map *s,u8 idx)
{
 dart->regs + DART_TTBR(dart, sid, idx);
}
static void apple_dart_hw_set_ttbr(struct apple_dart_stream_map *s,
                                   u8 idx, phys_addr_t paddr)
{
 dart->regs + DART_TTBR(dart, sid, idx);
}
static bool apple_n71_s8000_wlan_dart1_blocked(struct platform_device *pdev)
{
 return overlaps(0x602008000ULL);
}
static int apple_dart_probe(struct platform_device *pdev)
{
 if (apple_n71_s8000_wlan_dart1_blocked(pdev)) {
  return -EOPNOTSUPP;
 }
 dart->regs = devm_platform_get_and_ioremap_resource(pdev,0,&res);
}
"""+("/* synthetic padding, not original Apple or Linux code */\n"*300)

class TestOriginalS5LTTBRLayout(unittest.TestCase):
    def test_original_native_4x4_clear_instruction_sequence(self):
        self.assertTrue(
            G.original_s5l_clear_valid(original_code(),0x1b6c))

    def test_original_exact_vtable_target_required(self):
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.original_s5l_clear_valid(original_code(),0x1c00)

    def test_original_wrong_arm64_length_fails(self):
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.original_s5l_clear_valid(original_code()[:-4],0x1b6c)

    def test_each_original_native_instruction_mutation_fails(self):
        original=original_code()
        for offset in G.CLEAR_WORDS:
            with self.subTest(offset=hex(offset)):
                changed=bytearray(original)
                changed[offset]^=1
                with self.assertRaises(G.TTBRLayoutNotProven):
                    G.original_s5l_clear_valid(changed,0x1b6c)

    def test_synthetic_linux_source_matches_real_layout_contract(self):
        self.assertTrue(G.check_linux_source(synthetic_linux_source()))

    def test_synthetic_tcr_base_must_remain_original(self):
        bad=synthetic_linux_source().replace(
            "DART_S5L8960X_TCR 0xc","DART_S5L8960X_TCR 0x10")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_synthetic_ttbr_base_mutation_rejected(self):
        bad=synthetic_linux_source().replace(
            "DART_S5L8960X_TTBR 0x40","DART_S5L8960X_TTBR 0x44")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_synthetic_ttbr_count_changed_rejected(self):
        bad=synthetic_linux_source().replace(
            ".ttbr_count = 4,",".ttbr_count = 8,")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_synthetic_sid_count_changed_rejected(self):
        bad=synthetic_linux_source().replace(
            ".max_sid_count = 4,",".max_sid_count = 8,")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_stream_stride_mutation_rejected(self):
        bad=synthetic_linux_source().replace(
            "((dart)->hw->ttbr_count * (sid)) << 2",
            "((dart)->hw->ttbr_count * (sid)) << 3")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_table_slot_stride_mutation_rejected(self):
        bad=synthetic_linux_source().replace(
            "((idx) << 2)","((idx) << 3)")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_linux_source_without_guard_rejected(self):
        bad=synthetic_linux_source().replace(
            "apple_n71_s8000_wlan_dart1_blocked",
            "unsafe_auto_probe")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_linux_source_without_pre_mmio_probe_refusal_rejected(self):
        bad=synthetic_linux_source().replace(
            "return -EOPNOTSUPP;","return 0;")
        with self.assertRaises(G.TTBRLayoutNotProven):
            G.check_linux_source(bad)

    def test_s5l_ttbr_offsets_all_16_distinct(self):
        slots=G.validate_disjoint_registers()
        self.assertEqual(len(slots),16)
        self.assertEqual(len(set(slots)),16)
        self.assertEqual(slots[0],0x40)
        self.assertEqual(slots[-1],0x7c)

    def test_mapper0_ttbr_offset_exact(self):
        self.assertEqual([G.offset_for(0,i) for i in range(4)],
                         [0x40,0x44,0x48,0x4c])

    def test_other_streams_ttbr_offsets_exact(self):
        self.assertEqual([G.offset_for(1,i) for i in range(4)],
                         [0x50,0x54,0x58,0x5c])
        self.assertEqual([G.offset_for(2,i) for i in range(4)],
                         [0x60,0x64,0x68,0x6c])
        self.assertEqual([G.offset_for(3,i) for i in range(4)],
                         [0x70,0x74,0x78,0x7c])

    def test_ttbr_slots_never_overlap_packed_tcr(self):
        for i in G.validate_disjoint_registers():
            self.assertFalse(i<=0xc<i+4)

    def test_invalid_sid_zero_below_bounds_rejected(self):
        for idx in (-1,4,256):
            with self.subTest(idx=idx):
                with self.assertRaises(G.TTBRLayoutNotProven):
                    G.offset_for(idx,0)

    def test_invalid_table_index_rejected(self):
        for idx in (-1,4,128):
            with self.subTest(idx=idx):
                with self.assertRaises(G.TTBRLayoutNotProven):
                    G.offset_for(0,idx)

    def test_noninteger_index_rejected(self):
        for idx in (0.0,"0",None):
            with self.subTest(idx=str(idx)):
                with self.assertRaises(G.TTBRLayoutNotProven):
                    G.offset_for(idx,0)

    def test_corrupt_original_macho_failure_private_path_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"SYNTHETIC_PRIVATE_DART_SOURCE.dat"
            p.write_bytes(b"nonsense")
            result=subprocess.run(
                [sys.executable,str(TOOL),str(p),str(p),str(p)],
                text=True,capture_output=True,timeout=20)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("FAIL_CLOSED",result.stderr)
            self.assertNotIn(str(p),result.stderr+result.stdout)

    def test_symlink_original_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            real=Path(folder)/"a"
            real.write_bytes(b"ORIGINAL_SYNTHETIC")
            link=Path(folder)/"b"
            link.symlink_to(real)
            with self.assertRaises(G.TTBRLayoutNotProven):
                G.private_read(link,100)

    def test_s5l_verified_code_is_not_a_live_hardware_driver(self):
        tool=TOOL.read_text()
        self.assertIn("PHYSICAL_PCIE_WLAN_REQUESTER_TO_DART1_HARDWARE_SID_PROVEN=NO",tool)
        self.assertIn("DART1_TTBR_PAGE_TABLE_IOVA_AND_FAULT_ISOLATION_PROVEN=NO",tool)
        for api in ("ioremap(", "readl(", "writel(", "dma_map(", "ioctl(",
                    "socket(", "reset_control_", "pci_host_probe("):
            self.assertNotIn(api,tool)

if __name__=="__main__":
    unittest.main()
