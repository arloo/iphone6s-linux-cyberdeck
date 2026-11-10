"""Offline regression tests for our operator-provided RAM-only payload packer."""
from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pack_ram", ROOT / "scripts/pack_ram.py")
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)


class RAMImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.m1n1 = root / "m1n1"
        self.m1n1.write_bytes(b"m1n1-fixture")
        self.a = root / "s8000.dtb"
        self.b = root / "s8003.dtb"
        fdt = b"\xd0\x0d\xfe\xed" + struct.pack(">I", 40) + bytes(32)
        self.a.write_bytes(fdt)
        self.b.write_bytes(fdt[:-1] + b"\x01")
        self.image = root / "Image.gz"
        self.image.write_bytes(gzip.compress(b"synthetic-arm64-kernel"))
        self.initramfs = root / "initramfs.gz"
        self.initramfs.write_bytes(gzip.compress(b"synthetic-initramfs"))
        self.out = root / "output" / "m1n1-linux.bin"

    def tearDown(self):
        self.temp.cleanup()

    def test_reproduces_upstream_exact_concatenation_contract(self):
        inputs = [
            PACK.validated_regular_file(str(self.m1n1), "m1n1"),
            PACK.validated_regular_file(str(self.a), "dtb"),
            PACK.validated_regular_file(str(self.b), "dtb"),
            PACK.validated_regular_file(str(self.image), "kernel"),
            PACK.validated_regular_file(str(self.initramfs), "initramfs"),
        ]
        digest = PACK.pack(*inputs, self.out, "console=tty0 hl_rd=shell")
        expected = (
            self.m1n1.read_bytes() + b"chosen.bootargs=console=tty0 hl_rd=shell\n"
            + self.a.read_bytes() + self.b.read_bytes()
            + self.image.read_bytes() + self.initramfs.read_bytes()
        )
        self.assertEqual(self.out.read_bytes(), expected)
        self.assertEqual(digest, PACK.sha256_file(self.out))

    def test_never_overwrites_existing_payload(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text("protected")
        with self.assertRaises(FileExistsError):
            PACK.pack(self.m1n1, self.a, self.b, self.image,
                      self.initramfs, self.out, "console=tty0")
        self.assertEqual(self.out.read_text(), "protected")

    def test_rejects_bad_board_dtb(self):
        self.b.write_bytes(b"NOT-A-DTB")
        with self.assertRaisesRegex(ValueError, "FDT"):
            PACK.validated_regular_file(str(self.b), "dtb")

    def test_rejects_truncated_dtb(self):
        self.a.write_bytes(b"\xd0\x0d\xfe\xed" + struct.pack(">I", 400) + bytes(32))
        with self.assertRaisesRegex(ValueError, "total size"):
            PACK.validated_regular_file(str(self.a), "dtb")

    def test_rejects_symlinked_input(self):
        link = self.m1n1.parent / "link-to-m1n1"
        link.symlink_to(self.m1n1)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            PACK.validated_regular_file(str(link), "m1n1")

    def test_rejects_non_gzip_kernel(self):
        self.image.write_bytes(b"fake-kernel")
        with self.assertRaisesRegex(ValueError, "gzip"):
            PACK.validated_regular_file(str(self.image), "kernel")

    def test_rejects_corrupted_gzip_crc(self):
        bad = bytearray(self.image.read_bytes())
        bad[-5] ^= 0x01
        self.image.write_bytes(bad)
        with self.assertRaises((OSError, EOFError, gzip.BadGzipFile)):
            PACK.check_gzip(self.image)

    def test_rejects_newline_in_bootargs(self):
        with self.assertRaisesRegex(ValueError, "arguments"):
            PACK.pack(self.m1n1, self.a, self.b, self.image,
                      self.initramfs, self.out, "console=tty0\nbad=value")

    def test_package_requires_both_foundry_dtbs(self):
        self.b.unlink()
        with self.assertRaises(FileNotFoundError):
            PACK.validated_regular_file(str(self.b), "dtb")


if __name__ == "__main__":
    unittest.main()
