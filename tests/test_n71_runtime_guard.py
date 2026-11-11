from pathlib import Path
import unittest

PATCH = Path(__file__).resolve().parents[1] / "patches/0007-n71-runtime-read-once-irq-diagnostics-rfc.patch"
MAX_REPORT = 4000
FINGERS_OFFSET = 24
HEADER = 5
FINGER_BYTES = 30

def guarded_length(controller_length):
    return (controller_length + 8) & ~3

def valid_length(controller_length):
    length = guarded_length(controller_length)
    return HEADER + FINGERS_OFFSET <= length <= MAX_REPORT

def valid_fingers(controller_length, count):
    if not valid_length(controller_length):
        return False
    body = guarded_length(controller_length) - HEADER
    return count <= (body - FINGERS_OFFSET) // FINGER_BYTES

class RuntimeReportBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text()

    def test_all_possible_controller_lengths(self):
        for n in range(65536):
            size = guarded_length(n)
            self.assertEqual(valid_length(n), 29 <= size <= 4000)

    def test_finger_count_arithmetic(self):
        for raw in (0, 1, 16, 24, 64, 256, 1000, 3992, 65535):
            for fingers in range(256):
                if valid_fingers(raw, fingers):
                    self.assertLessEqual(HEADER + FINGERS_OFFSET +
                                         fingers * FINGER_BYTES, guarded_length(raw))

    def test_kernel_patch_has_safety_checks(self):
        required = (
            "APPLE_Z2_RX_BUF_SIZE",
            "pkt_len > APPLE_Z2_RX_BUF_SIZE",
            "nfingers > (msg_len - APPLE_Z2_FINGERS_OFFSET)",
            "mutex_lock(&z2->report_lock)",
            "mutex_unlock(&z2->report_lock)",
            "apple_z2_read_packet(z2, &sample)",
            'of_machine_is_compatible("apple,n71")',
            "devm_device_add_group",
            "static DEVICE_ATTR_RO(runtime_probe)",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, self.patch)

    def test_added_lines_do_not_toggle_power_or_firmware(self):
        additions = "\n".join(line[1:] for line in self.patch.splitlines()
                              if line.startswith("+") and not line.startswith("+++"))
        for risky in ("gpiod_set_value(", "regulator_enable(", "regulator_disable(",
                      "clk_prepare_enable(", "request_firmware(", "reboot("):
            self.assertNotIn(risky, additions)

if __name__ == "__main__":
    unittest.main()
