#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static fail-closed regression for live, read-only N71 port1 FDT observer."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]/'experimental/port1'
SOURCE=(ROOT/'pcie-apple-s8000-port1-live-dt-observer.c').read_text()
BUILD=(ROOT/'Makefile').read_text()

class N71Port1LiveDTObserverTests(unittest.TestCase):
    def test_built_as_separate_module(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-live-dt-observer.o',BUILD)
        self.assertIn('module_init(n71_port1_live_dt_observer_init)',SOURCE)
        self.assertIn('module_exit(n71_port1_live_dt_observer_exit)',SOURCE)

    def test_restricted_n71_s8000_compatible(self):
        self.assertIn('of_machine_is_compatible("apple,n71")',SOURCE)
        self.assertIn('of_machine_is_compatible("apple,s8000")',SOURCE)
        self.assertIn('"/soc/pcie-port1-preflight@602000000"',SOURCE)

    def test_only_blocked_runtime_dt_accepted(self):
        self.assertIn('"apple,s8000-pcie-research-blocked"',SOURCE)
        self.assertIn('of_device_is_compatible(np, N71_BLOCKED_COMPAT)',SOURCE)
        self.assertIn('of_property_read_bool(np, "research,hardware-activation-blocked")',SOURCE)

    def test_all_three_windows_pinned_to_real_n71(self):
        windows=[(int(a,16),int(b,16)) for a,b in re.findall(
            r'0x([0-9a-f]+)ULL, 0x([0-9a-f]+)ULL',SOURCE)]
        self.assertEqual(windows,[(0x602000000,0x4000),
                                  (0x602004000,0x4000),
                                  (0x602008000,0x4000)])
        self.assertIn('"dart1-reg"',SOURCE)
        self.assertNotIn('0x600000000ULL',SOURCE)

    def test_exact_resource_shape_checked(self):
        for token in ('of_property_count_strings(np, "reg-names")',
                      'of_property_count_u32_elems(np, "reg") != 12',
                      'of_address_to_resource(np, i, &res)',
                      'res.start != expected->base',
                      'resource_size(&res) != expected->length'):
            self.assertIn(token,SOURCE)

    def test_apple_logical_mapper_not_a_physical_sid(self):
        self.assertIn('"research,dart1-mapper-index"',SOURCE)
        self.assertIn('"research,pcie-port-index"',SOURCE)
        self.assertIn('"research,refclk-to-perst-delay-us"',SOURCE)
        self.assertIn('val != 100',SOURCE)
        self.assertIn('physical DART requester/SID isolation',SOURCE)

    def test_no_mmio_gpio_pm_dma_pci_activity(self):
        impl=SOURCE.split('*/',1)[1]
        forbidden=['ioremap(', 'readl(', 'writel(', 'memremap(',
                   'gpiod_get(', 'gpio_request(', 'gpiod_set_value(',
                   'dev_pm_domain_attach(', 'pm_runtime_get(',
                   'pci_host_probe(', 'pci_scan_root_bus(',
                   'dma_map_', 'iommu_attach_device(',
                   'reset_control_assert(', 'reset_control_deassert(']
        for token in forbidden:
            with self.subTest(token=token):self.assertNotIn(token,impl)

    def test_no_device_driver_binding(self):
        self.assertNotIn('platform_driver_register(',SOURCE)
        self.assertNotIn('module_platform_driver(',SOURCE)
        self.assertNotIn('platform_get_resource(',SOURCE)

    def test_error_stops_observer_and_balances_node_reference(self):
        self.assertIn('of_node_put(np)',SOURCE)
        self.assertIn('return ret;',SOURCE)
        self.assertIn('return -ENODEV;',SOURCE)
        self.assertIn('if (ret)',SOURCE)

if __name__=='__main__':unittest.main()
