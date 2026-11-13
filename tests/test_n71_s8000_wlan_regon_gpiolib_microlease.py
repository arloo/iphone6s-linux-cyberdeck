#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded native PMIC GPIO10 WLAN REG_ON GPIOLIB integration safety."""
from pathlib import Path
import re
import subprocess
import unittest

P = Path(__file__).resolve().parents[1] / "experimental" / "port1"
SRC = (P / "pcie-apple-s8000-wlan-regon-gpiolib-microlease.c").read_text()
DTS = (P / "n71-s8000-wlan-regon-gpiolib-microlease.dts").read_text()
HDR = (P / "n71-native-wlan-reg-on-25ms-blob-20261113.h").read_text()
MAKE = (P / "Makefile").read_text()

class N71S8000WlanRegOnGpiolib(unittest.TestCase):
    def test_out_of_tree_gpl_module(self):
        self.assertIn("obj-m += pcie-apple-s8000-wlan-regon-gpiolib-microlease.o", MAKE)
        self.assertIn("MODULE_LICENSE(\"GPL\")", SRC)
        self.assertIn("module_exit(n71_native_exit)", SRC)

    def test_only_real_samsung_n71_with_original_pcie_block(self):
        for value in ('of_machine_is_compatible("apple,n71")',
                      'of_machine_is_compatible("apple,s8000")',
                      '"apple,s8000-pcie-research-blocked"',
                      '"research,hardware-activation-blocked"'):
            self.assertIn(value, SRC)

    def test_gpio10_exact_provider_identity(self):
        self.assertIn('N71_GPIO10_PROVIDER "/soc/i2c@20a110000/pmic@74/gpio@900"', SRC)
        self.assertIn('provider->phandle==0x09', SRC)
        self.assertIn('parsed.np==expected', SRC)
        self.assertIn('parsed.args_count==2', SRC)
        self.assertIn('parsed.args[0]==10', SRC)
        self.assertIn('parsed.args[1]==0', SRC)
        self.assertIn('wlan-reg-on-gpios = <0x09 10 0>;', DTS)
        self.assertNotIn('wlan-reg-on-gpios = <0x09 8 ', DTS)

    def test_single_probed_guard(self):
        self.assertIn('if (probed)', SRC)
        self.assertIn('probed=true;', SRC)
        self.assertLess(SRC.index('if (probed)'), SRC.index('gpiod_get(&pdev->dev'))

    def test_armed_only_with_unarmed_default(self):
        self.assertIn('static bool armed;', SRC)
        self.assertIn('module_param(armed, bool, 0400)', SRC)
        self.assertIn('if (!armed) {', SRC)
        self.assertIn('GPIO10 not requested, PMU unchanged', SRC)

    def test_standard_gpiolib_exclusive_line_and_immediate_rollback(self):
        self.assertIn('gpiod_get(&pdev->dev,"wlan-reg-on",GPIOD_OUT_LOW)', SRC)
        self.assertEqual(SRC.count('gpiod_set_value_cansleep(reg_on,1)'), 1)
        self.assertEqual(SRC.count('gpiod_set_value_cansleep(reg_on,0)'), 1)
        self.assertIn('gpiod_get_value_cansleep(reg_on)', SRC)
        self.assertIn('gpiod_put(reg_on)', SRC)
        self.assertTrue(SRC.index('gpiod_set_value_cansleep(reg_on,1)') <
                        SRC.index('gpiod_set_value_cansleep(reg_on,0)') <
                        SRC.index('gpiod_put(reg_on)'))
        self.assertIn('msleep(25)', SRC)

    def test_perst_clkreq_exact_guard_but_no_pin_write(self):
        self.assertIn('perst!=0x00072200 || clkreq!=0x00076a21', SRC)
        self.assertIn('perst_after==perst && clkreq_after==clkreq', SRC)
        self.assertNotIn('writel(', SRC)
        self.assertNotIn('gpiod_direction_output(', SRC)
        self.assertNotIn('gpio_request(', SRC)

    def test_no_direct_pmic_writes_or_pcie_dart_dma_actions(self):
        for dangerous in ('regmap_update_bits(', 'regmap_write(', 'pci_host_probe(',
                          'pci_scan_root_bus(', 'iommu_attach_device(',
                          'dma_map_', 'dev_pm_domain_attach_list(',
                          'reset_control_deassert('):
            with self.subTest(dangerous=dangerous):
                self.assertNotIn(dangerous, SRC)
        for key in ('power-domains =', 'reg =', 'clocks =', 'resets =',
                    'interrupts =', 'iommus ='):
            self.assertNotIn(key, DTS)

    def test_overlay_is_reversible(self):
        self.assertIn('of_overlay_fdt_apply(', SRC)
        self.assertIn('platform_driver_unregister(&n71_native_driver)', SRC)
        self.assertIn('of_overlay_remove(&overlay_id)', SRC)
        self.assertIn('return -ENODEV; /* no lasting binding */', SRC)

    def test_exact_generated_blob_and_required_alignment(self):
        self.assertIn('__attribute__((aligned(8)))', HDR)
        binary = subprocess.check_output(['dtc', '-q', '-@', '-I', 'dts', '-O', 'dtb',
                   str(P / 'n71-s8000-wlan-regon-gpiolib-microlease.dts')])
        embedded=bytes(int(v,16) for v in re.findall(r'0x([0-9a-f]{2})',
                                HDR.split('= {', 1)[1].split('};', 1)[0]))
        self.assertEqual(binary, embedded)
        self.assertIn(f'n71_native_wlan_gpio10_dtbo_len = {len(binary)};', HDR)

if __name__ == '__main__':
    unittest.main()
