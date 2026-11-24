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

    def test_original_kernel_dma_field_and_self_fingerprints(self):
        fake = bytearray(MASK.EXPECTED_KERNEL_TEXT_SIZE)
        for pos, word in MASK.KERNEL_DMA_SOURCE_WORDS.items():
            struct.pack_into('<I', fake, pos, word)
        MASK.verify_kernel_dma_words(fake)
        for at in MASK.KERNEL_DMA_SOURCE_WORDS:
            with self.subTest(kernel_instruction=hex(at)):
                fake[at] ^= 1
                with self.assertRaises(ValueError):
                    MASK.verify_kernel_dma_words(fake)
                fake[at] ^= 1
        # Passing selected words must never substitute for original identity.
        with self.assertRaises(ValueError):
            MASK.verify_true_original_kernel_text(fake)
        with self.assertRaises(ValueError):
            MASK.verify_kernel_dma_words(fake[:-1])
        with self.assertRaises(ValueError):
            MASK.verify_kernel_dma_words(fake + b'\0')

    def test_import_name_and_address_both_bind_each_dma_method(self):
        for method, (_, expected) in MASK.DMA_KERNEL_SYMBOLS.items():
            with self.subTest(method=method):
                names = b'\0' + expected + b'\0'
                entry = struct.pack('<IBBHQ', 1, 0x0f, 1, 0, 0x1000)
                blob = entry + names
                MASK.verify_mapper_symbol(blob, 0x1000, 0, 1, 16,
                                          len(names), expected=expected)
                for bad_name, bad_target in ((expected + b'X', 0x1000),
                                              (expected, 0x1008)):
                    with self.assertRaises(ValueError):
                        MASK.verify_mapper_symbol(blob, bad_target, 0, 1, 16,
                                                  len(names), expected=bad_name)

    def test_class_reference_registers_shift_and_extent(self):
        for reg in (0, 1, 2, 8):
            code = struct.pack('<2I', 0x90000000 | reg,
                               0x9100A000 | (reg << 5) | reg)
            self.assertEqual(MASK.original_adrp_add(code, 0x2000, 0, reg), 0x2028)
            changed = bytearray(code)
            changed[4] ^= 1
            with self.assertRaises(ValueError):
                MASK.original_adrp_add(changed, 0x2000, 0, reg)
            with self.assertRaises(ValueError):
                MASK.original_adrp_add(code[:7], 0x2000, 0, reg)
            with self.assertRaises(ValueError):
                MASK.original_adrp_add(code, 0x2000, -4, reg)
        shifted = struct.pack('<2I', 0x90000000, 0x9140A000)
        with self.assertRaises(ValueError):
            MASK.original_adrp_add(shifted, 0x2000, 0, 0)

    def test_cast_name_must_belong_to_own_file_backed_strings(self):
        expected = b'AppleANS2NVMeController'
        data = expected + b'\0'
        main = {'__PRELINK_TEXT': {'vm': 0x1000, 'offset': 0, 'filesize': len(data)}}
        nested = {'__TEXT': {'sections': {'__cstring': {'vm': 0x1000, 'size': len(data)}}}}
        MASK.verify_class_literal(data, main, nested, 0x1000, expected)
        for blob, address in ((data.replace(b'ANS2', b'ANSX'), 0x1000),
                              (data[:-1], 0x1000), (data, 0x0FFF), (data, 0x1001)):
            with self.assertRaises(ValueError):
                MASK.verify_class_literal(blob, main, nested, address, expected)
        for bad in (b'', expected + b'\0', b'x' * 121):
            with self.assertRaises(ValueError):
                MASK.verify_class_literal(data, main, nested, 0x1000, bad)

    def test_no_runtime_hardware_claims_or_nand_execution(self):
        source = (ROOT/'tools/n71_s8000_original_read_flag_mask_gate.py').read_text()
        self.assertIn('LOOKUP_AND_AUXILIARY_RUNTIME_VALUES=UNVERIFIED',source)
        self.assertIn('ACTIVE_N71_CONTROLLER_BINDING=UNVERIFIED',source)
        self.assertIn('FIRST_NAND_READ_OR_DMA_ACCESS=NOT_AUTHORIZED',source)
        self.assertNotIn('writel(', source)
        self.assertNotIn('dma_map_single(', source)

if __name__ == '__main__':
    unittest.main()
