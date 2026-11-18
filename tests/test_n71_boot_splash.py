#!/usr/bin/env python3
"""Host-only tests for the optional 750x1334 RAM splash."""
from __future__ import annotations
import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/n71_boot_splash_prepare.py"
splash = None
if Image is not None:
    spec = importlib.util.spec_from_file_location("n71_boot_splash_prepare", SCRIPT)
    splash = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(splash)


@unittest.skipIf(Image is None, "Pillow is required for the host artwork converter")
class BootSplashTests(unittest.TestCase):
    def test_safe_letterbox_and_framebuffer_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inp = root / "art.png"
            Image.new("RGB", (400, 400), (0, 248, 16)).save(inp)
            out = root / "generated"
            result = splash.prepare(inp, out)
            self.assertEqual(result["raw_bytes"], 4_002_000)
            raw = gzip.decompress((out / "splash.bgrx.gz").read_bytes())
            self.assertEqual(len(raw), 4_002_000)
            # Black letterbox in top-left, BGRX center pixel is green.
            self.assertEqual(raw[0:3], bytes([0, 0, 0]))
            center = ((1334 // 2) * 750 + (750 // 2)) * 4
            self.assertEqual(raw[center:center + 3], bytes([16, 248, 0]))
            with Image.open(out / "splash-iphone6s-750x1334.png") as preview:
                self.assertEqual(preview.size, (750, 1334))
            self.assertEqual((out / "boot-mode").read_text(), "showcase\n")
            with self.assertRaises(FileExistsError):
                splash.prepare(inp, out)


if __name__ == "__main__":
    unittest.main()
