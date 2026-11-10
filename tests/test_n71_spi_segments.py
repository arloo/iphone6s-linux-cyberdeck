"""Offline contract for bounded S8000 HBPP SPI PIO transfers.

USB disconnect after a private 1040-byte calibration trial is NOT evidence of
the root cause. This model never connects to a device or reads calibration.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/0006-n71-hbpp-segmented-spi-256-rfc.patch"

CHUNK = 256


def segments(length: int) -> list[tuple[int, int]]:
    if length <= 0:
        raise ValueError("packet must not be empty")
    return [(off, min(CHUNK, length - off))
            for off in range(0, length, CHUNK)]


class N71SegmentedSPIContract(unittest.TestCase):
    def test_bounded_lengths_preserve_exact_packet_bytes(self):
        for length in (2, 8, 16, 255, 256, 257, 1038, 1040,
                       18600, 65460):
            with self.subTest(length=length):
                offsets = segments(length)
                self.assertEqual(sum(size for _, size in offsets), length)
                self.assertTrue(all(0 < size <= CHUNK for _, size in offsets))
                for i, (offset, size) in enumerate(offsets):
                    self.assertEqual(offset, i * CHUNK)
                    self.assertLessEqual(offset + size, length)

    def test_1040_byte_trial_is_five_hardware_transfers(self):
        self.assertEqual([size for _, size in segments(1040)],
                         [256, 256, 256, 256, 16])

    def test_previous_1038_byte_trial_is_five_transfers(self):
        self.assertEqual([size for _, size in segments(1038)],
                         [256, 256, 256, 256, 14])

    def test_two_large_firmware_records_are_bounded(self):
        for size in (18600, 65460):
            self.assertTrue(all(n <= CHUNK for _, n in segments(size)))
            self.assertEqual(sum(n for _, n in segments(size)), size)

    def test_only_one_driver_is_modified(self):
        self.assertEqual(
            [line for line in PATCH.read_text().splitlines()
             if line.startswith("diff --git ")],
            ["diff --git a/drivers/input/touchscreen/apple_z2.c "
             "b/drivers/input/touchscreen/apple_z2.c"],
        )

    def test_patch_decreases_chunk_and_preserves_message_semantics(self):
        s = PATCH.read_text()
        self.assertIn("+#define APPLE_Z2_HBPP_CHUNK              256", s)
        self.assertIn("-#define APPLE_Z2_HBPP_CHUNK              4096", s)
        self.assertNotIn("+\t\txfers[i].cs_change", s)
        self.assertNotIn("+\tspi_sync(", s)

    def test_no_claim_that_chunking_fixes_crash(self):
        s = PATCH.read_text().lower()
        self.assertIn("not-yet-hardware-tested", s)
        self.assertIn("do not infer", s)

    def test_refuses_zero_length(self):
        with self.assertRaises(ValueError):
            segments(0)

    def test_refuses_negative_length(self):
        with self.assertRaises(ValueError):
            segments(-1)


if __name__ == "__main__":
    unittest.main()
