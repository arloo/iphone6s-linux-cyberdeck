"""Synthetic checks for N71 opt-in runtime wake/report-info.
These tests cannot prove hardware functionality.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/0008-n71-opt-in-z2-runtime-wake-d9-rfc.patch"

def frame(opcode, report=0):
    data = bytearray(16)
    data[0], data[1] = opcode, report
    data[14:16] = sum(data[:14]).to_bytes(2, "little")
    return bytes(data)

class N71WakeD9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text()
        cls.additions = "\n".join(
            line[1:] for line in cls.patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def test_wake_frame_matches_sandcastle_checksum(self):
        self.assertEqual(frame(0xee).hex(), "ee" + "00" * 13 + "ee00")

    def test_d9_frame_matches_sandcastle_checksum(self):
        self.assertEqual(frame(0xe3, 0xd9).hex(), "e3d9" + "00" * 12 + "bc01")

    def test_explicit_sysfs_and_board_gates(self):
        for gate in (
            "static DEVICE_ATTR_WO(runtime_wake)",
            "static DEVICE_ATTR_WO(runtime_d9)",
            "static DEVICE_ATTR_RO(runtime_state)",
            "z2->n71_wake_attempted = true;",
            "if (z2->n71_wake_attempted)",
            "z2->n71_d9_attempts >= 2",
            "if (!z2->n71_wake_attempted || z2->n71_wake_rc)",
            'of_machine_is_compatible("apple,n71")',
            "READ_ONCE(z2->booted)",
            "mutex_lock(&z2->report_lock)",
            "mutex_unlock(&z2->report_lock)",
            "put_unaligned_le16(sum, z2->tx_buf + 14)",
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.additions)

    def test_no_automatic_wake_or_unbounded_retry(self):
        self.assertEqual(self.additions.count("apple_z2_n71_runtime_cmd(z2,"), 2)
        for unsafe in ("request_firmware(", "gpiod_set_value(",
                       "regulator_enable(", "clk_prepare_enable(",
                       "while (", "for (;;)", "msleep("):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, self.additions)

    def test_privacy_and_safety(self):
        for unsafe in ("print_hex_dump(", "%*ph", "apple,z2-cal-blob",
                       "devm_gpiod_get(", "kernel_restart("):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, self.additions)

if __name__ == "__main__":
    unittest.main()
