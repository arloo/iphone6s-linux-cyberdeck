# SPDX-License-Identifier: MIT
"""Static safety contract for the N71 S8000 on-phone PHY/local MMIO probes."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]/"experimental/port0"
PHY=(ROOT/"n71_s3e_phy_stock_ro.c").read_text()
LOCAL=(ROOT/"n71_s3e_p0_local_window_compare.c").read_text()

class S8000ReadOnlyComparisonContracts(unittest.TestCase):
    def test_phy_strict_board_gate(self):
        for x in ("apple,n71","apple,s8000","apple,s8000-pcie-research-blocked"):
            self.assertIn(x,PHY)
    def test_phy_default_inert(self):
        self.assertIn("static bool armed;",PHY)
        self.assertIn("if (!armed)",PHY)
    def test_phy_original_resource_and_wlan_control(self):
        for text in ("0x600008000ULL","0x600000000ULL","0x602008000ULL",
                     "pci_get_device(0x14e4, 0x43a3",
                     "ACTUAL(p0) != 0","ACTUAL(p1) != 15"):
            self.assertIn(text,PHY)
    def test_phy_41_unique_original_read_offsets(self):
        m=re.search(r'n71_stock_phy_offsets\[\]\s*=\s*\{([^}]+)\}',PHY,re.S)
        self.assertIsNotNone(m)
        arr=[int(x,16) for x in re.findall(r'0x([0-9a-f]+)U',m.group(1))]
        self.assertEqual(len(arr),41)
        self.assertEqual(len(set(arr)),41)
        self.assertTrue(all(x%4==0 and x+4<=0x4000 for x in arr))
    def test_phy_no_hardware_or_dma_writes(self):
        for call in ("writel(", "writeq(", "regmap_write(",
                     "regmap_update_bits(", "dma_map(", "pci_write_config",
                     "gpiod_direction_output(", "pm_runtime_resume_and_get("):
            self.assertNotIn(call,PHY)
    def test_phy_stable_root_before_after(self):
        self.assertIn("root_p0 != original_root_p0",PHY)
        self.assertIn("root_p1 != original_root_p1",PHY)
    def test_local_source_uses_stock_port0_and_port1_ranges(self):
        for phys in ("0x601000000ULL","0x601004000ULL",
                     "0x602000000ULL","0x602004000ULL"):
            self.assertIn(phys,LOCAL)
    def test_local_comparison_only_with_storage_reset_held(self):
        self.assertIn("if (sample_local_banks && (!assert_storage_reset",LOCAL)
        self.assertIn("gpiod_direction_output(n71_reset_pin,0)",LOCAL)
        self.assertNotIn("gpiod_direction_output(n71_reset_pin,1)",LOCAL)
        self.assertIn("LOCAL_BANK_COMPARE_TOTAL",LOCAL)
    def test_local_readonly_probe_has_no_new_writes(self):
        start=LOCAL.rindex("        if (sample_local_banks) {")
        end=LOCAL.index("        if (root_mmio)",start)
        block=LOCAL[start:end]
        for call in ("writel(", "writeq(", "regmap_write(",
                     "gpiod_direction_output(", "dma_map(",
                     "pci_write_config", "pm_runtime_resume_and_get("):
            self.assertNotIn(call,block)
    def test_local_full_rollback_preserved(self):
        for x in ("ROOT_PORT0_ID2_ID3_RESTORED_TO_ORIGINAL_BASELINE",
                  "ORIGINAL_NVME_MODE_ROOT24_RESTORED_TO_ZERO",
                  "GPIO160_ORIGINAL_INPUT_RESTORED_VERIFIED",
                  "GPIO160_RESET_RETAINED_LOW_AS_P0_NOT_OFF"):
            self.assertIn(x,LOCAL)
    def test_local_bounded_25ms(self):
        self.assertIn("#define DWELL_MS 25U",LOCAL)
        self.assertIn("msleep(DWELL_MS)",LOCAL)
    def test_per_port_bank_8_exact_offsets(self):
        m=re.search(r'const u32 off\[\]\s*=\s*\{([^}]+)\}',LOCAL,re.S)
        self.assertIsNotNone(m)
        values=[int(x,16) for x in re.findall(r'0x([0-9a-f]+)U',m.group(1))]
        self.assertEqual(set(values),{0x90,0x98,0x130,0x134,0x138,0x13c,0x140,0x154})

if __name__=="__main__":
    unittest.main()
