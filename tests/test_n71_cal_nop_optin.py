"""OFFLINE-ONLY synthetic checks of N71 HBPP calibration NOP framing.

The private calibration is neither read nor reconstructed by this test.
CI success NEVER implies real ACK_DATA or functional touch.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hbpp_frame", ROOT / "tools/touch/hbpp_cal_audit.py"
)
HBPP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HBPP)
PATCH = ROOT / "patches/0005-n71-calibration-nop-prefix-optin-rfc.patch"


class N71CalibrationNOPTests(unittest.TestCase):
    def setUp(self):
        # All four source blocks are generated synthetically.
        self.cal = bytes((i * 17 + 3) & 255 for i in range(1024))
        self.original = HBPP.encode_n71_cal(self.cal)
        self.experimental = HBPP.optional_nop_prefix(self.original, True)

    def test_default_1038_byte_frame_unchanged(self):
        self.assertEqual(len(self.original), 1038)
        self.assertEqual(HBPP.optional_nop_prefix(self.original), self.original)

    def test_optional_frame_is_1040_bytes(self):
        self.assertEqual(len(self.experimental), 1040)
        self.assertEqual(self.experimental[:2], struct.pack(">H", HBPP.NOP))

    def test_optional_prefix_is_only_difference(self):
        self.assertEqual(self.experimental[2:], self.original)
        self.assertEqual(HBPP.inspect_frame(self.experimental[2:]),
                         HBPP.inspect_frame(self.original))

    def test_header_and_payload_checksums_remain_valid(self):
        info = HBPP.inspect_frame(self.original)
        self.assertEqual(info["length"], 1038)
        self.assertEqual(info["payload_length"], 1024)
        self.assertEqual(info["address"], 0x10009000)
        self.assertEqual(info, HBPP.inspect_frame(self.experimental[2:]))

    def test_known_firmware_nop_does_not_prove_acceptance(self):
        self.assertEqual(HBPP.evaluate_ack([HBPP.REQ_CAL] * 50), "TIMEOUT")
        self.assertEqual(HBPP.evaluate_ack([HBPP.IDLE] * 50), "TIMEOUT")
        self.assertEqual(HBPP.evaluate_ack([HBPP.REQ_CAL, HBPP.ACK_DATA]),
                         "ACK_DATA")

    def test_non_ack_cannot_be_interpreted_as_success(self):
        for status in (HBPP.REQ_CAL, HBPP.IDLE, HBPP.NOP, 0, 0xFFFF):
            self.assertNotEqual(HBPP.evaluate_ack([status]), "ACK_DATA")

    def test_nop_wrapper_rejects_corrupt_data(self):
        corrupted = bytearray(self.original)
        corrupted[-1] ^= 0x80
        with self.assertRaisesRegex(ValueError, "checksum"):
            HBPP.optional_nop_prefix(bytes(corrupted), True)

    def test_patch_is_only_apple_z2_driver(self):
        patch = PATCH.read_text()
        self.assertEqual(
            [line for line in patch.splitlines()
             if line.startswith("diff --git ")],
            ["diff --git a/drivers/input/touchscreen/apple_z2.c "
             "b/drivers/input/touchscreen/apple_z2.c"],
        )

    def test_feature_is_off_by_default_and_readonly_parameter(self):
        patch = PATCH.read_text()
        self.assertIn("+static bool hbpp_cal_nop;", patch)
        self.assertIn("+module_param(hbpp_cal_nop, bool, 0444);", patch)
        self.assertNotIn("+static bool hbpp_cal_nop = true;", patch)

    def test_protected_board_address_size_and_framing(self):
        patch = PATCH.read_text()
        for marker in (
            "of_device_is_compatible(root, \"apple,s8000\")",
            "!is_s8000",
            "len != 1024",
            "padded != 1024",
            "pkt_len != 1038",
            "address != 0x10009000",
            "memmove(pkt + 2, pkt, pkt_len)",
            "put_unaligned_be16(APPLE_Z2_HBPP_NOP, pkt)",
            "pkt_len += 2",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, patch)

    def test_no_change_to_ACK_or_device_firmware_logic(self):
        patch = PATCH.read_text()
        self.assertNotIn("+\t\treturn 0; /* calibration accepted */", patch)
        self.assertNotIn("+\t\trequest_firmware(", patch)
        self.assertNotIn("+\t\tspi_write(", patch)
        self.assertNotIn("+\t\tAPPLE_Z2_HBPP_EXECUTE", patch)


if __name__ == "__main__":
    unittest.main()
