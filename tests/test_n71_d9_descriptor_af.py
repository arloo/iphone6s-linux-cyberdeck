"""Synthetic safety gates for N71/S8000 D9 long read and AF enable.

These tests do not imply the iPhone touch works.
"""
import unittest
from pathlib import Path

PATCH = Path(__file__).resolve().parents[1] / (
    "patches/0009-n71-d9-geometry-and-optional-af-enable-rfc.patch"
)

def frame(opcode, report=0, data_len=0):
    b=bytearray(16)
    b[:5]=bytes((opcode,report,0,data_len & 255,data_len >> 8))
    b[14:16]=sum(b[:14]).to_bytes(2,"little")
    return bytes(b)

def data_frame(mode):
    if mode==2:
        return bytes([0xa5]*21)
    if mode!=1:
        raise ValueError("mode must be explicitly selected")
    b=bytearray(21)
    b[:5]=bytes((0xe7,0xd9,1,16,0))
    b[19:21]=sum(b[:19]).to_bytes(2,"little")
    return bytes(b)

def plausible(left,right,top,bottom):
    return (left < right and top < bottom and
            right-left<=20000 and bottom-top<=20000)

class TestN71D9FetchAF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=PATCH.read_text()
        cls.lines="\n".join(
            line[1:] for line in cls.source.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def test_e7_prepare_checksum(self):
        command=frame(0xe7,0xd9,16)
        self.assertEqual(len(command),16)
        self.assertEqual(command[:5],bytes.fromhex("e7d9001000"))
        self.assertEqual(command[14:],bytes.fromhex("d001"))

    def test_type1_data_frame(self):
        b=data_frame(1)
        self.assertEqual(len(b),21)
        self.assertEqual(b[:5],bytes.fromhex("e7d9011000"))
        self.assertEqual(b[-2:],bytes.fromhex("d101"))

    def test_type2_data_frame(self):
        self.assertEqual(data_frame(2),bytes([0xa5]*21))
        with self.assertRaises(ValueError):
            data_frame(0)

    def test_af_short_write_commit(self):
        b=bytearray(16)
        b[:4]=bytes((0xe4,0xaf,1,0))
        b[-2:]=sum(b[:14]).to_bytes(2,"little")
        self.assertEqual(b[-2:],bytes.fromhex("9401"))
        self.assertEqual(frame(0xe1)[-2:],bytes.fromhex("e100"))

    def test_expected_n71_gates(self):
        for name in (
            "APPLE_Z2_N71_D9_FRAME_LEN         21",
            "APPLE_Z2_N71_D9_DATA_LEN          16",
            "z2->n71_d9_fetch_attempted = true;",
            "z2->n71_d9_fetch_mode = mode;",
            "z2->n71_d9_attempts != 2",
            "z2->n71_d9_size != APPLE_Z2_N71_D9_DATA_LEN",
            "if (z2->n71_d9_fetch_attempted)",
            "if (z2->n71_af_attempted)",
            "z2->n71_af_attempted = true;",
            "z2->n71_d9_geometry_plausible",
            "memcpy(descriptor, z2->rx_buf + 3, sizeof(descriptor))",
            "static DEVICE_ATTR_WO(runtime_d9_fetch)",
            "static DEVICE_ATTR_WO(runtime_af)",
            "mutex_lock(&z2->report_lock)",
            "mutex_unlock(&z2->report_lock)",
        ):
            with self.subTest(name=name):
                self.assertIn(name,self.lines)

    def test_geometry_is_fail_closed(self):
        self.assertTrue(plausible(0,749,0,1333))
        for vals in ((10,10,0,1334),(100,1,0,1334),(0,750,1500,1),
                     (0,20001,0,1334),(0,750,0,20001)):
            with self.subTest(vals=vals):
                self.assertFalse(plausible(*vals))

    def test_no_unbounded_retries_or_private_data_logs(self):
        for unsafe in (
            "while (","for (;;)","msleep(","gpiod_set_value(",
            "regulator_enable(","clk_prepare_enable(","request_firmware(",
            "print_hex_dump(","%*ph","apple,z2-cal-blob"
        ):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe,self.lines)

if __name__ == "__main__":
    unittest.main()
