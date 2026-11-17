# SPDX-License-Identifier: MIT
"""Static fail-closed contract for the N71 S8000 integrated PCIe port0 pilot.

The hardware log is documented separately. Tests validate only the source
structure: original iOS/NAND isolation is not proven by a unit test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "experimental/port0/n71_s3e_p0_asserted_reset_rootstart.c"

class N71S3ECombinedPort0Safety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = SRC.read_text()

    def test_board_guard_restricts_n71_s8000(self):
        self.assertIn('of_machine_is_compatible("apple,n71")', self.s)
        self.assertIn('of_machine_is_compatible("apple,s8000")', self.s)

    def test_default_inert(self):
        self.assertIn('static bool armed;',self.s)
        self.assertIn('static bool assert_storage_reset;',self.s)
        self.assertIn('if (!armed)',self.s)

    def test_power_domain_exact_provider(self):
        self.assertIn('"/power-controller@80320"',self.s)
        self.assertIn('strcmp(label,"pcie_link0")',self.s)
        self.assertIn('of_genpd_add_device',self.s)
        self.assertIn('pm_runtime_resume_and_get(',self.s)
        self.assertIn('pm_runtime_put_sync_suspend(',self.s)

    def test_only_storage_gpio160_is_asserted(self):
        self.assertIn('GPIO_LOOKUP(S8000_GPIO_CHIP, 160, "s3e-reset", GPIO_ACTIVE_HIGH)',self.s)
        self.assertIn('gpiod_direction_output(n71_reset_pin,0)',self.s)
        self.assertNotIn('gpiod_direction_output(n71_reset_pin,1)',self.s)
        self.assertNotIn('gpiod_set_value(',self.s)

    def test_wifi_gpio161_unchanged(self):
        self.assertIn('S8000_GPIO161_WIFI 0x00072203U',self.s)
        self.assertIn('wifi!=S8000_GPIO161_WIFI',self.s)

    def test_reset_is_held_during_power(self):
        assert_pos=self.s.index('ret=gpiod_direction_output(n71_reset_pin,0)')
        power_pos=self.s.index('ret=pm_runtime_resume_and_get(&n71_consumer->dev)')
        return_pos=self.s.index('pin_ret=gpiod_direction_input(n71_reset_pin)')
        self.assertLess(assert_pos,power_pos)
        self.assertLess(power_pos,return_pos)

    def test_gpio_exact_apple_restore(self):
        for part in ('S8000_GPIO160_ORIGINAL 0x00072200U',
                     'S8000_GPIO160_ASSERTED_LOW 0x00072202U',
                     'regmap_update_bits(n71_pinctrl_regmap,',
                     'S8000_GPIO_MUTABLE_MASK',
                     'after!=S8000_GPIO160_ORIGINAL',
                     'cached!=S8000_GPIO160_ORIGINAL'):
            self.assertIn(part,self.s)

    def test_nand_reset_only_released_after_power_off(self):
        self.assertIn('ACTUAL(pmgr)!=0 || TARGET(pmgr)!=0',self.s)
        self.assertIn('GPIO160_RESET_RETAINED_LOW_AS_P0_NOT_OFF',self.s)

    def test_runtime_only_bounded_dwell(self):
        self.assertIn('#define DWELL_MS 25U',self.s)
        self.assertIn('msleep(DWELL_MS)',self.s)

    def test_reads_storage_iommu_without_configuring_it(self):
        for reg in ('DART0_PHYS 0x601008000ULL',
                    'NVMMU0_PHYS 0x601004000ULL',
                    'P0_PORT_PHYS 0x601000000ULL',
                    'REAL_DART0_READ_ONLY',
                    'REAL_NVMMU0_READ_ONLY'):
            self.assertIn(reg,self.s)
        for dangerous in ('dma_map(', 'pci_write_config', 'nvme_submit',
                          'blkdev_get(', 'of_dma_configure_id('):
            self.assertNotIn(dangerous,self.s)

    def test_rollback_of_s8000_root(self):
        for statement in ('ROOT_PORT0_ID2_ID3_RESTORED_TO_ORIGINAL_BASELINE',
                          'ORIGINAL_NVME_MODE_ROOT24_RESTORED_TO_ZERO',
                          'ROOT_NVME_MODE_RESTORE_REFUSED_WHILE_POWER_ACTIVE'):
            self.assertIn(statement,self.s)

    def test_quarantine_protects_failed_release(self):
        self.assertIn('__module_get(THIS_MODULE)',self.s)
        self.assertIn('QUARANTINE_GPIO160_PIN_HOLD_AND_MODULE_REF',self.s)
        self.assertIn('if (!n71_unreleased)',self.s)

if __name__ == '__main__':
    unittest.main()
