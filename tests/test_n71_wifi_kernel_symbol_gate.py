"""Synthetic AArch64 kernel symbol coverage: no original kernel files here."""
from pathlib import Path
import importlib.util
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/n71_wifi_kernel_symbol_gate.py"
spec=importlib.util.spec_from_file_location("n71_symbol_gate",P)
g=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)

def fake_symvers():
    lines=[f"0x00000000\tsymbol_{i}\tvmlinux\tEXPORT_SYMBOL\t"
           for i in range(130)]
    lines.append("0x00000000\tmodule_only\tdriver_module\tEXPORT_SYMBOL\t")
    return ("\n".join(lines)+"\n").encode()

def fixture_modules():
    return {
        "cfg80211":({"symbol_1","symbol_2","verify_pkcs7_signature",
                     "__this_module"},{"cfg80211_connect_done"}),
        "brcmutil":({"symbol_3"},{"brcmu_d11_attach"}),
        "brcmfmac":({"symbol_4","cfg80211_connect_done","brcmu_d11_attach"},
                     {"brcmf_do_something"}),
        "gpio_apple_pmic":({"symbol_5","__this_module"},set()),
    }

class TestA9WiFiSymbolGate(unittest.TestCase):
    def test_symbol_map_read_only_valid(self):
        result=g.parse_kernel_exports(fake_symvers())
        self.assertEqual(len(result),130)

    def test_non_vmlinux_exports_not_treated_as_core_symbols(self):
        self.assertNotIn("module_only",g.parse_kernel_exports(fake_symvers()))

    def test_invalid_symbol_map_rejected(self):
        with self.assertRaises(g.IncompatibleSymbols):
            g.parse_kernel_exports(b"not a symbol map\n")

    def test_nm_export_symbol_metadata_parsing(self):
        use,exp=g.parse_nm("    U cfg80211_connect_done\n"
                           "0000000000 r __export_symbol_brcmu_d11_attach\n"
                           "    U __this_module\n")
        self.assertEqual(use,{"cfg80211_connect_done","__this_module"})
        self.assertEqual(exp,{"brcmu_d11_attach"})

    def test_expected_single_kernel_blocker(self):
        outcome=g.calculate(g.parse_kernel_exports(fake_symvers()),
                            fixture_modules())
        self.assertEqual(outcome["missing"]["cfg80211"],
                         ["verify_pkcs7_signature"])
        for other in ("brcmutil","brcmfmac","gpio_apple_pmic"):
            self.assertEqual(outcome["missing"][other],[])

    def test_inter_module_exports_resolve_brcmfmac(self):
        o=g.calculate(g.parse_kernel_exports(fake_symvers()),
                      fixture_modules())
        self.assertEqual(o["missing"]["brcmfmac"],[])
        self.assertGreater(o["resolved"]["brcmfmac"],0)

    def test_unexpected_missing_wifi_symbol_is_visible(self):
        a=fixture_modules()
        a["brcmfmac"][0].add("unknown_required_kernel_symbol")
        o=g.calculate(g.parse_kernel_exports(fake_symvers()),a)
        self.assertIn("unknown_required_kernel_symbol",
                      o["missing"]["brcmfmac"])

    def test_missing_module_set_rejected(self):
        a=fixture_modules()
        a.pop("cfg80211")
        with self.assertRaises(g.IncompatibleSymbols):
            g.calculate(g.parse_kernel_exports(fake_symvers()),a)

    def test_empty_object_imports_rejected(self):
        a=fixture_modules()
        a["gpio_apple_pmic"]=(set(),set())
        with self.assertRaises(g.IncompatibleSymbols):
            g.calculate(g.parse_kernel_exports(fake_symvers()),a)

    def test_valid_synthetic_elf64_aarch64_object(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"synthetic.o"
            hdr=bytearray(64)
            hdr[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",hdr,16,1)
            struct.pack_into("<H",hdr,18,183)
            p.write_bytes(hdr)
            g.aarch64_relocatable_file(p)

    def test_foreign_architecture_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"x86.o"
            hdr=bytearray(64)
            hdr[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",hdr,16,1)
            struct.pack_into("<H",hdr,18,62)
            p.write_bytes(hdr)
            with self.assertRaises(g.IncompatibleSymbols):
                g.aarch64_relocatable_file(p)

    def test_executable_not_relocatable_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"executable"
            hdr=bytearray(64)
            hdr[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",hdr,16,2)
            struct.pack_into("<H",hdr,18,183)
            p.write_bytes(hdr)
            with self.assertRaises(g.IncompatibleSymbols):
                g.aarch64_relocatable_file(p)

    def test_no_writes_or_live_device_calls(self):
        s=P.read_text()
        for forbidden in ("write_bytes(","open('/dev/", "insmod ",
                          "modprobe ","mmap(", "ioremap(", "writel(",
                          "readl(", "git push"):
            self.assertNotIn(forbidden,s)

    def test_known_missing_symbol_must_not_be_silenced(self):
        text=P.read_text()
        self.assertIn("verify_pkcs7_signature",text)
        self.assertIn("ALTERNATE_KERNEL_LINKAGE_AND_NATIVE_PCIE_WIFI_PROVEN=NO",
                      text)

if __name__=="__main__":
    unittest.main()
