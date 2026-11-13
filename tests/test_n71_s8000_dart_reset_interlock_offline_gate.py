"""Adversarial offline tests: refuse unqualified N71 S8000 all-stream DART reset."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_dart_reset_interlock_offline_gate.py"
sp=importlib.util.spec_from_file_location("s8000_reset_interlock",SRC)
assert sp and sp.loader
M=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=M
sp.loader.exec_module(M)

def text_patch():return M.PATCH.read_text()

def fake_elf(machine=183,typ=1):
    data=bytearray(105000);data[:6]=b"\x7fELF\x02\x01"
    struct.pack_into("<HH",data,16,typ,machine)
    return bytes(data)

class TestS8000ResetInterlockOffline(unittest.TestCase):
    def test_exact_two_hunk_patch_contract(self):
        self.assertEqual(text_patch().count("\n@@ "),2)
        self.assertTrue(M.patch_contract(text_patch()).startswith("--- a/drivers/iommu/apple-dart.c"))
    def test_only_one_driver_source_file(self):
        self.assertEqual(text_patch().count("diff --git "),1)
    def test_legacy_s8000_is_always_denied(self):
        self.assertFalse(M.symbolic_reset_allowed("apple,s8000","other",True))
    def test_n71_is_denied_even_when_soc_string_incomplete(self):
        self.assertFalse(M.symbolic_reset_allowed("unknown","apple,n71",True))
    def test_iphone8_1_alias_denied_even_if_soc_unidentified(self):
        self.assertFalse(M.symbolic_reset_allowed("unknown","apple,iphone8,1",True))
    def test_other_soc_legacy_not_categorically_rejected(self):
        self.assertTrue(M.symbolic_reset_allowed("apple,s8003","apple,n71m",True))
    def test_nonlegacy_non_s5l_not_modified_by_this_interlock(self):
        self.assertTrue(M.symbolic_reset_allowed("apple,s8000","apple,n71",False))
    def test_all_four_owned_and_unowned_sid_have_same_denial_policy(self):
        for sid in range(4):
            with self.subTest(sid=sid):
                self.assertFalse(M.symbolic_reset_allowed("apple,s8000","apple,n71",True))
    def test_invalid_symbolic_values_rejected(self):
        for soc,board,old in (("apple,s8000","apple,n71",1),
                              ("apple,s8000","apple,n71","true"),
                              (None,"apple,n71",True),("apple,s8000",None,True)):
            with self.subTest(soc=soc,old=old):
                with self.assertRaises(M.UnsafeInterlock):
                    M.symbolic_reset_allowed(soc,board,old)
    def test_original_global_reset_still_documented_in_contract(self):
        self.assertIn("bitmap_set(stream_map.sidmap, 0, dart->num_streams);",SRC.read_text())
    def test_no_override_or_enable_flag_added(self):
        patch=text_patch()
        for key in ("module_param(", "force_dart_reset", "iommu_map(", "pci_host_probe(",
                    "+\twritel(", "+\tioremap(", "allow_unsafe_reset"):
            self.assertNotIn(key,patch)
    def test_missing_guard_definition_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                "apple_dart_s8000_unqualified_global_reset",
                "arbitrary_operation"))
    def test_missing_n71_machine_compatibility_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                'of_machine_is_compatible("apple,n71")',
                'of_machine_is_compatible("apple,s8003")'))
    def test_missing_eopnotsupp_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                "return -EOPNOTSUPP;", "return 0;"))
    def test_missing_remove_error_handling_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                "if (apple_dart_hw_reset(dart))", "apple_dart_hw_reset(dart);"))
    def test_new_mmio_write_operation_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                "return -EOPNOTSUPP;", "writel(0, dart->regs);\n\t\treturn -EOPNOTSUPP;"))
    def test_second_source_file_modified_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch()+"\ndiff --git a/arch/arm64/test.c b/arch/arm64/test.c\n")
    def test_removal_of_original_reset_instead_of_guard_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.patch_contract(text_patch().replace(
                "-\tapple_dart_hw_reset(dart);",
                "-\tapple_dart_hw_disable_dma(&stream_map);"))
    def test_elf_aarch64_relocatable_accepted(self):
        self.assertTrue(M.object_contract(fake_elf()))
    def test_host_elf_x86_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.object_contract(fake_elf(machine=62))
    def test_executable_elf_rejected(self):
        with self.assertRaises(M.UnsafeInterlock):
            M.object_contract(fake_elf(typ=2))
    def test_phone_work_not_misrepresented(self):
        tool=SRC.read_text()
        self.assertIn("N71_PHYSICAL_DART1_SID_OR_SHARED_ROOT_ISOLATION_PROVEN=NO",tool)
        self.assertIn("N71_BCM4350_PCIE_OR_NATIVE_WIFI_ENUMERATED=NO",tool)
        self.assertIn("N71_NO_PHONE_REBOOT_DART_MMIO_NAND_OR_DMA=YES",tool)
    def test_no_hardware_invocations_in_public_gate(self):
        source=SRC.read_text()
        for command in ("import subprocess", "from subprocess import",
                        "subprocess.run(", "subprocess.Popen(", "os.system(",
                        "GenUI", "tools.mcp__", "open(\"/dev/mem\""):
            self.assertNotIn(command,source)

if __name__=="__main__":unittest.main()
