#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source and exact DTB integrity tests for 25 ms N71/S8000 root-only microlease."""
from pathlib import Path
import re
import subprocess
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
SOURCE=(P/'pcie-apple-s8000-port1-root-microlease.c').read_text()
HEADER=(P/'n71-s8000-port1-root-microlease-blob.h').read_text()
DTS=(P/'n71-s8000-port1-root-microlease.dts').read_text()
MAKE=(P/'Makefile').read_text()

class N71S8000RootMicrolease(unittest.TestCase):
    def test_real_out_of_tree_arm64_kernel_module(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-root-microlease.o',MAKE)
        self.assertIn('module_init(n71_microlease_init)',SOURCE)
        self.assertIn('module_exit(n71_microlease_exit)',SOURCE)

    def test_arm_flag_inert_by_default_and_read_only(self):
        self.assertIn('static bool armed;',SOURCE)
        self.assertIn('module_param(armed, bool, 0400)',SOURCE)
        self.assertIn('if (!armed || !n71_validate_nodes()',SOURCE)

    def test_n71_s8000_only_with_original_pcie_block(self):
        for token in ('of_machine_is_compatible("apple,n71")',
                      'of_machine_is_compatible("apple,s8000")',
                      '"apple,s8000-pcie-research-blocked"',
                      '"research,hardware-activation-blocked"'):
            self.assertIn(token,SOURCE)

    def test_only_root_runtime_power_path(self):
        self.assertIn('dev_pm_domain_attach_by_name(&pdev->dev, "root")',SOURCE)
        self.assertIn('pm_runtime_resume_and_get(virt)',SOURCE)
        self.assertIn('pm_runtime_put_sync_suspend(virt)',SOURCE)
        self.assertIn('dev_pm_domain_detach(virt, true)',SOURCE)
        self.assertIn('msleep(N71_HOLD_MS)',SOURCE)
        self.assertIn('#define N71_HOLD_MS 25',SOURCE)
        self.assertEqual(SOURCE.count('dev_pm_domain_attach_by_name('),1)
        self.assertEqual(SOURCE.count('pm_runtime_resume_and_get('),1)
        self.assertNotIn('dev_pm_domain_attach_list(',SOURCE)

    def test_no_link_dart_pci_mmio_gpio_or_reset(self):
        implementation=SOURCE.split('*/',1)[1]
        for token in ('ioremap(', 'readl(', 'writel(', 'memremap(',
                      'gpio_request(', 'gpiod_get(', 'gpiod_set_value(',
                      'reset_control_assert(', 'reset_control_deassert(',
                      'pci_host_probe(', 'pci_scan_root_bus(', 'iommu_attach_device(',
                      'dma_map_', 'dev_pm_domain_attach_list('):
            with self.subTest(token=token):
                self.assertNotIn(token,implementation)

    def test_all_provider_phandles_required_before_overlay(self):
        for text in ('"ref", N71_PMGR "/power-controller@80148", 0x3a',
                     '"aux", N71_PMGR "/power-controller@80318", 0x3b',
                     '"link1", N71_PMGR "/power-controller@80328", 0x3c',
                     'node->phandle == n71_domains[i].phandle',
                     'of_parse_phandle(node, "power-domains", i)',
                     'provider == expected'):
            self.assertIn(text,SOURCE)

    def test_four_references_prevent_automatic_platform_single_domain_attach(self):
        self.assertIn('status = "okay";',DTS)
        self.assertIn('power-domains = <0x3a>, <0x3b>, <0x3c>, <0x2c>;',DTS)
        self.assertIn('power-domain-names = "ref", "aux", "link1", "root";',DTS)
        self.assertIn('research,owner-supervised-root-only;',DTS)
        for dangerous in ('reg =','clocks =','resets =','gpios =','iommus =',
                          'interrupts =','apple,explicit-supervised-power-test'):
            self.assertNotIn(dangerous,DTS)

    def test_synthetic_blob_bitwise_exact_and_aligned(self):
        self.assertIn('__attribute__((aligned(8)))',HEADER)
        compiled=subprocess.check_output(['dtc','-q','-@','-I','dts','-O','dtb',
                            str(P/'n71-s8000-port1-root-microlease.dts')])
        packed=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',
                    HEADER.split('= {',1)[1].split('};',1)[0]))
        self.assertEqual(compiled,packed)
        self.assertIn(f'n71_root_microlease_dtbo_len = {len(compiled)};',HEADER)

    def test_overlay_rollback_before_module_unload(self):
        self.assertIn('of_overlay_fdt_apply(',SOURCE)
        self.assertIn('of_overlay_remove(&n71_overlay_id)',SOURCE)
        self.assertIn('platform_driver_unregister(&n71_root_driver)',SOURCE)
        self.assertIn('if (armed && !ret && n71_probe_result)',SOURCE)

if __name__=='__main__':unittest.main()
