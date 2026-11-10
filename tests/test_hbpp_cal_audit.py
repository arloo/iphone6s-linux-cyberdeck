#!/usr/bin/env python3
"""Pure synthetic HBPP packet checks. No hardware/device data."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "tools/touch/hbpp_cal_audit.py"
spec = importlib.util.spec_from_file_location("hbpp_cal_audit", P)
audit = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(audit)


class TestHBPP(unittest.TestCase):
    def test_1024_byte_frame(self):
        payload = bytes(range(256)) * 4
        frame = audit.encode_n71_cal(payload)
        self.assertEqual(len(frame), 1038)
        info = audit.inspect_frame(frame)
        self.assertEqual(info["length"], 1038)
        self.assertEqual(info["payload_length"], 1024)
        self.assertEqual(info["address"], 0x10009000)
        self.assertEqual(frame[:2], b"\x30\x01")
        self.assertEqual(frame[2:4], b"\x01\x00")

    def test_reference_matches_current_wire_encoder(self):
        for n in (1, 2, 3, 4, 15, 256, 1023, 1024, 4096):
            with self.subTest(length=n):
                data = bytes((i * 37 + 11) & 0xFF for i in range(n))
                self.assertEqual(audit.encode_n71_cal(data),
                                 audit.independent_spi16_reference(data))

    def test_swap_only_changes_payload_not_header_or_checksum(self):
        data = bytes(range(256)) * 4
        a = audit.encode_n71_cal(data, swap_payload_words=True)
        b = audit.encode_n71_cal(data, swap_payload_words=False)
        self.assertEqual(a[:10], b[:10])
        self.assertEqual(a[-4:], b[-4:])
        self.assertNotEqual(a[10:-4], b[10:-4])
        self.assertEqual(audit.inspect_frame(a)["data_checksum"],
                         audit.inspect_frame(b)["data_checksum"])

    def test_bad_frames_detected(self):
        data = bytearray(audit.encode_n71_cal(bytes(range(32))))
        data[8] ^= 1
        with self.assertRaises(ValueError):
            audit.inspect_frame(bytes(data))
        data = bytearray(audit.encode_n71_cal(bytes(range(32))))
        data[15] ^= 1
        with self.assertRaises(ValueError):
            audit.inspect_frame(bytes(data))

    def test_ack_is_not_claimed_for_pending_idle(self):
        self.assertEqual(audit.evaluate_ack([audit.REQ_CAL] + [audit.IDLE] * 49),
                         "TIMEOUT")
        self.assertEqual(audit.evaluate_ack([audit.IDLE] * 3 + [audit.ACK_DATA]),
                         "ACK_DATA")
        self.assertEqual(audit.evaluate_ack([0x4F81]), "UNEXPECTED")

    def test_length_guards(self):
        for n in (0, 4097):
            with self.assertRaises(ValueError):
                audit.encode_n71_cal(b"X" * n)


if __name__ == "__main__":
    unittest.main()
