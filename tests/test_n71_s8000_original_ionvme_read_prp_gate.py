# SPDX-License-Identifier: MIT
"""Cross-check original IONVMeFamily READ -> IOVM/PRP mapping call graph.

All host-only synthetic tests use byte arrays, not device or Apple firmware.
Real original owner kernelcache is audited separately via provenance gate.
"""
import struct
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import n71_s8000_original_ionvme_read_source_gate as READ
import n71_s8000_original_ionvme_read_prp_gate as FLOW

READ_PLAN = (ROOT / "experimental/port0/n71_s3e_read_only_io_plan.h").read_text()


class OriginalReadToPRPTests(unittest.TestCase):
    def setUp(self):
        self.fake = bytearray(READ.EXPECTED_TEXT_SIZE)
        for at, word in {**FLOW.PROVENANCE_WORDS,
                         **FLOW.READ_FLAG_WORDS,
                         **FLOW.REQUEST_FLAG_INITIALIZER_WORDS}.items():
            struct.pack_into("<I", self.fake, at, word)

    def test_every_original_transport_instruction_is_pinned(self):
        self.assertGreaterEqual(len(FLOW.PROVENANCE_WORDS), 15)
        self.assertEqual(len(FLOW.READ_FLAG_WORDS), 6)
        self.assertEqual(len(FLOW.REQUEST_FLAG_INITIALIZER_WORDS), 8)
        FLOW.verify_transport_instruction_flow(bytes(self.fake))
        for at in {**FLOW.PROVENANCE_WORDS, **FLOW.READ_FLAG_WORDS,
                   **FLOW.REQUEST_FLAG_INITIALIZER_WORDS}:
            with self.subTest(arm64_source_offset=hex(at)):
                test = bytearray(self.fake)
                test[at] ^= 1
                with self.assertRaises(ValueError):
                    FLOW.verify_transport_instruction_flow(bytes(test))

    def test_all_selected_calls_resolve_to_original_read_prp_targets(self):
        self.assertEqual(FLOW.CALL_TARGETS[0x13248], 0x365B4)
        self.assertEqual(FLOW.CALL_TARGETS[0x13250], 0x36390)
        self.assertEqual(FLOW.CALL_TARGETS[0x132AC], 0x35BDC)
        self.assertEqual(FLOW.CALL_TARGETS[0x35BF4], 0x355B4)
        for addr, dest in FLOW.CALL_TARGETS.items():
            with self.subTest(call=hex(addr)):
                word = struct.unpack_from("<I", self.fake, addr)[0]
                self.assertEqual(FLOW.arm64_bl_target(addr, word), dest)
        with self.assertRaises(ValueError):
            FLOW.arm64_bl_target(0, 0xD65F03C0)

    def test_source_fingerprint_protection_cannot_be_bypassed_with_fixtures(self):
        FLOW.verify_transport_instruction_flow(bytes(self.fake))
        with self.assertRaises(READ.RejectedOriginalNVMeSource):
            FLOW.verify_transport_words(bytes(self.fake))
        with self.assertRaises(ValueError):
            FLOW.verify_transport_instruction_flow(bytes(self.fake[:0x35C00]))

    def test_vendor_flag_is_conditional_not_an_automatic_read_property(self):
        self.assertEqual(FLOW.READ_FLAG_WORDS[0x36168], 0xB940B809)
        self.assertEqual(FLOW.READ_FLAG_WORDS[0x3616C], 0x5316552A)
        self.assertEqual(FLOW.READ_FLAG_WORDS[0x36170], 0x1213014A)
        self.assertEqual(FLOW.READ_FLAG_WORDS[0x3617C], 0xB9011808)
        source = (ROOT / "tools/n71_s8000_original_ionvme_read_prp_gate.py").read_text()
        self.assertIn("READ_VENDOR_FLAG_BIT13_UNCONDITIONALLY_REQUIRED=UNVERIFIED", source)
        self.assertIn("APPLE_S8000_TAG1_IO_PHYSICAL_ACCEPTANCE=UNVERIFIED", source)
        self.assertIn("DMA_DRAIN_OR_NAND_DATA_READ=NO", source)
        self.assertEqual(FLOW.REQUEST_FLAG_INITIALIZER_WORDS[0x35008], 0xAA0603F9)
        self.assertEqual(FLOW.REQUEST_FLAG_INITIALIZER_WORDS[0x35044], 0x1A9F1129)
        self.assertEqual(FLOW.REQUEST_FLAG_INITIALIZER_WORDS[0x35050], 0xB900BA68)
        self.assertIn("ACTIVE_N71_IO_POOL_INITIALIZER_X6_VALUE=UNVERIFIED", source)
        self.assertIn("N71_RO_IO_FLAG_UNQUALIFIED 0U", READ_PLAN)

if __name__ == "__main__":
    unittest.main()
