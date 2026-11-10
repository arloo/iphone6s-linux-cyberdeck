"""Synthetic HBPP DATA-frame fuzzing; no real calibration or firmware is accessed."""
import importlib.util
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hbpp_cal_audit", ROOT / "tools/touch/hbpp_cal_audit.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class SyntheticDataFrameFaultInjectionTests(unittest.TestCase):
    def test_10000_random_packet_encodings_against_independent_reference(self):
        rng = random.Random(0xA9C0DE)
        for case in range(10_000):
            n = rng.randrange(1, 4097)
            payload = rng.randbytes(n)
            address = rng.getrandbits(32)
            frame = AUDIT.encode_n71_cal(payload, address, True)
            reference = AUDIT.independent_spi16_reference(payload, address)
            self.assertEqual(frame, reference, f"case={case}, length={n}")
            parsed = AUDIT.inspect_frame(frame)
            self.assertEqual(parsed["payload_length"], (n + 3) & ~3)
            self.assertEqual(parsed["address"], address)
            self.assertEqual(parsed["length"], len(frame))

    def test_mutated_headers_and_checksums_are_rejected(self):
        rng = random.Random(0xA9F17E)
        for case in range(1_000):
            payload = rng.randbytes(rng.randrange(1, 4097))
            original = AUDIT.encode_n71_cal(payload)
            # Exclude the command's first word only when we target another field.
            for byte_index in (0, 2, 4, 8, 10 + ((len(payload) + 3) & ~3)):
                candidate = bytearray(original)
                candidate[byte_index] ^= 1
                with self.assertRaises(ValueError, msg=f"case={case}, byte={byte_index}"):
                    AUDIT.inspect_frame(candidate)

    def test_optional_nop_is_never_treated_as_a_valid_data_frame(self):
        raw = AUDIT.encode_n71_cal(bytes(range(256)) * 4)
        prefixed = AUDIT.optional_nop_prefix(raw, True)
        self.assertEqual(prefixed[:2], b"\x18\xe1")
        self.assertEqual(prefixed[2:], raw)
        with self.assertRaises(ValueError):
            AUDIT.inspect_frame(prefixed)

    def test_bounded_reqcal_ack_model_keeps_timeout(self):
        s = [AUDIT.REQ_CAL] * AUDIT.MAX_POLLS
        self.assertEqual(AUDIT.evaluate_ack(s), "TIMEOUT")
        self.assertEqual(AUDIT.evaluate_ack(s[:49] + [AUDIT.ACK_DATA]), "ACK_DATA")

    def test_odd_and_maximum_padding(self):
        for n in (1, 2, 3, 4, 7, 1023, 1024, 1025, 4095, 4096):
            with self.subTest(n=n):
                frame = AUDIT.encode_n71_cal(bytes([0x7E]) * n)
                self.assertEqual(AUDIT.inspect_frame(frame)["payload_length"],
                                 (n + 3) & ~3)


if __name__ == "__main__":
    unittest.main()
