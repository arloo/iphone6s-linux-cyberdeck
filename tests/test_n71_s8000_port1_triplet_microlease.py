#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static safety regression for sequential N71 WLAN port1 PMGR triplet lease."""
from pathlib import Path
import re
import subprocess
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(P/'pcie-apple-s8000-port1-triplet-microlease.c').read_text()
D=(P/'n71-s8000-port1-triplet-microlease.dts').read_text()
H=(P/'n71-s8000-port1-triplet-microlease-blob.h').read_text()
MAKE=(P/'Makefile').read_text()

class N71S8000TripletMicrolease(unittest.TestCase):
    def test_inert_module_default_and_immutable_arm_flag(self):
        self.assertIn('static bool armed;',S)
        self.assertIn('module_param(armed, bool, 0400)',S)
        self.assertIn('if (!armed || !n71_validate_nodes()',S)
        self.assertIn('obj-m += pcie-apple-s8000-port1-triplet-microlease.o',MAKE)

    def test_exact_samsung_n71_and_original_hardware_block(self):
        for token in ('of_machine_is_compatible("apple,n71")',
                      'of_machine_is_compatible("apple,s8000")',
                      '"apple,s8000-pcie-research-blocked"',
                      '"research,hardware-activation-blocked"'):
            self.assertIn(token,S)

    def test_four_provider_paths_are_explicit_and_different(self):
        for expected in ('"ref", N71_PMGR "/power-controller@80148", 0x3a',
                         '"aux", N71_PMGR "/power-controller@80318", 0x3b',
                         '"link1", N71_PMGR "/power-controller@80328", 0x3c',
                         '"root", N71_PMGR "/power-controller@80310", 0x2c'):
            self.assertIn(expected,S)
        self.assertIn('provider == expected',S)
        self.assertIn('node->phandle == n71_domains[i].phandle',S)

    def test_platform_core_cannot_auto_power_a_single_domain(self):
        self.assertIn('status = "okay";',D)
        self.assertIn('power-domains = <0x3a>, <0x3b>, <0x3c>, <0x2c>;',D)
        self.assertIn('power-domain-names = "ref", "aux", "link1", "root";',D)
        self.assertIn('of_property_count_u32_elems(node, "power-domains") != 4',S)
        self.assertIn('of_property_count_strings(node, "power-domain-names") != 4',S)
        self.assertIn('research,owner-supervised-triplet-only;',D)

    def test_only_ref_aux_link1_in_correct_order(self):
        self.assertIn('static const char * const names[] = { "ref", "aux", "link1" };',S)
        self.assertIn('dev_pm_domain_attach_by_name(&pdev->dev, names[i])',S)
        self.assertIn('pm_runtime_resume_and_get(virt[i])',S)
        self.assertNotIn('dev_pm_domain_attach_by_name(&pdev->dev, "root")',S)
        self.assertEqual(S.count('pm_runtime_resume_and_get('),1)

    def test_bounded_lease_with_interstage_delay_but_no_perst(self):
        self.assertIn('#define N71_HOLD_MS 25',S)
        self.assertIn('msleep(N71_HOLD_MS)',S)
        self.assertIn('usleep_range(150, 300)',S)
        self.assertIn('PERST is NEVER touched',S)
        self.assertNotIn('apple,explicit-supervised-power-test',D)

    def test_all_partial_failures_roll_back_in_reverse_order(self):
        self.assertIn('goto rollback;',S)
        self.assertIn('for (i = resumed; i > 0; i--)',S)
        self.assertIn('pm_runtime_put_sync_suspend(virt[i - 1])',S)
        self.assertIn('for (i = attached; i > 0; i--)',S)
        self.assertIn('dev_pm_domain_detach(virt[i - 1], true)',S)
        self.assertIn('if (armed && !ret && n71_probe_result)',S)

    def test_no_pcie_link_training_dma_dart_mmio_gpio_or_reset(self):
        impl=S.split('*/',1)[1]
        for forbidden in ('ioremap(', 'readl(', 'writel(', 'memremap(',
                          'gpiod_get(', 'gpiod_set_value(', 'gpio_request(',
                          'reset_control_assert(', 'reset_control_deassert(',
                          'pci_host_probe(', 'pci_scan_root_bus(',
                          'dma_map_', 'iommu_attach_device(',
                          'dev_pm_domain_attach_list('):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,impl)
        for forbidden in ('reg =','interrupts =','gpios =','iommus =','clocks =','resets ='):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,D)

    def test_embedded_synthetic_blob_exact_and_eight_byte_aligned(self):
        self.assertIn('__attribute__((aligned(8)))',H)
        expected=subprocess.check_output(['dtc','-q','-@','-I','dts','-O','dtb',
                                          str(P/'n71-s8000-port1-triplet-microlease.dts')])
        actual=bytes(int(v,16) for v in re.findall(r'0x([0-9a-f]{2})',
                         H.split('= {',1)[1].split('};',1)[0]))
        self.assertEqual(actual,expected)
        self.assertIn(f'n71_triplet_microlease_dtbo_len = {len(expected)};',H)

    def test_overlay_lifetime_is_bounded_by_module_call(self):
        self.assertIn('of_overlay_fdt_apply(',S)
        self.assertIn('of_overlay_remove(&n71_overlay_id)',S)
        self.assertIn('platform_driver_unregister(&n71_triplet_driver)',S)
        self.assertIn('module_exit(n71_microlease_exit)',S)

if __name__=='__main__':unittest.main()
