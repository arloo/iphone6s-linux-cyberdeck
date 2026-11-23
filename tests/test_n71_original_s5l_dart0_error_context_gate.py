# SPDX-License-Identifier: MIT
"""Synthetic verification of the original S8000 DART0 fault-context gate."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import n71_original_s5l_dart0_error_context_gate as G


class OriginalDART0ContextTests(unittest.TestCase):
    def setUp(self):
        self.payload = bytearray(G.S5L_EXPECTED_SIZE)
        for offset, word in G.S5L_WORDS.items():
            struct.pack_into("<I", self.payload, offset, word)

    def test_expected_source_fingerprints(self):
        G.verify_s5l_fault_path(bytes(self.payload))
        self.assertEqual(len(G.S5L_WORDS), 13)
        self.assertEqual(G.S5L_WORDS[0xe48], 0xb9401109)
        self.assertEqual(G.S5L_WORDS[0xe4c], 0x37f80509)

    def test_every_modified_original_instruction_rejected(self):
        for offset in G.S5L_WORDS:
            with self.subTest(relative_offset=hex(offset)):
                modified = bytearray(self.payload)
                modified[offset] ^= 0x1
                with self.assertRaises(G.RejectedDARTContext):
                    G.verify_s5l_fault_path(bytes(modified))

    def test_truncated_or_unexpected_source_rejected(self):
        for modified in (bytes(self.payload[:-4]), bytes(self.payload + b"0")):
            with self.assertRaises(G.RejectedDARTContext):
                G.verify_s5l_fault_path(modified)

    def test_register_offsets_are_dart0_not_dart1(self):
        self.assertEqual(0x500 & (1 << 31), 0)
        self.assertEqual(0x500 & ((1 << 8) | (1 << 10)), 0x500)
        body = (ROOT / "experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        self.assertIn("s8000_v0_layout_unverified=YES", body)
        self.assertIn("raw_context_redacted=YES", body)
        self.assertIn("fault_not_dma_fence=YES", body)

if __name__ == "__main__":
    unittest.main()
