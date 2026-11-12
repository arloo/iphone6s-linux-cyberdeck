"""Synthetic mutation tests for Apple N71 S5L TTBR and PTE software format."""
from __future__ import annotations
import importlib.util,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_original_s5l_dart1_ttbr_pte_format_gate.py"
SP=importlib.util.spec_from_file_location("n71_s5l_format_tests",TOOL)
assert SP and SP.loader
G=importlib.util.module_from_spec(SP);SP.loader.exec_module(G)

def native():
    data=bytearray(G.BASE.ORIGINAL.EXPECTED_LENGTHS[G.BASE.ORIGINAL.S5L])
    for at,w in {**G.ORIGINAL_TTBR_PROGRAM_WORDS,**G.ORIGINAL_PTE_BUILDER_WORDS}.items():
        struct.pack_into("<I",data,at,w)
    return bytes(data)

TTBR_LINUX="""
#define DART_T8020_TTBR_VALID BIT(31)
#define DART_T8020_TTBR_SHIFT 12
#define DART_T8020_TTBR_ADDR_FIELD_SHIFT 0
static const struct apple_dart_hw apple_dart_hw_s5l8960x = {
 .ttbr_valid = DART_T8020_TTBR_VALID,
 .ttbr_addr_field_shift = DART_T8020_TTBR_ADDR_FIELD_SHIFT,
 .ttbr_shift = DART_T8020_TTBR_SHIFT,
};
"""
PGTABLE_LINUX="""
#define APPLE_DART1_PADDR_MASK GENMASK_ULL(35, 12)
#define APPLE_DART_PTE_VALID BIT(0)
#define APPLE_DART1_PTE_PROT_SP_DIS BIT(1)
typedef u64 dart_iopte;
static void some_pte_access(struct dart_io_pgtable *data) {
 if (data->iop.fmt == APPLE_DART) {
  pte |= APPLE_DART1_PTE_PROT_SP_DIS;
 }
 pte |= APPLE_DART_PTE_VALID;
}
"""
class TestOriginalA9S5LTTBRPTEFormat(unittest.TestCase):
    def test_genuine_source_pattern_fixture_accepted(self):
        self.assertTrue(G.verify_native_instruction_format(native()))

    def test_every_ttbr_programming_arm64_word_mutation_rejected(self):
        for at in G.ORIGINAL_TTBR_PROGRAM_WORDS:
            with self.subTest(offset=hex(at)):
                b=bytearray(native());b[at]^=1
                with self.assertRaises(G.FormatNotQualified):
                    G.verify_native_instruction_format(bytes(b))

    def test_every_pte_builder_arm64_word_mutation_rejected(self):
        for at in G.ORIGINAL_PTE_BUILDER_WORDS:
            with self.subTest(offset=hex(at)):
                b=bytearray(native());b[at]^=1
                with self.assertRaises(G.FormatNotQualified):
                    G.verify_native_instruction_format(bytes(b))

    def test_wrong_apple_text_length_rejected(self):
        with self.assertRaises(G.FormatNotQualified):
            G.verify_native_instruction_format(native()[:-4])

    def test_linux_synthetic_field_macros_accepted(self):
        self.assertTrue(G.verify_linux_format(TTBR_LINUX,PGTABLE_LINUX))

    def test_linux_ttbr_valid_bit_mutation_rejected(self):
        b=TTBR_LINUX.replace("BIT(31)","BIT(0)")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(b,PGTABLE_LINUX)

    def test_linux_ttbr_page_shift_mutation_rejected(self):
        b=TTBR_LINUX.replace("TTBR_SHIFT 12","TTBR_SHIFT 14")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(b,PGTABLE_LINUX)

    def test_linux_ttbr_address_field_shift_mutation_rejected(self):
        b=TTBR_LINUX.replace("ADDR_FIELD_SHIFT 0","ADDR_FIELD_SHIFT 2")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(b,PGTABLE_LINUX)

    def test_linux_dart1_page_address_mask_mutation_rejected(self):
        b=PGTABLE_LINUX.replace("GENMASK_ULL(35, 12)","GENMASK_ULL(37, 10)")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(TTBR_LINUX,b)

    def test_linux_dart1_valid_pte_bit_mutation_rejected(self):
        b=PGTABLE_LINUX.replace("PTE_VALID BIT(0)","PTE_VALID BIT(2)")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(TTBR_LINUX,b)

    def test_linux_dart1_sp_disable_flag_mutation_rejected(self):
        b=PGTABLE_LINUX.replace("PTE_PROT_SP_DIS BIT(1)","PTE_PROT_SP_DIS BIT(3)")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(TTBR_LINUX,b)

    def test_linux_requires_64bit_pte(self):
        b=PGTABLE_LINUX.replace("typedef u64 dart_iopte","typedef u32 dart_iopte")
        with self.assertRaises(G.FormatNotQualified):
            G.verify_linux_format(TTBR_LINUX,b)

    def test_ttbr_36_bit_4k_phys_frame_software_encode(self):
        self.assertEqual(G.encode_ttbr(0),0x80000000)
        self.assertEqual(G.encode_ttbr(0x12345000),0x80012345)
        self.assertEqual(G.encode_ttbr(0xffffff000),0x80ffffff)

    def test_ttbr_rejects_unaligned_and_out_of_36bit(self):
        for n in (-1,1,0x12345678,1<<36,1<<40,1.0,"0",None):
            with self.subTest(n=str(n)):
                with self.assertRaises(G.FormatNotQualified):
                    G.encode_ttbr(n)

    def test_pte_36_bit_page_and_flags_software_encode(self):
        self.assertEqual(G.encode_dart_pte(0x12345000,True),0x12345003)
        self.assertEqual(G.encode_dart_pte(0x12345000,False),0x12345002)
        self.assertEqual(G.encode_dart_pte(0xffffff000,True),0xffffff003)

    def test_pte_rejects_bad_physical_page_and_flag(self):
        for n in (-1,1,0x1234,1<<36,1<<40,"0",None):
            with self.subTest(n=str(n)):
                with self.assertRaises(G.FormatNotQualified):
                    G.encode_dart_pte(n,True)
        for flag in (0,1,"true",None):
            with self.assertRaises(G.FormatNotQualified):
                G.encode_dart_pte(0x12345000,flag)

    def test_full_check_fails_if_private_native_word_is_mutated(self):
        b=bytearray(native());b[0x21dc]^=4
        modules={G.BASE.ORIGINAL.S5L:{"code":bytes(b)}}
        with patch.object(G.BASE,"original_ttbr_layout",return_value=True),\
             patch.object(G.BASE,"check_linux_source",return_value=True),\
             patch.object(G.BASE.ORIGINAL,"extract_original_modules",
                          return_value=({},modules)):
            with self.assertRaises(G.FormatNotQualified):
                G.check_all(b"SYNTHETIC",b"ADT",TTBR_LINUX,PGTABLE_LINUX)

    def test_private_missing_file_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(G.BASE.TTBRLayoutNotProven):
                G.source_bytes(Path(tmp)/"absent",1000)

    def test_private_symlink_file_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"synthetic";p.write_bytes(b"SYNTHETIC_DATA")
            link=Path(tmp)/"link";link.symlink_to(p)
            with self.assertRaises(G.BASE.TTBRLayoutNotProven):
                G.source_bytes(link,1000)

    def test_malformed_cli_does_not_disclose_private_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"SYNTHETIC_UNIQUE_PRIVATE_TRACE_121";p.write_bytes(b"bad data")
            args=[sys.executable,str(TOOL),str(p),str(p),str(p),str(p)]
            res=subprocess.run(args,text=True,capture_output=True,timeout=15)
            self.assertNotEqual(res.returncode,0)
            self.assertIn("FAIL_CLOSED",res.stderr)
            self.assertNotIn(str(p),res.stderr+res.stdout)

    def test_no_live_mmio_dma_or_requester_sid_claim(self):
        text=TOOL.read_text()
        self.assertIn("PHYSICAL_WLAN_PCIE_REQUESTER_TO_DART_SID_PROVEN=NO",text)
        self.assertIn("AUTHORIZATION_TO_WRITE_DART1_MMIO_OR_TTBR=NO",text)
        for call in ("ioremap(", "readl(", "writel(", "ioctl(", "socket(",
                     "pci_host_probe(", "dma_map("):
            self.assertNotIn(call,text)

if __name__=="__main__":unittest.main()
