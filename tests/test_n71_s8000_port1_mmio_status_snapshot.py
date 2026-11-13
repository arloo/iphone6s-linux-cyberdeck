#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71/S8000 source regressions for one read-only root register sample."""
from pathlib import Path
import re
import subprocess
import unittest

BASE = Path(__file__).resolve().parents[1] / 'experimental/port1'
SOURCE = (BASE/'pcie-apple-s8000-port1-status-snapshot.c').read_text()
DTS = (BASE/'n71-s8000-port1-status-snapshot.dts').read_text()
HEADER = (BASE/'n71-s8000-port1-status-snapshot-blob.h').read_text()
MAKE = (BASE/'Makefile').read_text()

class N71StatusSnapshot(unittest.TestCase):
    def test_matching_arm64_out_of_tree_module(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-status-snapshot.o', MAKE)
        self.assertIn('module_init(n71_microlease_init)', SOURCE)
        self.assertIn('module_exit(n71_microlease_exit)', SOURCE)

    def test_read_only_double_gated_with_one_of_two_exclusive_targets(self):
        for expected in ('static bool armed;', 'static bool sample_shared_status;',
                         'static bool sample_port1_status;',
                         'module_param(armed, bool, 0400)',
                         'module_param(sample_shared_status, bool, 0400)',
                         'module_param(sample_port1_status, bool, 0400)',
                         'sample_shared_status == sample_port1_status'):
            self.assertIn(expected, SOURCE)
        self.assertEqual(SOURCE.count('readl('), 1)
        self.assertNotIn('writel(', SOURCE)
        self.assertNotIn('readl_relaxed(', SOURCE)

    def test_original_apple_s8000_root_resource9_status_offsets(self):
        for constant in ('#define N71_ROOT_COMMON_PHYS 0x600000000ULL',
                         '#define N71_ROOT_SHARED_REGISTER 0x2cU',
                         '#define N71_ROOT_PORT1_REGISTER 0x1acU',
                         '#define N71_ROOT_IOREMAP_BYTES 0x1000U'):
            self.assertIn(constant, SOURCE)
        self.assertIn('shared_regs = ioremap(N71_ROOT_COMMON_PHYS, N71_ROOT_IOREMAP_BYTES)', SOURCE)
        self.assertIn('status_snapshot = readl((u8 __iomem *)shared_regs +', SOURCE)
        self.assertIn('iounmap(shared_regs)', SOURCE)
        self.assertIn('sample_shared_status ? N71_ROOT_SHARED_REGISTER :', SOURCE)

    def test_status_is_opaque_not_pcie_link_up(self):
        self.assertIn('root_shared_id1_at_0x60000002c', SOURCE)
        self.assertIn('root_port1_id5_at_0x6000001ac', SOURCE)
        self.assertIn('status_snapshot & BIT(4)', SOURCE)
        self.assertIn('status_snapshot & BIT(0)', SOURCE)
        self.assertIn('opaque status, not link', SOURCE)

    def test_original_pcie_guard_and_samsung_machine(self):
        for expected in ('of_machine_is_compatible("apple,n71")',
                         'of_machine_is_compatible("apple,s8000")',
                         '"apple,s8000-pcie-research-blocked"',
                         '"research,hardware-activation-blocked"'):
            self.assertIn(expected, SOURCE)

    def test_all_pmgr_attachments_before_mmio_read(self):
        self.assertIn('static const char * const names[] = { "ref", "aux", "link1" };', SOURCE)
        self.assertIn('dev_pm_domain_attach_by_name(&pdev->dev, names[i])', SOURCE)
        self.assertIn('pm_runtime_resume_and_get(virt[i])', SOURCE)
        self.assertLess(SOURCE.index('pm_runtime_resume_and_get(virt[i])'),
                        SOURCE.index('status_snapshot = readl('))
        self.assertLess(SOURCE.index('status_snapshot = readl('),
                        SOURCE.index('pm_runtime_put_sync_suspend(virt[i - 1])'))

    def test_bounded_sleep_reverse_rollback_and_cleanup(self):
        for expected in ('#define N71_HOLD_MS 25', 'msleep(N71_HOLD_MS)',
                         'for (i = resumed; i > 0; i--)',
                         'pm_runtime_put_sync_suspend(virt[i - 1])',
                         'for (i = attached; i > 0; i--)',
                         'dev_pm_domain_detach(virt[i - 1], true)',
                         'of_overlay_fdt_apply(', 'of_overlay_remove(&n71_overlay_id)',
                         'platform_driver_unregister(&n71_triplet_driver)'):
            self.assertIn(expected, SOURCE)

    def test_no_pcie_host_gpio_perst_reset_dma_or_other_resources(self):
        code = SOURCE.split('*/',1)[1]
        for forbidden in ('gpio_request(', 'gpiod_set_value(', 'gpiod_get(',
                          'reset_control_deassert(', 'reset_control_assert(',
                          'pci_host_probe(', 'pci_scan_root_bus(', 'dma_map_',
                          'iommu_attach_device(', 'dev_pm_domain_attach_list('):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        for forbidden in ('reg =', 'gpios =', 'iommus =', 'interrupts =',
                          'resets =', 'clocks =', 'apple,explicit-supervised-power-test'):
            self.assertNotIn(forbidden, DTS)

    def test_disabled_dma_controller_stays_blocked_while_observer_is_created(self):
        self.assertIn('status = "okay";', DTS)
        self.assertIn('research,owner-supervised-status-snapshot;', DTS)
        self.assertIn('power-domains = <0x3a>, <0x3b>, <0x3c>, <0x2c>;', DTS)
        self.assertIn('power-domain-names = "ref", "aux", "link1", "root";', DTS)
        self.assertIn('of_property_count_u32_elems(node, "power-domains") != 4', SOURCE)
        self.assertIn('provider == expected', SOURCE)

    def test_exact_synthetic_fdt_binary_embedded_eight_byte_aligned(self):
        self.assertIn('__attribute__((aligned(8)))', HEADER)
        actual=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',
                       HEADER.split('= {',1)[1].split('};',1)[0]))
        expected=subprocess.check_output(['dtc','-q','-@','-I','dts','-O','dtb',
                                          str(BASE/'n71-s8000-port1-status-snapshot.dts')])
        self.assertEqual(actual, expected)
        self.assertIn(f'n71_status_snapshot_dtbo_len = {len(expected)};', HEADER)

if __name__ == '__main__': unittest.main()
