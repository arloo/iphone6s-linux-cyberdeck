"""Offline checks for the public N71 guarded HBPP identification diagnostic.

These tests do not exercise physical hardware or private calibration. The
observed historical read frame is protocol metadata, not a device identifier.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/touch/n71-hbpp-once/n71_hbpp_once.c"
MAKEFILE = ROOT / "tools/touch/n71-hbpp-once/Makefile"


def decode_strict_read(packet: bytes) -> int:
    if len(packet) != 8:
        raise ValueError("HBPP register reply must be eight bytes")
    status = int.from_bytes(packet[:2], "big")
    if status != 0x4C39:
        raise ValueError("Unexpected status, not READ_DATA")
    checksum = int.from_bytes(packet[6:8], "big")
    if checksum != sum(packet[2:6]) & 0xFFFF:
        raise ValueError("Invalid HBPP checksum")
    value = int.from_bytes(packet[2:4], "big") | (
        int.from_bytes(packet[4:6], "big") << 16
    )
    return value


class LiveN71SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()

    def test_makefile_target_isolated(self):
        self.assertEqual(MAKEFILE.read_text().strip(), "obj-m += n71_hbpp_once.o")

    def test_known_hardware_reply_strictly_decodes(self):
        packet = bytes.fromhex("4c 39 15 c1 43 4d 01 66")
        self.assertEqual(decode_strict_read(packet), 0x434D15C1)

    def test_any_bad_checksum_is_rejected(self):
        packet = bytearray.fromhex("4c 39 15 c1 43 4d 01 66")
        for i in range(2, 8):
            with self.subTest(position=i):
                mutated = bytearray(packet)
                mutated[i] ^= 1
                with self.assertRaises(ValueError):
                    decode_strict_read(mutated)

    def test_wrong_status_is_rejected(self):
        for status in ("1f01", "4879", "4bc1", "0000", "ffff"):
            with self.subTest(status=status):
                packet = bytes.fromhex(status + "15c1434d0166")
                with self.assertRaises(ValueError):
                    decode_strict_read(packet)

    def test_truncated_and_overlong_replies_rejected(self):
        sample = bytes.fromhex("4c3915c1434d0166")
        for length in (0, 1, 2, 6, 7, 9, 10, 16):
            with self.subTest(length=length):
                with self.assertRaises(ValueError):
                    decode_strict_read((sample + bytes(16))[:length])

    def test_source_requires_status_and_checksum(self):
        s = self.source
        self.assertIn("status != HBPP_READ_DATA || returned_sum != sum", s)
        self.assertIn("return -EBADMSG", s)
        self.assertIn("REJECT_INVALID_READ_REPLY", s)
        self.assertIn("HBPP_VERSION_ADDR 0x10008ffcU", s)

    def test_source_does_not_upload_calibration_or_execute(self):
        for forbidden in (
            "request_firmware(",
            "spi_write(",
            "HBPP_EXECUTE",
            "HBPP_REG_WRITE",
            "0x1e33",
            "0x1d53",
            "nvmem_cell_write(",
            "kernel_write(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_single_use_with_bounded_watchdog(self):
        s = self.source
        self.assertIn("WATCHDOG_MS 1500U", s)
        self.assertIn("schedule_delayed_work(", s)
        self.assertIn("shutdown_hardware(\"DIRECT\")", s)
        self.assertIn("shutdown_hardware(\"WATCHDOG\")", s)
        self.assertIn("atomic_cmpxchg(&g.restore_owner, 0, 1)", s)

    def test_failure_cleans_up_before_release(self):
        s = self.source
        self.assertIn('gpiod_set_value_cansleep(g.reset, 1)', s)
        self.assertIn("clk_disable_unprepare(g.clk)", s)
        self.assertIn("ANALOG_RESTORE_RETRIES_EXHAUSTED", s)
        self.assertIn("spi_unregister_device(g.spi)", s)
        self.assertIn("FINAL_BOARD_BASELINE_PASS", s)

    def test_hardware_profiles_are_fixed_n71_only(self):
        s = self.source
        for required in (
            "PMGR_BASE 0x800002eeU",
            "PMGR_ACTIVE 0x000802dcU",
            "RESET_BASE 0x00072202U",
            "ANALOG_BASE 0x0f",
            "ANALOG_ACTIVE 0x1f",
            "SPI_HZ 1000000U",
            "of_device_is_available(touch)",
        ):
            self.assertIn(required, s)

    def test_no_identifying_private_material_in_source(self):
        s = self.source
        self.assertNotRegex(s, r"/home/[A-Za-z][A-Za-z0-9_-]+/|@[a-z]+\.com")

    def test_controller_version_is_not_assumed_to_be_panel_vendor(self):
        self.assertIn("VERSION_MATCHES_PRIOR_N71_DIAGNOSTIC", self.source)
        self.assertIn("VALID_CONTROLLER_VERSION", self.source)
        self.assertNotIn("DISPLAY_VENDOR=", self.source)


if __name__ == "__main__":
    unittest.main()
