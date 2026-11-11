"""Offline checks of the experimental RAM-only fbdev/evdev GUI."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"examples/fb-cyberdeck/cyberdeck.c"
FONT_TOOL=ROOT/"tools/gen_cyberdeck_font.py"
FONT=Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

class CyberdeckFramebufferTest(unittest.TestCase):
    def test_static_source_includes_expected_screen_gates(self):
        s=SRC.read_text()
        for required in (
            'open("/dev/fb0",O_RDWR',
            'open("/dev/input/event0",O_RDONLY|O_NONBLOCK',
            'ioctl(fbfd,FBIOGET_FSCREENINFO',
            'ioctl(fbfd,FBIOGET_VSCREENINFO',
            'W!=750||H!=1334||vinfo.bits_per_pixel!=32',
            'ABS_MT_SLOT','ABS_MT_TRACKING_ID',
            'ABS_MT_POSITION_X','ABS_MT_POSITION_Y','SYN_REPORT',
            'pwrite(fbfd,', 'signal(SIGTERM,on_signal)',
        ):
            with self.subTest(required=required):
                self.assertIn(required,s)

    def test_unsafe_device_controls_excluded(self):
        s=SRC.read_text()
        for unsafe in (
            "/dev/mem", "/dev/nvme", "/dev/mtd", "EVIOCGRAB",
            "runtime_wake", "runtime_type1_setup", "runtime_af",
            "gpiod_set_value", "ioctl(fbfd,FBIOBLANK",
            "system(", "execve(", "unlink(",
        ):
            self.assertNotIn(unsafe,s)

    def test_bitmap_generator_is_deterministic(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        if not FONT.exists():
            self.skipTest("Local licensed TTF absent")
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/"a.h"
            b=Path(temp)/"b.h"
            for target in (a,b):
                subprocess.run([sys.executable,str(FONT_TOOL),
                                "--font",str(FONT),"--output",str(target)],
                               check=True,capture_output=True,timeout=10)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(a.read_text().count("/* char "),95)

    def test_host_compilation_without_font_distribution(self):
        try:
            import PIL
        except ImportError:
            self.skipTest("Pillow not installed")
        cc=shutil.which("cc")
        if not cc or not FONT.exists():
            self.skipTest("Host compiler or local TTF absent")
        with tempfile.TemporaryDirectory() as temp:
            dst=Path(temp)/"font_data.h"
            subprocess.run([sys.executable,str(FONT_TOOL),
                            "--font",str(FONT),"--output",str(dst)],
                           check=True,capture_output=True,timeout=10)
            subprocess.run([cc,"-Wall","-Wextra","-Werror",
                            "-fsyntax-only","-I",str(temp),str(SRC)],
                           check=True,capture_output=True,timeout=10)

if __name__=="__main__":
    unittest.main()
