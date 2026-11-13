#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed original S8000 Antigua GPIO10 WLAN REG_ON power policy."""
from pathlib import Path
import re
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(P/'n71-s8000-wlan-pmu-regon-microlease.c').read_text()
MAKE=(P/'Makefile').read_text()

class S8000WlanPMUGpio10(unittest.TestCase):
    def test_arm64_module_target_and_n71_exclusivity(self):
        self.assertIn('obj-m += n71-s8000-wlan-pmu-regon-microlease.o',MAKE)
        self.assertIn('of_machine_is_compatible("apple,n71")',S)
        self.assertIn('of_machine_is_compatible("apple,s8000")',S)
        self.assertIn('"apple,antigua-pmic-gpio"',S)
        self.assertIn('"apple,antigua-pmic"',S)

    def test_unarmed_default_and_read_only_param(self):
        self.assertIn('static bool armed;',S)
        self.assertIn('module_param(armed, bool, 0400)',S)
        self.assertIn('if (!armed) {',S)
        self.assertIn('unarmed read-only PASS',S)

    def test_exact_original_pmu_regon_gpio10_address(self):
        self.assertIn('regmap_read(map,0x914,&original)',S)
        self.assertIn('regmap_read(map,0x187,&st_before)',S)
        self.assertIn('regmap_read(map,0x910,&bt_before)',S)
        self.assertIn('original!=0x80 || bt_before!=0x80',S)

    def test_writes_only_one_pmu_bit_with_low_rollback(self):
        writes=re.findall(r'regmap_update_bits\(map,([^;]+)\);',S)
        self.assertEqual(writes,['0x914,BIT(0),BIT(0)','0x914,BIT(0),0'])
        self.assertIn('on!=0x81 || off!=0x80',S)
        self.assertIn('msleep(25)',S)

    def test_repeated_probe_cannot_repeat_electrical_pulse(self):
        self.assertIn('if (visited)',S)
        self.assertLess(S.index('if (visited)'),S.index('regmap_update_bits(map,0x914'))
        self.assertIn('visited=true;',S)

    def test_no_gpiochip_bt_or_rtc_side_effects(self):
        for forbidden in ('devm_gpiochip_add_data(', 'gpiochip_add_data(',
              'regmap_write(', 'writel(', 'gpiod_set_value(',
              'gpio_direction_output(', 'i2c_smbus_write_',
              '0x910,BIT(', 'regmap_update_bits(map,0x910',
              'dev_pm_domain_attach(', 'dma_map_', 'pci_host_probe('):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,S)
        self.assertIn('bt_after!=bt_before',S)

    def test_pad_not_false_claimed_as_physical_voltage(self):
        self.assertIn('pad voltage not independently proven',S)
        self.assertIn('st_on&BIT(2)',S)
        self.assertNotIn('!(st_on&BIT(2)) ||',S)

    def test_cleanup_and_readback_before_success(self):
        for token in ('platform_driver_unregister(&n71_wlan_pm_driver)',
                      'regmap_read(map,0x914,&off)',
                      'regmap_read(map,0x910,&bt_after)',
                      'rollback=regmap_update_bits(map,0x914,BIT(0),0)',
                      'return -ENODEV;', 'module_exit(n71_wlan_pm_exit)'):
            self.assertIn(token,S)

if __name__=='__main__':unittest.main()
