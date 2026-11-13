"""Adversarial synthetic BCM4350 PCIe OTP parser integration tests. No device."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_bcm4350_otp_software_arm64_offline_gate.py"
spec=importlib.util.spec_from_file_location("n71_otp_gate",SRC)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

class TestN71Bcm4350Otp(unittest.TestCase):
    def test_no_otp_available_is_explicitly_optional(self):
        self.assertEqual(M.otp_words(0),0)
    def test_minimum_present_otp_does_not_underflow(self):
        self.assertEqual(M.otp_words(1),32)
    def test_example_apple_otp_size_from_upstream(self):
        self.assertEqual(M.otp_words(5),288)
    def test_upper_4bit_encoding_bounded(self):
        self.assertEqual(M.otp_words(15),928)
    def test_every_valid_otp_encoding_is_small_and_aligned(self):
        for enc in range(16):
            with self.subTest(enc=enc):
                result=M.otp_words(enc)
                self.assertGreaterEqual(result,0)
                self.assertLessEqual(result,1024)
                self.assertEqual(result%32,0)
    def test_negative_and_overwide_encoding_fail_closed(self):
        for enc in (-1,-5,16,31,1<<32):
            with self.subTest(enc=enc):
                with self.assertRaises(M.UnsafeOtpSource):M.otp_words(enc)
    def test_bool_float_string_encoding_rejected(self):
        for enc in (True,5.0,"5",None):
            with self.subTest(enc=enc):
                with self.assertRaises(M.UnsafeOtpSource):M.otp_words(enc)
    def test_exact_patch_two_hunks_and_original_author(self):
        p=M.PATCH.read_text()
        self.assertEqual(sum(s.startswith("@@ ") for s in p.splitlines()),2)
        self.assertIn("Henrik Klee",p)
        self.assertIn("SPDX-License-Identifier: GPL-2.0-only",p)
    def test_patch_no_board_specific_register_changes(self):
        p=M.PATCH.read_text()
        added="\n".join(x for x in p.splitlines()
                        if x.startswith("+") and not x.startswith("+++"))
        for dangerous in ("apple_dart_hw_reset(", "writel(", "gpio_set_value(",
                          "iommu_map(", "clk_prepare_enable(", "pci_host_probe("):
            self.assertNotIn(dangerous,added)
    def test_missing_otp_is_optional_not_fatal(self):
        self.assertIn("if (ret && optional)",M.PATCH.read_text())
        self.assertIn("return 0;",M.PATCH.read_text())
    def test_4350_chip_specific(self):
        self.assertIn("case BRCM_CC_4350_CHIP_ID:",M.PATCH.read_text())
    def test_real_otp_firmware_variant_not_overclaimed(self):
        source=SRC.read_text()
        self.assertIn("N71_BCM4350C5_OTP_FORMAT_VALIDATED_ON_N71_HARDWARE=NO",source)
        self.assertIn("N71_PHYSICAL_PCIE_DART1_OR_NATIVE_WIFI_PROVEN=NO",source)
    def test_no_run_commands_or_device_access_in_gate(self):
        code=SRC.read_text()
        for token in ("import subprocess","os.system(","/dev/mem","insmod ",
                      "palera1n ","/dev/input/event0"):
            self.assertNotIn(token,code)
    def test_invalid_private_source_hash_must_abort(self):
        with self.assertRaises(M.UnsafeOtpSource):
            M.source_guard(b"BAD",b"BAD",b"BAD",b"BAD")
    def test_source_diff_paths_are_restricted(self):
        source=M.diff_of("old\n","new\n")
        self.assertIn("+++ b/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c",source)

if __name__=="__main__":unittest.main()
