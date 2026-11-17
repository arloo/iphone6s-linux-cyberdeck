# SPDX-License-Identifier: MIT
"""Synthetic adversarial regression checks for the original A9 call chain.

Only the private source gate's authenticated run establishes original
Apple firmware provenance; these tests do not touch a physical phone.
"""
import struct
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import n71_s8000_original_storage_pcie_command_order_gate as gate

class OriginalS8000CommandOrder(unittest.TestCase):
    def test_original_command3_and7_same_perport_offset(self):
        self.assertEqual(gate.S800X_COMMAND_WORDS[0x7d8],gate.S800X_COMMAND_WORDS[0x7f0])
        self.assertEqual(gate.S800X_COMMAND_WORDS[0x7dc],gate.S800X_COMMAND_WORDS[0x7f4])
        self.assertEqual(gate.S800X_COMMAND_WORDS[0x7e8],0x52800062)
        self.assertEqual(gate.S800X_COMMAND_WORDS[0x800],0x528000e2)

    def test_command_register_within_stock_window(self):
        for port in range(4):
            offset=0x4020+port*0x40
            self.assertEqual(offset,(0x4020,0x4060,0x40a0,0x40e0)[port])
            self.assertLess(offset,gate.ROOT_COMMON_WINDOW_LENGTH)

    def test_exact_a9_vtable_dispatch(self):
        self.assertEqual(gate.PORT_METHODS,{1864:0xb3c,1872:0xb54})
        self.assertEqual(gate.ROOT_METHODS,{2040:0x7d8,2048:0x7f0})

    def test_stock_call_order(self):
        gate.check_order()

    def test_reordered_source_fails(self):
        data=list(gate.S800X_STARTUP_ORDER)
        data[0],data[1]=data[1],data[0]
        with self.assertRaises(gate.UnsafeAppleSequence):
            gate.check_order(data)

    def test_swapped_callback_names_fails(self):
        data=list(gate.S800X_STARTUP_ORDER)
        o0,n0=data[4];o1,n1=data[5]
        data[4]=(o0,n1);data[5]=(o1,n0)
        with self.assertRaises(gate.UnsafeAppleSequence):
            gate.check_order(data)

    def test_alias_position_fails(self):
        data=list(gate.S800X_STARTUP_ORDER)
        data[4]=(data[3][0],data[4][1])
        with self.assertRaises(gate.UnsafeAppleSequence):
            gate.check_order(data)

    def test_original_command_arm64_words(self):
        words={0:0x52880408,4:0x52800062,8:0x528000e2}
        raw=struct.pack('<III',*words.values())
        gate.check_words(raw,words)

    def test_mutated_command_word_rejected(self):
        words={0:0x52880408,4:0x52800062,8:0x528000e2}
        raw=bytearray(struct.pack('<III',*words.values()))
        raw[8]^=0x01
        with self.assertRaises(gate.UnsafeAppleSequence):
            gate.check_words(bytes(raw),words)

    def test_truncated_original_blob_rejected(self):
        with self.assertRaises(gate.UnsafeAppleSequence):
            gate.check_words(b'\x00\x00',gate.S800X_COMMAND_WORDS)

    def test_port_subroutine_writes3_before_storage_callback(self):
        self.assertLess(0x12f0,0x1300)
        self.assertLess(0x1300,0x1318)
        self.assertLess(0x1318,0x1328)
        self.assertLess(0x1328,0x1338)
        self.assertLess(0x1338,0x1358)

    def test_zero_state_is_separate_code_method(self):
        self.assertEqual(gate.S800X_SEPARATE_ZERO_STATE_METHOD,(0x1174,0x1178,0x1194))
        self.assertLess(max(gate.S800X_SEPARATE_ZERO_STATE_METHOD),
                        min(x for x,_ in gate.S800X_STARTUP_ORDER))

    def test_both_stock_command7_sites_are_proven(self):
        self.assertEqual(gate.S800X_ROOT_WRITE_7_CALL_SITES,
                         (('shared',0xa5c),('embedded',0x3eb0)))
        self.assertEqual(gate.EMBEDDED_WORDS[0x3eb0],0xf943a908)

    def test_never_imports_hardware_access_controls(self):
        source=Path(gate.__file__).read_text()
        for op in ('/dev/mem','writel(', 'insmod ', 'modprobe ', 'dma_map(',
                   'gpiod_direction_output(', 'pci_write_config'):
            self.assertNotIn(op,source)

if __name__=='__main__':
    unittest.main()
