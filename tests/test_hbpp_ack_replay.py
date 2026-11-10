"""Offline ACK regression and high-volume deterministic fault injection."""
import importlib.util
import itertools
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools/touch/hbpp_ack_replay.py"
SPEC = importlib.util.spec_from_file_location("hbpp_ack_replay", SRC)
ACK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ACK
SPEC.loader.exec_module(ACK)
PATCH = ROOT / "patches/0003-n71-hbpp-cal-data-reqcal-pending-rfc.patch"


class PollRegressionTests(unittest.TestCase):
    def test_reqcal_then_ack_data_is_reachable(self):
        self.assertEqual(ACK.replay([ACK.REQ_CAL, ACK.ACK_DATA]), ("ACK", 2))

    def test_reqcal_then_idle_then_ack_data_is_reachable(self):
        self.assertEqual(
            ACK.replay([ACK.REQ_CAL, ACK.IDLE, ACK.ACK_DATA]), ("ACK", 3)
        )

    def test_reqcal_does_not_count_as_ack(self):
        self.assertEqual(ACK.replay([ACK.REQ_CAL] * 50), ("TIMEOUT", 50))

    def test_reg_write_still_rejects_reqcal(self):
        self.assertEqual(ACK.replay([ACK.REQ_CAL, ACK.ACK_REG],
                                    ACK.ACK_REG), ("UNEXPECTED", 1))

    def test_no_ack_beyond_limit(self):
        self.assertEqual(
            ACK.replay([ACK.IDLE] * 50 + [ACK.ACK_DATA]), ("TIMEOUT", 50)
        )

    def test_ack_on_last_poll(self):
        self.assertEqual(
            ACK.replay([ACK.REQ_CAL] * 49 + [ACK.ACK_DATA]), ("ACK", 50)
        )

    def test_wrong_ack_is_error(self):
        self.assertEqual(
            ACK.replay([ACK.ACK_REG, ACK.ACK_DATA]), ("UNEXPECTED", 1)
        )

    def test_poller_limit_enforced(self):
        for n in (0, -1, 301):
            with self.subTest(limit=n):
                with self.assertRaises(ValueError):
                    ACK.replay([], limit=n)

    def test_unexpected_status_error(self):
        self.assertEqual(ACK.replay([0x1234, ACK.ACK_DATA]),
                         ("UNEXPECTED", 1))

    def test_exhaustive_short_sequences(self):
        words = [ACK.ACK_DATA, ACK.ACK_REG, ACK.REQ_CAL, ACK.IDLE,
                 ACK.NOP, 0, 0xFFFF, 0x1234]
        for n in (1, 2, 3):
            for seq in itertools.product(words, repeat=n):
                outcome, polls = ACK.replay(seq)
                self.assertIn(outcome, ("ACK", "UNEXPECTED", "TIMEOUT"))
                self.assertLessEqual(polls, 50)
                if outcome == "ACK":
                    self.assertEqual(seq[polls - 1], ACK.ACK_DATA)

    def test_100000_random_sequences_never_false_ack(self):
        rng = random.Random(0xA9B00)
        words = [ACK.ACK_DATA, ACK.ACK_REG, ACK.REQ_CAL,
                 ACK.IDLE, ACK.NOP, 0, 0xFFFF, 0x1234]
        for _ in range(100_000):
            n = rng.randrange(1, 65)
            seq = [rng.choice(words) for _ in range(n)]
            outcome, polls = ACK.replay(seq)
            self.assertLessEqual(polls, 50)
            if outcome == "ACK":
                self.assertEqual(seq[polls - 1], ACK.ACK_DATA)
                self.assertTrue(all(
                    ACK.classify_status(v, ACK.ACK_DATA) == "PENDING"
                    for v in seq[:polls - 1]
                ))

    def test_kernel_patch_limits_change_to_data_ack(self):
        content = PATCH.read_text()
        self.assertIn("expected == APPLE_Z2_HBPP_ACK_DATA", content)
        self.assertIn("status == APPLE_Z2_HBPP_REQ_CAL", content)
        self.assertIn("status != APPLE_Z2_HBPP_IDLE", content)
        self.assertNotIn("return 0; /* allow REQ_CAL", content)

    def test_no_phone_io(self):
        code = SRC.read_text()
        for disallowed in ("spidev", "socket", "subprocess", "open(", "serial"):
            self.assertNotIn(disallowed, code)


if __name__ == "__main__":
    unittest.main()
