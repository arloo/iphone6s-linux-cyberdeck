# SPDX-License-Identifier: MIT
"""N71 S8000 active WLAN port +0x210 read-only hardware probe source safety."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/
        "experimental/port0/n71_s8000_port1_0210_ro.c")

class Port0210ReadOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.src=SOURCE.read_text()
    def test_unarmed_default(self):
        self.assertIn("static bool armed;",self.src)
        self.assertIn("if (!armed)",self.src)
    def test_n71_s8000_guard(self):
        self.assertIn('of_machine_is_compatible("apple,n71")',self.src)
        self.assertIn('of_machine_is_compatible("apple,s8000")',self.src)
    def test_exact_real_wlan_port(self):
        self.assertIn("0x602000000ULL",self.src)
        self.assertIn("0x14e4,0x43a3",self.src)
    def test_exact_original_offset_single_read(self):
        self.assertEqual(self.src.count("readl((u8 __iomem *)port+0x210)"),1)
    def test_storage_port_power_off_guard(self):
        self.assertIn("ACTUAL(p0)!=0",self.src)
        self.assertIn("TARGET(p0)!=0",self.src)
    def test_wifi_power_guard(self):
        self.assertIn("ACTUAL(p1)!=15",self.src)
        self.assertIn("r1id5!=1",self.src)
    def test_no_hw_writes(self):
        for forbidden in ("writel(", "writeq(", "regmap_write(",
                          "regmap_update_bits(", "gpiod_direction_output(",
                          "dma_map(", "pm_runtime_get(", "pci_write_config",
                          "nvme_submit"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,self.src)
    def test_no_nvme_controller_access(self):
        self.assertNotIn("0x601004000",self.src)
        self.assertNotIn("0x601008000",self.src)

if __name__=="__main__":unittest.main()
