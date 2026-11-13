#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Require reversible module tests without permitting forced unload."""
from pathlib import Path
import unittest

PATH=(Path(__file__).resolve().parents[1]/
      'experimental/port1/n71-c5-module-unload.config')

class ModuleUnloadConfig(unittest.TestCase):
    def test_exact_safe_delta(self):
        lines=[line.strip() for line in PATH.read_text().splitlines()
               if line.strip() and not line.startswith('# SPDX') and
               not line.startswith('# Minimal') and
               not line.startswith('# Preserve') and
               not line.startswith('# This fragment')]
        self.assertEqual(lines,[
            'CONFIG_MODULES=y',
            'CONFIG_MODULE_UNLOAD=y',
            '# CONFIG_MODULE_FORCE_UNLOAD is not set',
            '# CONFIG_MODULE_UNLOAD_TAINT_TRACKING is not set'])

    def test_no_pcie_activation_in_kconfig_fragment(self):
        contents=PATH.read_text()
        for prohibited in ('CONFIG_PCIE_APPLE=', 'CONFIG_APPLE_DART=',
                           'CONFIG_MODULE_FORCE_UNLOAD=y',
                           'CONFIG_MODULE_UNLOAD_TAINT_TRACKING=y'):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited,contents)

if __name__=='__main__':unittest.main()
