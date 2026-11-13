#!/usr/bin/env python3
"""Test the real loader against an intercepted kernel syscall, never a phone."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = r"""
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

static unsigned int calls;
static void report(void) { printf("INTERCEPT_CALLS=%u\n", calls); }
long __wrap_syscall(long number, ...)
{
    va_list args;
    int fd, flags;
    const char *params, *expected, *failure;
    if (!calls) atexit(report);
    calls++;
    va_start(args, number);
    fd = va_arg(args, int);
    params = va_arg(args, const char *);
    flags = va_arg(args, int);
    va_end(args);
    expected = getenv("EXPECT_PARAMETERS");
    if (number != SYS_finit_module || flags != 0 ||
        !(fcntl(fd, F_GETFD) & FD_CLOEXEC) ||
        (expected && strcmp(params, expected))) {
        errno = EINVAL;
        return -1;
    }
    failure = getenv("FAKE_KERNEL_ERRNO");
    if (failure && atoi(failure)) {
        errno = atoi(failure);
        return -1;
    }
    return 0;
}
"""

class ModuleOnceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if not compiler:
            raise unittest.SkipTest("native C compiler unavailable")
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        (cls.base / "syscall-wrapper.c").write_text(WRAPPER)
        cls.loader = cls.base / "loader"
        subprocess.run([
            compiler, "-O2", "-Wall", "-Wextra", "-Werror",
            str(ROOT / "tools/n71-module-once.c"),
            str(cls.base / "syscall-wrapper.c"),
            "-Wl,--wrap=syscall", "-o", str(cls.loader)
        ], check=True, capture_output=True)
        cls.module = cls.base / "fake.ko"
        cls.module.write_bytes(b"OFFLINE SYNTHETIC MODULE; NEVER LOADED")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_loader(self, path=None, parameters="", error=0):
        env = dict(os.environ, EXPECT_PARAMETERS=parameters,
                   FAKE_KERNEL_ERRNO=str(error))
        return subprocess.run(
            [str(self.loader), str(path or self.module), parameters],
            text=True, capture_output=True, env=env
        )

    def test_success_preserves_full_parameter_string(self):
        result = self.run_loader(parameters="armed=1 stage=8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INTERCEPT_CALLS=1", result.stdout)
        self.assertIn("FINIT_MODULE_ONCE rc=0 errno=0", result.stdout)

    def test_unsupported_finit_module_never_retries_init_module(self):
        result = self.run_loader(error=38)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INTERCEPT_CALLS=1", result.stdout)
        self.assertIn("no retry performed", result.stderr)

    def test_rejected_experiment_never_repeats_module_init(self):
        result = self.run_loader(error=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INTERCEPT_CALLS=1", result.stdout)

    def test_invalid_parameter_error_never_retries(self):
        result = self.run_loader(error=22)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INTERCEPT_CALLS=1", result.stdout)

    def test_missing_file_never_calls_kernel(self):
        result = self.run_loader(self.base / "absent.ko")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("INTERCEPT_CALLS", result.stdout)

    def test_directory_never_calls_kernel(self):
        result = self.run_loader(self.base)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("INTERCEPT_CALLS", result.stdout)

    def test_symlink_never_calls_kernel(self):
        link = self.base / "link.ko"
        link.symlink_to(self.module)
        result = self.run_loader(link)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("INTERCEPT_CALLS", result.stdout)

    def test_empty_file_never_calls_kernel(self):
        empty = self.base / "empty.ko"
        empty.touch()
        result = self.run_loader(empty)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("INTERCEPT_CALLS", result.stdout)

    def test_oversized_file_never_calls_kernel(self):
        large = self.base / "large.ko"
        with large.open("wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        result = self.run_loader(large)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("INTERCEPT_CALLS", result.stdout)

if __name__ == "__main__":
    unittest.main()
