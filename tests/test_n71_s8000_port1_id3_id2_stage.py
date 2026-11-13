#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed source regression for physically verified S8000 PCIe port1 RMW."""
from pathlib import Path
import re
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(P/'pcie-apple-s8000-port1-id3-id2-stage.c').read_text()
MAKE=(P/'Makefile').read_text()

class N71S8000Port1ID3ID2Stage(unittest.TestCase):
    def test_module_build_target_and_match_samsung_exclusively(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-id3-id2-stage.o',MAKE)
        for token in ('of_machine_is_compatible("apple,n71")',
                      'of_machine_is_compatible("apple,s8000")',
                      '"apple,s8000-pcie-research-blocked"',
                      '"research,hardware-activation-blocked"'):
            self.assertIn(token,S)

    def test_explicit_double_gate_defaults_to_no_writes(self):
        for token in ('static bool armed;', 'static bool stage_id3_id2;',
                      'module_param(armed, bool, 0400)',
                      'module_param(stage_id3_id2, bool, 0400)',
                      'if (!armed || !stage_id3_id2 ||'):
            self.assertIn(token,S)

    def test_only_three_port_specific_power_consumers(self):
        self.assertIn('static const char * const names[] = { "ref", "aux", "link1" };',S)
        self.assertIn('pm_runtime_resume_and_get(virt[i])',S)
        self.assertIn('pm_runtime_put_sync_suspend(virt[i - 1])',S)
        self.assertIn('dev_pm_domain_detach(virt[i - 1], true)',S)

    def test_exact_original_mmio_and_pinctrl_windows_only(self):
        self.assertIn('#define N71_ROOT_COMMON_PHYS 0x600000000ULL',S)
        self.assertIn('#define N71_PINCTRL_PHYS 0x20f100000ULL',S)
        self.assertIn('pin161 = readl(',S)
        self.assertIn('pin165 = readl(',S)
        self.assertIn('id4 = readl(',S)
        self.assertIn('id5 = readl(',S)

    def test_hardware_start_requires_byte_exact_safe_snapshot(self):
        for token in ('pin161 != 0x00072200','pin165 != 0x00076a21',
                      'id1 != 0x00000010','id2 != 0x01000100',
                      'id3 != 0x00000100','id4 != 0','id5 != 0'):
            self.assertIn(token,S)
        self.assertLess(S.index('id3 != 0x00000100'), S.index('writel(id3 | BIT(0)'))

    def test_only_port1_id3_and_id2_control_writes(self):
        statements=re.findall(r'^\s*writel\(([^;]+)\);',S,re.M)
        self.assertEqual(len(statements),5)
        self.assertEqual([x.rsplit('+',1)[1].strip() for x in statements],
                         ['0x194', '0x194', '0x180', '0x180', '0x194'])
        self.assertIn('writel(id3 | BIT(0)',S)
        self.assertIn('writel(id2 & ~BIT(8)',S)
        self.assertNotIn('writel(id4',S)

    def test_reverse_rollback_before_power_down(self):
        assert_id2=S.index('writel(id2 & ~BIT(8)')
        restore_id2=S.index('writel(id2,')
        restore_id3=S.index('writel(id3,',restore_id2)
        release=S.index('pm_runtime_put_sync_suspend(virt[i - 1])')
        self.assertLess(assert_id2,restore_id2)
        self.assertLess(restore_id2,restore_id3)
        self.assertLess(restore_id3,release)
        self.assertIn('restored2 != id2',S)
        self.assertIn('restored != id3',S)

    def test_reset_phy_dart_and_pci_enumeration_absent(self):
        for forbidden in ('gpiod_get(', 'gpio_request(', 'gpiod_set_value(',
                          'reset_control_deassert(', 'pci_host_probe(',
                          'pci_scan_root_bus(', 'dma_map_',
                          'iommu_attach_device(', 'dev_pm_domain_attach_list('):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,S)

    def test_no_unbounded_pcie_poll_and_cleanup_overlay(self):
        self.assertNotIn('while (readl(',S)
        self.assertIn('of_overlay_remove(&n71_overlay_id)',S)
        self.assertIn('iounmap(shared_regs)',S)
        self.assertIn('iounmap(gpio_regs)',S)
        self.assertIn('return -ENODEV;',S)

if __name__=='__main__':unittest.main()
