#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed tests for a disabled PMGR consumer descriptor overlay."""
from pathlib import Path
import re
import subprocess
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(P/'pcie-apple-s8000-port1-powerstage-overlay-inert.c').read_text()
H=(P/'n71-s8000-port1-powerstage-runtime-disabled-blob.h').read_text()
D=(P/'n71-s8000-port1-powerstage-runtime-disabled.dts').read_text()
M=(P/'Makefile').read_text()

class N71PowerstageInertOverlayTests(unittest.TestCase):
    def test_separate_arm64_module(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-powerstage-overlay-inert.o',M)
        self.assertIn('module_init(n71_powerstage_overlay_init)',S)
        self.assertIn('module_exit(n71_powerstage_overlay_exit)',S)

    def test_s8000_exclusive_and_boot_guard(self):
        for x in ('of_machine_is_compatible("apple,n71")',
                  'of_machine_is_compatible("apple,s8000")',
                  '"apple,s8000-pcie-research-blocked"',
                  '"research,hardware-activation-blocked"'):
            self.assertIn(x,S)

    def test_explicit_pm_domain_provider_paths(self):
        for path in ('"/power-controller@80148", 0x3a',
                     '"/power-controller@80318", 0x3b',
                     '"/power-controller@80328", 0x3c'):
            self.assertIn(path,S)
        self.assertIn('node->phandle == n71_links[i].phandle',S)
        self.assertIn('"#power-domain-cells"',S)
        self.assertIn('cells == 0',S)

    def test_powerstage_stays_disabled_without_supervision(self):
        self.assertIn('status = "disabled";',D)
        self.assertNotIn('apple,explicit-supervised-power-test;',D)
        self.assertIn('!of_device_is_available(node)',S)
        self.assertIn('!of_property_read_bool(node, "apple,explicit-supervised-power-test")',S)

    def test_inert_node_phandles_resolve_without_attach(self):
        self.assertIn('of_parse_phandle(node, "power-domains", i)',S)
        self.assertIn('of_node_cmp(provider->full_name, n71_links[i].path)',S)
        self.assertIn('power-domains = <0x3a>, <0x3b>, <0x3c>;',D)
        self.assertIn('of_property_count_u32_elems(node, "power-domains") == 3',S)

    def test_embedded_dtbo_bit_exact_and_aligned(self):
        self.assertIn('__attribute__((aligned(8)))',H)
        compiled=subprocess.check_output(['dtc','-q','-@','-I','dts','-O','dtb',
                           str(P/'n71-s8000-port1-powerstage-runtime-disabled.dts')])
        values=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',
                               H.split('= {',1)[1].split('};',1)[0]))
        self.assertEqual(compiled,values)
        self.assertIn(f'n71_port1_powerstage_dtbo_len = {len(values)};',H)

    def test_no_hardware_paths_in_descriptor_loader(self):
        impl=S.split('*/',1)[1]
        forbidden=('ioremap(', 'readl(', 'writel(', 'memremap(', 'gpiod_get(',
                   'gpiod_set_value(', 'gpio_request(', 'dev_pm_domain_attach(',
                   'dev_pm_domain_attach_list(', 'pm_runtime_get(',
                   'reset_control_deassert(', 'pci_host_probe(',
                   'pci_scan_root_bus(', 'dma_map_', 'iommu_attach_device(')
        for needle in forbidden:
            with self.subTest(needle=needle):self.assertNotIn(needle,impl)

    def test_rollbacks_reversible_and_no_probe_opt_in(self):
        self.assertIn('of_overlay_fdt_apply(',S)
        self.assertIn('of_overlay_remove(&n71_changeset_id)',S)
        self.assertIn('n71_changeset_active = false',S)
        self.assertNotIn('allow_power_test',S)

if __name__=='__main__':unittest.main()
