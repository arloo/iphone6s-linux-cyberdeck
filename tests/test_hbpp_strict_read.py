"""Synthetic protocol and source-contract checks for strict HBPP MEM_READ validation."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools/touch/hbpp_read_validator.py"
SPEC = importlib.util.spec_from_file_location("hbpp_read_validator", SRC)
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)
PATCH = ROOT / "patches/0002-n71-hbpp-read-strict-validation-rfc.patch"


class HBPPReadValidationTests(unittest.TestCase):
    def test_synthetic_valid_version(self):
        for value in (0, 0x12345678, 0xFFFFFFFF):
            with self.subTest(value=value):
                self.assertEqual(
                    VALIDATOR.decode_register_reply(VALIDATOR.make_synthetic_reply(value)),
                    value,
                )

    def test_invalid_status_rejected(self):
        reply = bytearray(VALIDATOR.make_synthetic_reply(0x12345678))
        reply[:2] = (0x4879).to_bytes(2, "big")
        with self.assertRaisesRegex(ValueError, "status"):
            VALIDATOR.decode_register_reply(reply)

    def test_invalid_checksum_rejected(self):
        reply = bytearray(VALIDATOR.make_synthetic_reply(0x12345678))
        reply[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            VALIDATOR.decode_register_reply(reply)

    def test_bad_length_rejected(self):
        for blob in (b"", b"\x00" * 7, b"\x00" * 9):
            with self.subTest(size=len(blob)):
                with self.assertRaisesRegex(ValueError, "length"):
                    VALIDATOR.decode_register_reply(blob)

    def test_illegal_encoder_value_rejected(self):
        with self.assertRaises(ValueError):
            VALIDATOR.make_synthetic_reply(-1)
        with self.assertRaises(ValueError):
            VALIDATOR.make_synthetic_reply(1 << 32)

    def test_kernel_patch_stops_on_invalid_response(self):
        p = PATCH.read_text()
        added = "\n".join(
            x[1:] for x in p.splitlines()
            if x.startswith("+") and not x.startswith("+++")
        )
        self.assertIn("sum != apple_z2_sum8(rx + 2, 4)", added)
        self.assertIn("status != APPLE_Z2_HBPP_READ_DATA", added)
        self.assertIn("return -EBADMSG;", added)
        # The parsed value must be assigned only after validation.
        self.assertLess(p.index("+\t\treturn -EBADMSG;"),
                        p.index(" \t*val = get_unaligned_be16"))
        self.assertNotIn("%*ph", added)  # Do not dump private RX words

    def test_patch_is_scoped_to_z2_driver(self):
        p = PATCH.read_text()
        touched = [x for x in p.splitlines() if x.startswith("diff --git")]
        self.assertEqual(
            touched,
            ["diff --git a/drivers/input/touchscreen/apple_z2.c "
             "b/drivers/input/touchscreen/apple_z2.c"],
        )


if __name__ == "__main__":
    unittest.main()
