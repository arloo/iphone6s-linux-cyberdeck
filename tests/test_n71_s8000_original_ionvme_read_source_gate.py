# SPDX-License-Identifier: MIT
"""Provenance checks for original iPhone 6s IONVMeFamily Read builder.

No firmware is bundled and no hardware accesses occur. The authentic
kernelcache is checked separately by the source gate on the owner host.
"""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import n71_s8000_original_ionvme_read_source_gate as AUDIT

READ = (ROOT / "experimental/port0/n71_s3e_read_only_io_plan.h").read_text()
DOC = (ROOT / "docs/N71_S8000_S3E_DMA_RETIREMENT_AUDIT_2026_11_20.md").read_text()


class OriginalIONVMeReadTests(unittest.TestCase):
    def setUp(self):
        self.code = bytearray(AUDIT.EXPECTED_TEXT_SIZE)
        for offset, word in AUDIT.READ_WIRE_PROVENANCE.items():
            struct.pack_into("<I", self.code, offset, word)

    def test_each_source_instruction_mutation_denied(self):
        self.assertEqual(len(AUDIT.READ_WIRE_PROVENANCE), 15)
        AUDIT.verify_read_words(bytes(self.code))
        for offset in AUDIT.READ_WIRE_PROVENANCE:
            with self.subTest(offset=hex(offset)):
                corrupt = bytearray(self.code)
                corrupt[offset] ^= 0x01
                with self.assertRaises(AUDIT.RejectedOriginalNVMeSource):
                    AUDIT.verify_read_words(bytes(corrupt))
        with self.assertRaises(AUDIT.RejectedOriginalNVMeSource):
            AUDIT.verify_read_words(bytes(self.code[:-4]))

    def test_fake_content_can_match_instructions_but_never_original_hash(self):
        # These selected instruction bytes alone cannot authenticate
        # the original complete firmware or authorize device I/O.
        AUDIT.verify_read_words(bytes(self.code))
        with self.assertRaises(AUDIT.RejectedOriginalNVMeSource):
            AUDIT.verify_true_original_text(bytes(self.code))

    def test_original_cdw_encoding_matches_existing_one_sector_candidate(self):
        self.assertEqual(AUDIT.READ_WIRE_PROVENANCE[0x36178], 0x321F0148)
        self.assertEqual(AUDIT.READ_WIRE_PROVENANCE[0x36184], 0xF900A002)
        self.assertEqual(AUDIT.READ_WIRE_PROVENANCE[0x363C4], 0x97FFFF5E)
        self.assertEqual(AUDIT.READ_WIRE_PROVENANCE[0x363E8], 0x52808008)
        self.assertEqual(AUDIT.READ_WIRE_PROVENANCE[0x363EC], 0x52810009)
        self.assertEqual(AUDIT.EXPECTED_TEXT_SIZE, 272392)
        self.assertIn("N71_RO_NVM_READ 0x02U", READ)
        self.assertIn("n71_ro_le32(tmp + 4, N71_RO_NSID)", READ)
        self.assertIn("n71_ro_le64(tmp + 40, slba)", READ)
        self.assertIn("n71_ro_le16(tmp + 48, 0U)", READ)

    def test_transport_flag_and_dma_retirement_explicitly_not_proven(self):
        source = (ROOT / "tools/n71_s8000_original_ionvme_read_source_gate.py").read_text()
        self.assertIn("FLATDMA_TRANSPORT_BIT5_FOR_NVM_READ=UNVERIFIED", source)
        self.assertIn("DMA_DRAIN_OR_NAND_READ_PROVEN=NO", source)
        self.assertIn("PRIVATE_FIRMWARE_OR_USER_DATA_PUBLISHED=NO", source)
        self.assertIn("N71_RO_IO_FLAG_UNQUALIFIED 0U", READ)
        self.assertIn("dma_quiescence_proven", DOC.lower())
        self.assertNotIn("nand-write", source.lower())

if __name__ == "__main__":
    unittest.main()
