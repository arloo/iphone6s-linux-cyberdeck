# SPDX-License-Identifier: MIT
"""N71/S8000 NAND PERST160: source-only fail-closed safety contract.

Passing these tests does not establish physical success of the revised
module. The independent recovery helper already restored and re-read
the genuine original register on the real device.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experimental/port0/n71_s3e_perst160_low.c'
class N71S3EPerst160SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=SOURCE.read_text()

    def test_owner_opt_in_default_inert(self):
        self.assertIn('static bool armed;',self.s)
        self.assertIn('if (!armed)',self.s)

    def test_samsung_n71_only(self):
        for k in ('apple,n71','apple,s8000'):
            self.assertIn('of_machine_is_compatible("'+k+'")',self.s)

    def test_real_pin_mapping(self):
        for text in ('N71_P0_GPIO 160U','N71_P1_GPIO 161U',
                     '0x20f100000ULL','20f100000.pinctrl'):
            self.assertIn(text,self.s)

    def test_never_release_perst(self):
        self.assertIn('gpiod_direction_output(pin,0)',self.s)
        self.assertNotRegex(self.s,r'gpiod_direction_output\s*\(\s*pin\s*,\s*1\s*\)')
        self.assertNotIn('gpiod_set_value(',self.s)
        self.assertNotIn('gpiod_set_value_cansleep(',self.s)

    def test_uses_real_native_gpio_regmap(self):
        self.assertIn('of_find_device_by_node(ap_node)',self.s)
        self.assertIn('dev_get_regmap(&ap_device->dev,NULL)',self.s)
        self.assertNotIn('syscon_node_to_regmap(ap_node)',self.s)

    def test_preserves_original_pin_mode_and_cache(self):
        self.assertIn('N71_GPIO0_STOCK 0x00072200U',self.s)
        self.assertIn('regmap_update_bits(pin_map,N71_P0_REG',self.s)
        self.assertIn('N71_GPIO_MUTABLE_MASK',self.s)
        self.assertIn('reset_register!=baseline || cached!=baseline',self.s)

    def test_gpio161_wifi_is_never_driven(self):
        self.assertIn('N71_GPIO1_WIFI 0x00072203U',self.s)
        self.assertNotIn('gpiod_direction_output(wifi',self.s)
        self.assertNotIn('writel(',self.s)

    def test_power_and_link0_remain_off(self):
        self.assertIn('N71_P0_PMGR 0x80320U',self.s)
        self.assertIn('ret=power_off()',self.s)
        self.assertIn('if (!ret && power_off())',self.s)

    def test_bounded_dwell(self):
        self.assertIn('N71_RESET_DWELL_MS 50',self.s)
        self.assertIn('msleep(N71_RESET_DWELL_MS)',self.s)

    def test_no_storage_or_dma_operations(self):
        for dangerous in ('dma_map(', 'pci_write_config', 'nvme_submit',
                          'blkdev_get', 'pm_runtime_resume_and_get(',
                          'regmap_write(', 'pm_runtime_get_sync('):
            with self.subTest(operation=dangerous):
                self.assertNotIn(dangerous,self.s)

    def test_fail_closed_quarantine(self):
        self.assertIn('if (quarantine)',self.s)
        self.assertIn('__module_get(THIS_MODULE)',self.s)
        self.assertIn('GPIO160_RESTORE_FAILED',self.s)

if __name__=='__main__':
    unittest.main()
