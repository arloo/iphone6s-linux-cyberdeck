"""Static test gates for the deliberately inert A9 PCIe research guard RFC11.

Tests check the staged public diff; they do NOT prove live PCIe correctness.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"patches/0011-s8000-pcie-port1-research-guard-rfc.patch"

class TestS8000ResearchGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch=PATCH.read_text()
        cut=cls.patch.index("diff --git a/drivers/pci/controller/pcie-apple-s8000-guard.c")
        cls.driver="\n".join(x[1:] for x in cls.patch[cut:].splitlines()
                             if x.startswith("+") and not x.startswith("+++"))
        cls.added="\n".join(x[1:] for x in cls.patch.splitlines()
                            if x.startswith("+") and not x.startswith("+++"))

    def test_guaranteed_default_off(self):
        self.assertIn("config PCIE_APPLE_S8000_RESEARCH_GUARD",self.added)
        self.assertRegex(self.added,r"(?m)^\s*default n\s*$")
        self.assertIn("$(CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD)",self.added)
        self.assertIn("depends on ARCH_APPLE && OF",self.added)

    def test_probing_is_intentionally_refused(self):
        self.assertIn('apple,s8000-pcie-research-blocked',self.driver)
        self.assertIn('if (!of_machine_is_compatible("apple,n71")',self.driver)
        self.assertIn('!of_machine_is_compatible("apple,s8000")',self.driver)
        self.assertIn("return -ENODEV;",self.driver)
        self.assertIn("return -ERANGE;",self.driver)
        self.assertIn("return -EOPNOTSUPP;",self.driver)
        self.assertNotIn(' .compatible = "apple,pcie"',self.driver)
        self.assertNotIn('.compatible = "apcie,s8000"',self.driver)

    def test_explicit_port1_window_metadata(self):
        for value in ("0x602000000ULL","0x602004000ULL",
                      "0x602008000ULL"):
            self.assertIn(value,self.driver)

    def test_protect_storage_modem_and_all_shared_resources(self):
        for value in ("0x601000000ULL", "0x603000000ULL",
                      "0x604000000ULL", "0x600000000ULL",
                      "0x600008000ULL", "0x610000000ULL"):
            self.assertIn(value,self.driver)
        self.assertIn("apple_s8000_regions_overlap",self.driver)
        self.assertIn("apple_s8000_port1_metadata_isolated",self.driver)

    def test_no_hardware_side_effects_or_dynamic_dma(self):
        for forbidden in (
           "devm_ioremap", "ioremap(", "readl(", "writel(",
           "ioread", "iowrite", "regmap_read", "regmap_write",
           "clk_prepare", "clk_enable", "reset_control",
           "gpiod_", "dma_alloc", "dma_map", "iommu_",
           "pci_host_probe", "pci_scan", "pci_bus_", "pci_create",
           "devm_request_irq", "request_irq(", "devm_phy_get",
           "phy_power", "regulator_", "pm_runtime", "devm_of_pci",
           "/dev/mem", "power_on", "firmware_request",
        ):
            with self.subTest(forbidden=forbidden):
                # The comment containing "iommu" is harmless, but no
                # actual API call or mutation is permitted.
                real="\n".join(x for x in self.driver.splitlines()
                                if not x.lstrip().startswith("*") and
                                   not x.lstrip().startswith("//"))
                self.assertNotIn(forbidden,real)

    def test_no_private_firmware_or_identity(self):
        for forbidden in ("ECID:", "SerialNumber:",
                          "BEGIN PRIVATE", "BEGIN OPENSSH", ".hcd",
                          "private-firmware/", "runtime-apple-adt.bin"):
            self.assertNotIn(forbidden,self.driver)

    def test_patch_does_not_enable_device_tree_nodes(self):
        self.assertNotIn("arch/arm64/boot/dts/",self.patch)
        self.assertNotIn("status = \"okay\"",self.patch)


    def test_clean_replay_script_includes_0010_and_0011(self):
        sh=(ROOT/"scripts/check_kernel_rfc.sh").read_text()
        self.assertIn('00{01..11}-*.patch',sh)
        self.assertIn('drivers/pci/controller/pcie-apple-s8000-guard.o',sh)
        found=sorted(ROOT.glob("patches/00*.patch"))
        self.assertEqual(len(found),11)
        self.assertEqual([p.name[:4] for p in found],
                         [f"{i:04d}" for i in range(1,12)])


if __name__=="__main__":
    unittest.main()
