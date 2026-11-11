"""Offline safety/transport contracts for a single guarded segmented-NOP SPI test.

No real iPhone, Apple calibration, firmware, USB or peripheral access.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/touch/n71-hbpp-segprobe/n71_hbpp_segprobe.c"
MAKE = ROOT / "tools/touch/n71-hbpp-segprobe/Makefile"

FRAME = 1040
CHUNK = 256


def bounds(length: int) -> list[tuple[int, int]]:
    if length <= 0:
        raise ValueError("invalid frame size")
    return [(off, min(CHUNK, length - off)) for off in range(0, length, CHUNK)]


class SegmentedNOPLabGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()

    def test_module_is_distinct_and_one_shot(self):
        self.assertEqual(MAKE.read_text().strip(),
                         "obj-m += n71_hbpp_segprobe.o")
        self.assertIn("COMPLETE protocol_result=%d (module deliberately inert)", self.source)
        self.assertIn("return 0;", self.source.split("module_init(n71_init);")[0][-740:])

    def test_1040_uses_five_segments(self):
        self.assertEqual(bounds(FRAME),
                         [(0,256),(256,256),(512,256),(768,256),(1024,16)])
        self.assertIn("#define SEG_FRAME_BYTES 1040U", self.source)
        self.assertIn("#define SEG_CHUNK 256U", self.source)
        self.assertIn("#define SEG_COUNT 5U", self.source)

    def test_all_segmentation_boundaries_and_byte_count(self):
        for length in (2, 8, 16, 255, 256, 257, 1038, 1040):
            with self.subTest(length=length):
                segments = bounds(length)
                self.assertEqual(sum(x[1] for x in segments), length)
                self.assertTrue(all(0 < x[1] <= CHUNK for x in segments))

    def test_segmented_message_single_spi_sync(self):
        body = self.source.split("static int segmented_reset_idle_probe(void)",1)[1]
        body = body.split("static int status_only_probe(void)",1)[0]
        self.assertIn("spi_message_init(&msg)", body)
        self.assertIn("spi_message_add_tail(&xfers[i], &msg)", body)
        self.assertIn("spi_sync(g.spi, &msg)", body)
        self.assertIn("msg.actual_length != SEG_FRAME_BYTES", body)
        self.assertNotIn("spi_sync_transfer(", body)
        self.assertNotIn("cs_change = true", body)
        self.assertIn("bits_per_word = 8", body)
        self.assertIn("speed_hz = SPI_HZ", body)

    def test_only_nop_bytes_not_calibration(self):
        body = self.source.split("static int segmented_reset_idle_probe(void)",1)[1]
        body = body.split("static int status_only_probe(void)",1)[0]
        self.assertIn("tx[i] = 0x18;", body)
        self.assertIn("tx[i + 1] = 0xe1;", body)
        self.assertNotIn("0x3001", body)
        self.assertNotIn("request_firmware(", self.source)
        self.assertNotIn("nvmem_cell_write(", self.source)
        self.assertNotIn("kernel_write(", self.source)

    def test_reset_required_before_segment_test_and_deasserted_after(self):
        s = self.source
        assert_start = s.index("static int segmented_reset_idle_probe(void)")
        deassert = s.index("gpiod_set_value_cansleep(g.reset, 0); /* deassert active-low reset */")
        call = s.index("err = segmented_reset_idle_probe();")
        self.assertLess(assert_start, call)
        self.assertLess(call, deassert)
        self.assertIn("gpiod_get_raw_value(g.reset) != 0", s)
        self.assertIn('SEGMENT_PREFLIGHT_FAILED_RESET_NOT_ASSERTED', s)

    def test_active_clock_and_analog_preflight_not_offline_signature(self):
        body = self.source.split("static int segmented_reset_idle_probe(void)",1)[1]
        body = body.split("static int status_only_probe(void)",1)[0]
        self.assertIn("read_mmio_word(PMGR_PHYS, 0) != PMGR_ACTIVE", body)
        self.assertIn("analog_read() != ANALOG_ACTIVE", body)
        self.assertNotIn('check_baseline("SEGMENT_PREFLIGHT")', body)

    def test_short_hbpp_reads_still_strict_after_test(self):
        s=self.source
        self.assertIn("status != HBPP_READ_DATA || returned_sum != sum", s)
        self.assertIn("HBPP_STATUS_AND_BOTH_STRICT_READS_VALID", s)
        self.assertIn("VALID_CONTROLLER_VERSION", s)

    def test_independent_watchdog_and_cleanup_retained(self):
        s=self.source
        for token in (
            "WATCHDOG_MS 1500U",
            "schedule_delayed_work(",
            'shutdown_hardware("DIRECT")',
            'shutdown_hardware("WATCHDOG")',
            "WATCHDOG_AUDIT_PASS",
            "FINAL_BOARD_BASELINE_PASS",
            "spi_unregister_device(g.spi)",
            "clk_disable_unprepare(g.clk)",
        ):
            self.assertIn(token, s)

    def test_material_is_not_private(self):
        s=self.source
        for token in (
            "n71_private_calibration", "/home/", "PRIVATE KEY",
            "device_serial", "private_fw", "nvmem_cell_write(", "request_firmware(",
        ):
            self.assertNotIn(token, s)

    def test_explicit_fail_closed_on_incomplete_message(self):
        self.assertIn("SEGMENTED_RESET_NOP_SHORT=", self.source)
        self.assertIn("return err;", self.source)
        self.assertIn("memzero_explicit(tx, SEG_FRAME_BYTES)", self.source)


if __name__ == "__main__":
    unittest.main()
