# SPDX-License-Identifier: MIT
"""Original, provenance-checked IONVMeFamily virtual method 1440 alternatives.

These host-only tests must never substitute a synthetic byte array for the
complete, SHA-256 authenticated original kernelcache on actual hardware.
"""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import n71_s8000_original_ionvme_vtable1440_gate as G
import n71_s8000_original_ionvme_read_source_gate as READ

SOURCE = (ROOT / "tools/n71_s8000_original_ionvme_vtable1440_gate.py").read_text()


class N71AppleVirtual1440Alternatives(unittest.TestCase):
    def setUp(self):
        self.fake = bytearray(READ.EXPECTED_TEXT_SIZE)
        for off, word in G.ORIGINAL_VTABLE_SOURCE_WORDS.items():
            struct.pack_into("<I", self.fake, off, word)

    def test_all_original_constructor_and_virtual_return_words_mutated(self):
        self.assertEqual(len(G.ORIGINAL_VTABLE_SOURCE_WORDS), 15)
        G.verify_original_vptr_instruction_words(bytes(self.fake))
        for off in G.ORIGINAL_VTABLE_SOURCE_WORDS:
            with self.subTest(original_instruction_offset=hex(off)):
                changed = bytearray(self.fake)
                changed[off] ^= 1
                with self.assertRaises(ValueError):
                    G.verify_original_vptr_instruction_words(bytes(changed))
        with self.assertRaises(ValueError):
            G.verify_original_vptr_instruction_words(bytes(self.fake[:-4]))

    def test_original_direct_base_derived_return_differ(self):
        self.assertEqual(G.METHOD_OFFSET, 1440)
        self.assertEqual(G.CHOICE_OFFSET, 1448)
        self.assertEqual(G.DERIVED_PARENT_TARGET, 0x246AC)
        self.assertEqual(G.RET0, (0x52800000, 0xD65F03C0))
        self.assertEqual(G.RET1, (0x52800020, 0xD65F03C0))
        self.assertEqual(
            G.ORIGINAL_VTABLE_SOURCE_WORDS[G.DERIVED_PARENT_BL], 0x97FFCD53)
        self.assertEqual(
            G.ORIGINAL_VTABLE_SOURCE_WORDS[G.BASE_VPTR_SETTER], 0x900033E8)
        self.assertEqual(
            G.ORIGINAL_VTABLE_SOURCE_WORDS[G.DERIVED_VPTR_SETTER], 0x90003388)

    def test_verified_partial_words_do_not_authorize_firmware_or_hardware(self):
        G.verify_original_vptr_instruction_words(bytes(self.fake))
        with self.assertRaises(READ.RejectedOriginalNVMeSource):
            READ.verify_true_original_text(bytes(self.fake))
        self.assertIn("ACTIVE_N71_CONTROLLER_DYNAMIC_CLASS=UNVERIFIED", SOURCE)
        self.assertIn("ACTIVE_N71_CONTROLLER_VTABLE1440_RETURN=UNVERIFIED", SOURCE)
        self.assertIn("NAND_IO_OR_DMA_QUALIFIED=NO", SOURCE)
        self.assertNotIn("writel(", SOURCE)

if __name__ == "__main__":
    unittest.main()
