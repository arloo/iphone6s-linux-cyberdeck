"""Synthetic fail-closed Linux Wi-Fi stack prerequisite checks for iPhone6s N71.

No remote shell, original firmware, DMA, MMIO, hardware activation or kernel
build operations: test only Kconfig and known Broadcom driver table strings.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_brcmfmac_pcie_kernel_readiness_gate.py"
SP=importlib.util.spec_from_file_location("n71_brcmfmac_software_gate",SRC)
assert SP and SP.loader
M=importlib.util.module_from_spec(SP)
sys.modules[SP.name]=M
SP.loader.exec_module(M)

BASE={"WIRELESS":"n","WLAN":"n","MODULES":"y","BT":"y",
      "APPLE_DART":"y","PCIE_APPLE":"y"}
CAND={**BASE,"WIRELESS":"y","WLAN":"y",
      **{symbol:"y" for symbol in M.REQUIRED_BUILTIN},
      **{symbol:"n" for symbol in M.MUST_REMAIN_DISABLED}}
HW="#define BRCM_PCIE_4350_DEVICE_ID 0x43a3\n"
PCIE='''BRCMF_PCIE_DEVICE(BRCM_PCIE_4350_DEVICE_ID, WCC)
BRCMF_FW_DEF(4350C, "brcmfmac4350c2-pcie");
BRCMF_FW_ENTRY(BRCM_CC_4350_CHIP_ID, 0x000000FF, 4350C),
'''

def conf(x:dict)->str:
    return "\n".join(
        f"CONFIG_{k}={v}" if v!="n" else f"# CONFIG_{k} is not set"
        for k,v in sorted(x.items())
    )+"\n"

class TestN71OfflineBrcmfmacConfig(unittest.TestCase):
    def test_valid_separate_wifi_built_in_config(self):
        self.assertTrue(M.check_config(conf(BASE),conf(CAND)))

    def test_valid_pcie_id_and_firmware_source(self):
        self.assertTrue(M.check_source(HW,PCIE))

    def test_baseline_must_remain_wireless_disabled(self):
        old={**BASE,"WIRELESS":"y"}
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_config(conf(old),conf(CAND))

    def test_missing_top_level_wlan_rejected(self):
        candidate={**CAND,"WLAN":"n"}
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_config(conf(BASE),conf(candidate))

    def test_missing_wireless_stack_rejected(self):
        for key in M.REQUIRED_BUILTIN:
            with self.subTest(key=key):
                candidate={**CAND,key:"n"}
                with self.assertRaises(M.SoftwareReadinessUnproven):
                    M.check_config(conf(BASE),conf(candidate))

    def test_modules_not_disabled(self):
        candidate={**CAND,"MODULES":"n"}
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_config(conf(BASE),conf(candidate))

    def test_original_bluetooth_remains_enabled(self):
        candidate={**CAND,"BT":"n"}
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_config(conf(BASE),conf(candidate))

    def test_original_dart_and_pcie_host_config_not_changed(self):
        for key in ("APPLE_DART","PCIE_APPLE"):
            with self.subTest(key=key):
                candidate={**CAND,key:"n"}
                with self.assertRaises(M.SoftwareReadinessUnproven):
                    M.check_config(conf(BASE),conf(candidate))

    def test_unapproved_broadcom_usb_sdio_transport_rejected(self):
        for key in ("BRCMFMAC_SDIO","BRCMFMAC_USB"):
            with self.subTest(key=key):
                candidate={**CAND,key:"y"}
                with self.assertRaises(M.SoftwareReadinessUnproven):
                    M.check_config(conf(BASE),conf(candidate))

    def test_unsafe_hardware_guard_change_rejected(self):
        for key in ("PCIE_APPLE_S8000_RESEARCH_GUARD","NL80211_TESTMODE"):
            with self.subTest(key=key):
                candidate={**CAND,key:"y"}
                with self.assertRaises(M.SoftwareReadinessUnproven):
                    M.check_config(conf(BASE),conf(candidate))

    def test_driver_module_not_accepted_instead_of_built_in(self):
        candidate={**CAND,"BRCMFMAC":"m"}
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_config(conf(BASE),conf(candidate))

    def test_wrong_pcie_device_id_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_source(HW.replace("0x43a3","0x43a4"),PCIE)

    def test_missing_4350_pcie_table_entry_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_source(HW,PCIE.replace("BRCMF_PCIE_DEVICE","BRCMF_PCIE_UNKNOWN"))

    def test_missing_4350c2_firmware_template_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_source(HW,PCIE.replace("brcmfmac4350c2-pcie","brcmfmac9999-pcie"))

    def test_broadcom_chipid_mask_missing_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_source(HW,PCIE.replace("BRCM_CC_4350_CHIP_ID","BRCM_CC_UNKNOWN"))

    def test_duplicate_kconfig_is_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.config_dict("CONFIG_CFG80211=y\nCONFIG_CFG80211=n\n")

    def test_bad_unknown_module_image_rejected(self):
        with self.assertRaises(M.SoftwareReadinessUnproven):
            M.check_image(b"not a known good A9 image",b"not an image")

    def test_does_not_interact_with_phone_or_claim_native_wifi(self):
        s=SRC.read_text()
        for forbidden in ("insmod","devmem","ioremap(","writel(",
                          "modprobe","dfu","palera1n","ssh ",
                          "N71_NATIVE_WIFI_SUCCESS=YES"):
            self.assertNotIn(forbidden,s)
        self.assertIn("N71_S8000_PHYSICAL_PCIE_HOST_DART_DMA_AND_WLAN_INTERFACE_PROVEN=NO",s)

if __name__=="__main__":
    unittest.main()
