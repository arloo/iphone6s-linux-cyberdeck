#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed source regression for N71 PMGR powerstage (never activates HW)."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]/'experimental/port1'
SRC=(ROOT/'pcie-apple-s8000-port1-powerstage.c').read_text()
DTS=(ROOT/'s8000-n71-port1-powerstage-disabled.dts').read_text()

class N71PowerstageInertTests(unittest.TestCase):
    def test_explicit_status_disabled(self):
        self.assertRegex(DTS,r'status\s*=\s*"disabled"\s*;')
        self.assertNotRegex(DTS,r'status\s*=\s*"okay"\s*;')

    def test_different_compatible_from_safe_preflight(self):
        self.assertIn('apple,n71-s8000-pcie-port1-powerstage',DTS)
        self.assertIn('apple,n71-s8000-pcie-port1-powerstage',SRC)
        self.assertNotIn('apple,n71-s8000-pcie-port1-preflight',SRC)

    def test_explicit_module_param_default_false(self):
        self.assertRegex(SRC,r'static\s+bool\s+allow_power_test\s*;')
        self.assertIn('module_param(allow_power_test, bool, 0400)',SRC)
        self.assertIn('if (!allow_power_test)',SRC)
        self.assertIn('return -EOPNOTSUPP;',SRC)

    def test_power_domain_names_and_order(self):
        self.assertIn('power-domain-names = "ref", "aux", "link1"',DTS)
        self.assertIn('"ref", "aux", "link1"',SRC)
        self.assertNotIn('"link0"',DTS)
        self.assertNotIn('"link2"',DTS)
        self.assertNotIn('"link3"',DTS)

    def test_phy_and_parent_providers_explicit(self):
        self.assertIn('power-domains = <&ps_pcie_ref>, <&ps_pcie_aux>, <&ps_pcie_link1>',DTS)
        self.assertNotIn('<&ps_pcie_link0>',DTS)
        self.assertNotIn('<&ps_pcie_link2>',DTS)

    def test_power_on_only_after_descriptor_validation(self):
        index_check=SRC.index('n71_port1_check_descriptors(pdev);')
        attach=SRC.index('dev_pm_domain_attach_list(&pdev->dev')
        self.assertLess(index_check,attach)
        self.assertIn('of_property_count_u32_elems(np, "power-domains") != 3',SRC)
        self.assertIn('of_property_count_strings(np, "power-domain-names") != 3',SRC)

    def test_detach_on_remove(self):
        self.assertIn('PD_FLAG_ATTACH_POWER_ON | PD_FLAG_DETACH_POWER_OFF',SRC)
        self.assertIn('dev_pm_domain_detach_list(state->attached)',SRC)

    def test_no_mmio_gpio_dma_pci_bus_activity(self):
        content=SRC.split('*/',1)[1]
        forbidden=['ioremap(', 'readl(', 'writel(', 'gpiod_get(',
                   'gpiod_set_value(', 'pci_host_probe(',
                   'pci_scan_root_bus(', 'iommu_attach_device(',
                   'dma_map_', 'reset_control_assert(']
        for bad in forbidden:
            with self.subTest(bad=bad):self.assertNotIn(bad,content)

    def test_n71_only_and_port1_only(self):
        self.assertIn('of_machine_is_compatible("apple,n71")',SRC)
        self.assertIn('of_machine_is_compatible("apple,s8000")',SRC)
        self.assertIn('id != 1',SRC)
        for name,num in [('apple,perst-pin',161),('apple,clkreq-pin',165),
                         ('apple,device-wake-pin',73)]:
            self.assertIn('{ "'+name+'", '+str(num)+' }',SRC)

if __name__=='__main__':unittest.main()
