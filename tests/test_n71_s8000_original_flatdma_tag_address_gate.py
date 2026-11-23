# SPDX-License-Identifier: MIT
"""Original N71 NVMMU source and the 8 MiB FlatDMA tag stride."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import n71_s8000_original_flatdma_tag_address_gate as G

HEADER = (ROOT / "experimental/port0/n71_s3e_read_only_io_plan.h").read_text()


class N71OriginalFlatDMATagTests(unittest.TestCase):
    def test_original_instruction_fingerprints_and_each_mutation(self):
        content = bytearray(0x3308)
        for offset, word in G.ORIGINAL_S800X_TAG_WORDS.items():
            struct.pack_into("<I", content, offset, word)
        G.verify_source_words(bytes(content))
        for offset in G.ORIGINAL_S800X_TAG_WORDS:
            with self.subTest(original_instruction_offset=hex(offset)):
                modified = bytearray(content)
                modified[offset] ^= 1
                with self.assertRaises(ValueError):
                    G.verify_source_words(bytes(modified))
        with self.assertRaises(ValueError):
            G.verify_source_words(bytes(content[:0x3304]))

    def test_original_tag_formula_and_unique_alignment(self):
        self.assertEqual(G.TAG_COUNT, 128)
        self.assertEqual(G.TAG_SHIFT, 23)
        self.assertEqual(G.tag_base(0), 0x40000000)
        self.assertEqual(G.tag_base(1), 0x40800000)
        self.assertEqual(G.tag_base(127), 0x7F800000)
        self.assertEqual(G.tag_index(0x40800000), 1)
        self.assertEqual(G.tag_index(0x7F800000), 127)
        for invalid in (0x40001000, 0x40801000, 0x41001000,
                        0x3FFFFFFF, 0x80000000):
            with self.subTest(address=hex(invalid)):
                with self.assertRaises(ValueError):
                    G.tag_index(invalid)
        for invalid in (-1, 128, 65536):
            with self.assertRaises(ValueError):
                G.tag_base(invalid)

    def test_real_kernel_candidate_matches_source_proven_stride(self):
        self.assertIn("N71_RO_FLATDMA_TAG_SHIFT 23U", HEADER)
        self.assertIn("N71_RO_FLATDMA_TAG_COUNT 128U", HEADER)
        self.assertIn("N71_RO_FLATDMA_VBASE 0x40000000ULL", HEADER)
        self.assertIn("N71_RO_READ_FLATDMA_TAG_INDEX 1U", HEADER)
        self.assertIn("!n71_s3e_ro_valid_read_flatdma_tag(layout->data_iova)", HEADER)
        self.assertNotIn("#define N71_RO_READ_FLATDMA_TAG_CANDIDATE 0x40001000ULL", HEADER)

if __name__ == "__main__":
    unittest.main()
