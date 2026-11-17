# SPDX-License-Identifier: MIT
"""Synthetic tests for original stock port register +0x210 sequence."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import n71_s8000_stock_port_0210_source_gate as gate

class OriginalPort0210(unittest.TestCase):
    def test_source_contains_read_and_conditional_write(self):
        self.assertEqual(gate.ORIGINAL_1504[0x1740],0xf943e908)
        self.assertEqual(gate.ORIGINAL_1504[0x1758],0xf943ed08)
        self.assertEqual(gate.ORIGINAL_1504[0x1750],0x340000e0)
    def test_same_register_offset(self):
        self.assertEqual(gate.ORIGINAL_1504[0x1744],gate.ORIGINAL_1504[0x1760])
        self.assertEqual(gate.ORIGINAL_1504[0x1744],0x52804201)
    def test_writes_exact_value_returned_by_read(self):
        self.assertEqual(gate.ORIGINAL_1504[0x174c],0xaa0003f4)
        self.assertEqual(gate.ORIGINAL_1504[0x1764],0xaa1403e2)
    def test_branch_skips_write_on_zero(self):
        self.assertLess(0x1750,0x1758)
        self.assertLess(0x1768,0x176c)
    def test_original_port_vtable_slots(self):
        self.assertEqual(gate.STOCK_PORT_SLOTS,{1504:0x172c,2000:0x1a78,2008:0x1b58})
    def test_mutated_instruction_fails(self):
        raw=bytearray((max(gate.ORIGINAL_1504)+8))
        for i,val in gate.ORIGINAL_1504.items():
            struct.pack_into('<I',raw,i,val)
        gate.check_words(raw,gate.ORIGINAL_1504)
        raw[0x1764]^=0x4
        with self.assertRaises(gate.UnqualifiedLocalConfiguration):
            gate.check_words(raw,gate.ORIGINAL_1504)
    def test_short_source_fails(self):
        with self.assertRaises(gate.UnqualifiedLocalConfiguration):
            gate.check_words(b'',gate.ORIGINAL_1504)
    def test_offline_gate_no_hardware_writes(self):
        source=Path(gate.__file__).read_text()
        for op in ('writel(', 'regmap_write(', 'insmod ', 'dma_map(', 'pci_write_config'):
            self.assertNotIn(op,source)

if __name__=="__main__": unittest.main()
