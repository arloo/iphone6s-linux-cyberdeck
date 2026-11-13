#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed regression: source-verified S8000 PCIe port1 root stage3."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(ROOT/'pcie-apple-s8000-port1-id3-id2-id4-stage.c').read_text()
MAKE=(ROOT/'Makefile').read_text()

class N71Port1RootStage3(unittest.TestCase):
    def test_module_gated_to_samsung_owner(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-id3-id2-id4-stage.o',MAKE)
        for t in ('of_machine_is_compatible("apple,n71")',
                  'of_machine_is_compatible("apple,s8000")',
                  '"apple,s8000-pcie-research-blocked"',
                  '"research,hardware-activation-blocked"'):
            self.assertIn(t,S)

    def test_explicit_immutable_arm_and_stage3_flags(self):
        for t in ('static bool armed;', 'static bool stage_id3_id2_id4;',
                  'module_param(armed, bool, 0400)',
                  'module_param(stage_id3_id2_id4, bool, 0400)',
                  'if (!armed || !stage_id3_id2_id4 ||'):
            self.assertIn(t,S)

    def test_exact_apple_root_and_gpio_lookups(self):
        for t in ('N71_ROOT_COMMON_PHYS 0x600000000ULL',
                  'N71_PINCTRL_PHYS 0x20f100000ULL',
                  'pin161 = readl(', 'pin165 = readl(',
                  'id1 = readl(', 'id2 = readl(', 'id3 = readl(',
                  'id4 = readl(', 'id5 = readl('):
            self.assertIn(t,S)

    def test_preflight_all_original_registers_and_pins(self):
        for t in ('pin161 != 0x00072200', 'pin165 != 0x00076a21',
                  'id1 != 0x00000010', 'id2 != 0x01000100',
                  'id3 != 0x00000100', 'id4 != 0', 'id5 != 0'):
            self.assertIn(t,S)
        self.assertLess(S.index('id4 != 0'),S.index('writel(id4 | BIT(0)'))

    def test_only_exact_three_local_register_write_targets(self):
        writes=re.findall(r'^\s*writel\(([^;]+)\);',S,re.M)
        self.assertEqual(len(writes),9)
        self.assertEqual([w.rsplit('+',1)[1].strip() for w in writes],
             ['0x194','0x194','0x180','0x180','0x194',
              '0x1a4','0x1a4','0x180','0x194'])
        self.assertIn('writel(id3 | BIT(0)',S)
        self.assertIn('writel(id2 & ~BIT(8)',S)
        self.assertIn('writel(id4 | BIT(0)',S)

    def test_success_path_reverse_restore_before_pm_down(self):
        a=S.index('writel(id4 | BIT(0)')
        b=S.index('writel(id4,',a)
        c=S.index('writel(id2,',b)
        d=S.index('writel(id3,',c)
        e=S.index('pm_runtime_put_sync_suspend(virt[i - 1])')
        self.assertTrue(a<b<c<d<e)
        for t in ('restored4 != id4','restored2 != id2',
                  'restored != id3','pin161_after != pin161',
                  'pin165_after != pin165'):
            self.assertIn(t,S)

    def test_status_read_is_not_poll_or_dma_enable(self):
        self.assertIn('id5_during = readl(',S)
        self.assertIn('usleep_range(100, 150)',S)
        for forbidden in ('gpiod_get(', 'gpio_request(', 'gpiod_set_value(',
              'reset_control_deassert(', 'pci_host_probe(',
              'pci_scan_root_bus(', 'iommu_attach_device(',
              'dma_map_', 'dev_pm_domain_attach_list('):
            self.assertNotIn(forbidden,S)

    def test_removes_overlay_and_detaches_power(self):
        for t in ('of_overlay_remove(&n71_overlay_id)',
                  'dev_pm_domain_attach_by_name(&pdev->dev, names[i])',
                  'pm_runtime_put_sync_suspend(virt[i - 1])',
                  'dev_pm_domain_detach(virt[i - 1], true)',
                  'iounmap(shared_regs)', 'iounmap(gpio_regs)'):
            self.assertIn(t,S)

if __name__=='__main__':unittest.main()
