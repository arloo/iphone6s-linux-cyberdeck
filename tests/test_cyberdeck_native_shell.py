"""Compile/run the real UI parser, key dispatch and PTY without phone hardware."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('gcc'), 'host C compiler unavailable')
class NativeCyberdeckShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.root = Path(cls.work.name)
        source = cls.root / 'cyberdeck-shell'
        source.mkdir()
        font = cls.root / 'fb-cyberdeck'
        font.mkdir()
        # Synthetic glyphs test rendering bounds; no external font is required.
        (font / 'font_data.h').write_text(
            '#include <stdint.h>\nstatic const uint16_t font14x24[95][24]={{0}};\n')
        shutil.copy2(ROOT / 'examples/cyberdeck-shell/cyberdeck-shell.c', source)
        cls.binary = cls.root / 'ui'
        subprocess.run(['gcc', '-O1', '-Wall', '-Wextra', '-Werror',
                        '-o', str(cls.binary), str(source / 'cyberdeck-shell.c'),
                        '-lutil'], check=True, capture_output=True)
        cls.env = {'PATH': '/usr/bin:/bin', 'HOME': str(cls.root), 'LC_ALL': 'C'}

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def test_keyboard_dispatch_executes_real_pty_command(self):
        result = subprocess.run([str(self.binary), '--selftest'], env=self.env,
                                text=True, capture_output=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('native_pty_shell=1', result.stdout)
        self.assertIn('terminal_parser=1', result.stdout)

    def test_all_views_render_without_accessing_a_framebuffer(self):
        header = b'P6\n750 1334\n255\n'
        for page in range(4):
            with self.subTest(page=page):
                output = self.root / f'view-{page}.ppm'
                subprocess.run([str(self.binary), '--preview', str(output)],
                               env={**self.env, 'N71_PREVIEW_PAGE': str(page)},
                               check=True, capture_output=True, timeout=5)
                data = output.read_bytes()
                self.assertTrue(data.startswith(header))
                self.assertEqual(len(data), len(header) + 750 * 1334 * 3)

    def test_invalid_cli_does_not_attempt_device_access(self):
        result = subprocess.run([str(self.binary), '--invalid'], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage:', result.stderr)
