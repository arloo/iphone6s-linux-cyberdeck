"""Adversarial offline tests for N71 S5L8960X iOS-ordered TTBR/TLB rebase.

No actual kernel image, firmware, USB, radio, DART MMIO, PCIe or phone
operation. Synthetic errors and mutation of an already public text patch.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s5l8960x_dart_ttbr_tlb_failclosed_offline_gate.py"
sp=importlib.util.spec_from_file_location("n71_ttbr_offline_test",SRC)
assert sp and sp.loader
M=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=M
sp.loader.exec_module(M)

def patch():
    return M.PATCH.read_text()

def false_elf(machine=183,kind=1):
    b=bytearray(120_000);b[:6]=b"\x7fELF\x02\x01"
    struct.pack_into("<HH",b,16,kind,machine)
    return bytes(b)

class TestN71OfflineS5LTTBRFailclosed(unittest.TestCase):
    def test_exact_public_12_hunk_patch_contract(self):
        self.assertTrue(M.patch_contract(patch()).startswith("--- a/drivers/iommu/apple-dart.c"))
    def test_single_driver_source_modified_only(self):
        self.assertEqual(patch().count("diff --git "),1)
    def test_orchard_provenance_and_gpl(self):
        source=patch()
        self.assertIn("SPDX-License-Identifier: GPL-2.0-only",source)
        self.assertIn("Berkay Kösebay",source)
        self.assertIn("Henrik Klee",source)
        self.assertIn("OrchardLinux",source)
    def test_missing_pci_controller_block_guard_delta_rejected(self):
        p=patch().replace("\n static bool apple_n71_s8000_wlan_dart1_blocked",
                          "\n+static bool apple_n71_s8000_wlan_dart1_blocked")
        if p==patch():
            p=patch().replace("\n+/* Orchard", "\n+apple_n71_s8000_wlan_dart1_blocked();\n+/* Orchard")
        with self.assertRaises(M.UnprovenSafety):
            M.patch_contract(p)
    def test_disallow_additional_modified_file(self):
        p=patch()+"\ndiff --git a/drivers/pci/controller/Kconfig b/drivers/pci/controller/Kconfig\n"
        with self.assertRaises(M.UnprovenSafety):M.patch_contract(p)
    def test_required_readback_missing_rejected(self):
        for token in ("apple_dart_streams_ttbrs_are","apple_dart_streams_tcr_is"):
            with self.subTest(token=token):
                with self.assertRaises(M.UnprovenSafety):
                    M.patch_contract(patch().replace(token,"removed_guard_xyz"))
    def test_missing_sticky_flush_error_rejected(self):
        with self.assertRaises(M.UnprovenSafety):
            M.patch_contract(patch().replace("flush_error","discarded_error"))
    def test_missing_block_owned_streams_rejected(self):
        with self.assertRaises(M.UnprovenSafety):
            M.patch_contract(patch().replace("apple_dart_domain_block",
                                             "silent_continue_on_error"))
    def test_missing_tlb_return_rejected(self):
        with self.assertRaises(M.UnprovenSafety):
            M.patch_contract(patch().replace(
              "return apple_dart_domain_flush_tlb(to_dart_domain(domain));",
              "return 0;"))
    def test_missing_dynamic_original_dt_fields_rejected(self):
        for token in ("apple,error-reflector","apple,fetch-config","apple,diag-config"):
            with self.subTest(field=token):
                with self.assertRaises(M.UnprovenSafety):
                    M.patch_contract(patch().replace(token,"unverified,register"))
    def test_synthetic_all_good_translations_allowed(self):
        self.assertEqual(M.model_fail_closed(),(True,False))
    def test_synthetic_tcr_disable_readback_failure_blocks(self):
        self.assertEqual(M.model_fail_closed(disabled_ok=False),(False,True))
    def test_synthetic_tcr_enable_readback_failure_blocks(self):
        self.assertEqual(M.model_fail_closed(enabled_ok=False),(False,True))
    def test_synthetic_tlb_timeout_blocks(self):
        self.assertEqual(M.model_fail_closed(tlb_ok=False),(False,True))
    def test_synthetic_ttbr_readback_mismatch_blocks(self):
        self.assertEqual(M.model_fail_closed(ttbr_ok=False),(False,True))
    def test_synthetic_malformed_outcome_rejected(self):
        for v in (None,1,0,"false",[],()):
            with self.subTest(v=v):
                with self.assertRaises(M.UnprovenSafety):
                    M.model_fail_closed(tlb_ok=v)
    def test_elf_arm64_relocatable_accepted(self):
        self.assertTrue(M.elf_contract(false_elf()))
    def test_elf_host_x86_arch_rejected(self):
        with self.assertRaises(M.UnprovenSafety):
            M.elf_contract(false_elf(machine=62))
    def test_elf_executable_not_relocatable_rejected(self):
        with self.assertRaises(M.UnprovenSafety):
            M.elf_contract(false_elf(kind=2))
    def test_actual_real_phone_hardware_not_claimed(self):
        s=SRC.read_text()
        for marker in ("N71_PHYSICAL_ALL_STREAM_RESET_AND_SID_ISOLATION_PROVEN=NO",
                       "N71_NATIVE_PCIE_WIFI_OR_IOMMU_LINK_PROVEN=NO",
                       "N71_NO_PHONE_MMIO_DMA_NAND_OR_REBOOT=YES"):
            self.assertIn(marker,s)
    def test_no_high_risk_commands_in_offline_tool(self):
        s=SRC.read_text()
        for token in ("subprocess.run","subprocess.Popen","os.system(",
                      "devmem","insmod","modprobe","palera1n",
                      "iphone_erase","write32("):
            self.assertNotIn(token,s)
    def test_synthetic_diff_has_expected_file_namespace(self):
        old="one\ntwo\n";new="one\nchanged\n"
        self.assertIn("+++ b/drivers/iommu/apple-dart.c",M.diff_body(old,new))

if __name__=="__main__":unittest.main()
