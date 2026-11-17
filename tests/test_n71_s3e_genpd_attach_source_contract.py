# SPDX-License-Identifier: MIT
"""Source contract for owner-supervised Apple N71 S8000 storage genpd wiring.

These are static and do NOT validate silicon power, S3E DMA isolation,
read-only NVMe commands, or reliability on the phone. Physical testing is
separately gated by charging and a recoverable original iOS backup.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experimental/port0/n71_s3e_genpd_attach.c"
DTS = ROOT / "experimental/port0/n71-s8000-storage-controllers-disabled.dtsi"

class N71StorageGenpdContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        cls.dts = DTS.read_text()

    def test_exact_n71_and_s8000_gate(self):
        self.assertIn('of_machine_is_compatible("apple,n71")',self.source)
        self.assertIn('of_machine_is_compatible("apple,s8000")',self.source)

    def test_inert_by_default(self):
        self.assertRegex(self.source,r'static bool armed\s*;')
        self.assertRegex(self.source,r'static bool attach_domains\s*;')
        self.assertIn('if (!armed)',self.source)

    def test_two_native_resources_with_verified_addresses(self):
        self.assertIn('0x601008000ULL',self.source)
        self.assertIn('0x601004000ULL',self.source)
        self.assertIn('0x601000000ULL',self.source)
        self.assertIn('0x4000U',self.source)

    def test_existing_power_domain_reference(self):
        self.assertIn('"/power-controller@80320"',self.source)
        self.assertIn('"pcie_link0"',self.source)
        self.assertIn('of_genpd_add_device',self.source)
        self.assertIn('node->phandle',self.source)
        self.assertIn('spec.np = node;',self.source)

    def test_attach_both_and_remove_both(self):
        self.assertIn('of_genpd_add_device(&spec, &n71_dart0_dev->dev)',self.source)
        self.assertIn('of_genpd_add_device(&spec, &n71_nvmmu0_dev->dev)',self.source)
        self.assertIn('pm_genpd_remove_device(&n71_dart0_dev->dev)',self.source)
        self.assertIn('pm_genpd_remove_device(&n71_nvmmu0_dev->dev)',self.source)

    def test_power_must_remain_off(self):
        self.assertIn('n71_port0_power_off()',self.source)
        self.assertIn('if (state & 0xff)',self.source)

    def test_no_silicon_or_dma_activation(self):
        for call in ('writel(', 'writeq(', 'ioremap(', 'regmap_write(',
                     'regmap_update_bits(', 'pm_runtime_enable(',
                     'pm_runtime_resume_and_get(', 'pm_runtime_get_sync(',
                     'pci_write_config', 'dma_map(', 'gpiod_set_value('):
            with self.subTest(function=call):
                self.assertNotIn(call,self.source)

    def test_no_risky_auto_binding_in_dts(self):
        self.assertEqual(self.dts.count('status = "disabled"'),2)
        self.assertNotIn('status = "okay"',self.dts)
        self.assertIsNone(re.search(r'^\\s*dma-ranges\\s*=',self.dts,re.M))
        self.assertIsNone(re.search(r'^\\s*iommu-map\\s*=',self.dts,re.M))

if __name__ == '__main__':
    unittest.main()
