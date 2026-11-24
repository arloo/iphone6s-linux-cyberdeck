# SPDX-License-Identifier: MIT
"""Synthetic mutation and truth-table tests; no real device access."""
from pathlib import Path
import struct
import sys
import unittest
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import n71_s8000_original_read_flag_mask_gate as MASK
import n71_s8000_original_ionvme_read_source_gate as READ

class OriginalRequestFlagMaskTest(unittest.TestCase):
    def setUp(self):
        self.fake = bytearray(READ.EXPECTED_TEXT_SIZE)
        for pos, word in MASK.MASK_SOURCE_WORDS.items():
            struct.pack_into('<I', self.fake, pos, word)

    def test_all_original_instruction_fingerprints_fail_closed(self):
        self.assertGreaterEqual(len(MASK.MASK_SOURCE_WORDS), 110)
        MASK.verify_instructions(bytes(self.fake))
        for at in MASK.MASK_SOURCE_WORDS:
            with self.subTest(original_instruction=hex(at)):
                changed = bytearray(self.fake)
                changed[at] ^= 1
                with self.assertRaises(ValueError):
                    MASK.verify_instructions(bytes(changed))
        with self.assertRaises(ValueError):
            MASK.verify_instructions(bytes(self.fake[:-1]))
        with self.assertRaises(READ.RejectedOriginalNVMeSource):
            READ.verify_true_original_text(bytes(self.fake))

    def test_all_eight_boolean_combinations(self):
        for controller, lookup, auxiliary in product((0,1), repeat=3):
            with self.subTest(controller=controller, lookup=lookup, auxiliary=auxiliary):
                expected = int(bool(controller) and bool(lookup or auxiliary))
                self.assertEqual(MASK.effective_request_bit0(controller,lookup,auxiliary), expected)
        self.assertEqual(MASK.effective_request_bit0(1,0,0),0)
        self.assertEqual(MASK.effective_request_bit0(1,1,0),1)
        self.assertEqual(MASK.effective_request_bit0(1,0,1),1)
        self.assertEqual(MASK.effective_request_bit0(1,1,1),1)
        for invalid in ((2,0,0),(1,-1,1),(1,0,3)):
            with self.assertRaises(ValueError):
                MASK.effective_request_bit0(*invalid)

    def test_mapper_symbol_must_match_resolved_address(self):
        name = b'\0__ZN8IOMapper28copyMapperForDeviceWithIndexEP9IOServicej\0'
        entry = struct.pack('<IBBHQ', 1, 0x0f, 1, 0, 0x1000)
        blob = entry + name
        MASK.verify_mapper_symbol(blob, 0x1000, 0, 1, 16, len(name))
        with self.assertRaises(ValueError):
            MASK.verify_mapper_symbol(blob, 0x1004, 0, 1, 16, len(name))
        with self.assertRaises(ValueError):
            MASK.verify_mapper_symbol(entry + name.replace(b'IOMapper',b'XXMapper'),
                                      0x1000, 0, 1, 16, len(name))
        with self.assertRaises(ValueError):
            MASK.verify_mapper_symbol(blob[:-1], 0x1000, 0, 1, 16, len(name)-1)
        with self.assertRaises(ValueError):
            MASK.verify_mapper_symbol(blob, 0x1000, 0, 2, 16, len(name)+1)

    def test_no_runtime_hardware_claims_or_nand_execution(self):
        source = (ROOT/'tools/n71_s8000_original_read_flag_mask_gate.py').read_text()
        self.assertIn('LOOKUP_AND_AUXILIARY_RUNTIME_VALUES=UNVERIFIED',source)
        self.assertIn('ACTIVE_N71_CONTROLLER_BINDING=UNVERIFIED',source)
        self.assertIn('FIRST_NAND_READ_OR_DMA_ACCESS=NOT_AUTHORIZED',source)
        self.assertNotIn('writel(', source)
        self.assertNotIn('dma_map_single(', source)

if __name__ == '__main__':
    unittest.main()
