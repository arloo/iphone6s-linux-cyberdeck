"""Synthetic S8000 N71 port1 fail-closed guard/ADT consistency regressions.

Uses only the GPL C source embedded in the PUBLIC RFC11 patch; the real
Apple Device Tree, private Linux worktree and actual device are NOT read.
"""
from pathlib import Path
import importlib.util
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_port1_guard_consistency_gate.py"
PATCH=ROOT/"patches/0011-s8000-pcie-port1-research-guard-rfc.patch"
sp=importlib.util.spec_from_file_location("s8000_port1_guard_gate",TOOL)
gate=importlib.util.module_from_spec(sp)
assert sp and sp.loader
sp.loader.exec_module(gate)

def public_guard_source():
    contents=PATCH.read_text()
    target="diff --git a/drivers/pci/controller/pcie-apple-s8000-guard.c"
    assert contents.count(target)==1
    diff=contents.split(target,1)[1].split("\ndiff --git ",1)[0]
    return "".join(x[1:] for x in diff.splitlines(keepends=True)
                   if x.startswith("+") and not x.startswith("+++"))

def synthetic_metadata():
    return b"SYNTHETIC ORIGINAL-ADT-PLACEHOLDER FOR A MOCK ONLY"

class Port1OfflineGuardTests(unittest.TestCase):
    def setUp(self):
        self.source=public_guard_source()

    def check(self,source=None):
        with patch.object(gate.ADT,"audit_bytes",return_value=(
            "S8000_ADT_METADATA_GATE_PASS "
            "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED")):
            return gate.qualify(source if source is not None else self.source,
                                synthetic_metadata())

    def rejects(self,source):
        with self.assertRaises(gate.Port1Unqualified):
            self.check(source)

    def test_original_public_guard_matches_s8000_adt_geometry(self):
        r=self.check()
        self.assertEqual(r["candidate_windows"],3)
        self.assertEqual(r["protected_windows"],6)
        self.assertFalse(r["hardware_probe_enabled"])

    def test_wlan_candidate_windows_separate(self):
        self.assertEqual(gate.ranges_from_c(self.source,"wlan_candidate"),(
            gate.ADT.HOST_LAYOUT[3],gate.ADT.HOST_LAYOUT[4],
            gate.ADT.DART_LAYOUT[1]))

    def test_storage_base_changed_fails(self):
        self.rejects(self.source.replace("0x601000000ULL","0x601010000ULL"))

    def test_baseband_base_changed_fails(self):
        self.rejects(self.source.replace("0x603000000ULL","0x603010000ULL"))

    def test_global_core_range_changed_fails(self):
        self.rejects(self.source.replace("0x600000000ULL","0x600010000ULL"))

    def test_ecam_range_changed_fails(self):
        self.rejects(self.source.replace("0x610000000ULL","0x610010000ULL"))

    def test_wlan_dart1_swapped_with_dart0_fails(self):
        self.rejects(self.source.replace("0x602008000ULL","0x601008000ULL"))

    def test_wlan_port1_mmio_size_changed_fails(self):
        self.rejects(self.source.replace(
            "{ 0x602000000ULL, 0x4000 }",
            "{ 0x602000000ULL, 0x8000 }"))

    def test_removed_protected_storage_range_fails(self):
        self.rejects(self.source.replace(
            "{ 0x601000000ULL, 0xc000 },", ""))

    def test_duplicate_protected_range_fails(self):
        line="{ 0x603000000ULL, 0xc000 },"
        self.rejects(self.source.replace(line,line+"\n\t"+line))

    def test_probe_must_return_unsupported(self):
        self.rejects(self.source.replace(
            "return -EOPNOTSUPP;","return 0;"))

    def test_no_real_controller_binding(self):
        self.rejects(self.source.replace(
            "apple,s8000-pcie-research-blocked","apcie,s8000"))

    def test_no_mmio_write_helper(self):
        self.rejects(self.source.replace(
            "return -EOPNOTSUPP;",
            "writel(0, base);\n\treturn -EOPNOTSUPP;"))

    def test_no_pci_host_enumeration(self):
        self.rejects(self.source.replace(
            "return -EOPNOTSUPP;",
            "pci_host_probe(bridge);\n\treturn -EOPNOTSUPP;"))

    def test_missing_ad_hoc_isolation_guard_fails(self):
        self.rejects(self.source.replace(
            "apple_s8000_port1_metadata_isolated()", "true"))

    def test_expected_adt_error_is_fail_closed(self):
        with patch.object(gate.ADT,"audit_bytes",
                          return_value="UNRECOGNIZED_BOARD"):
            with self.assertRaises(gate.Port1Unqualified):
                gate.qualify(self.source,synthetic_metadata())

    def test_synthetic_arm64_rel_guard_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            elf=Path(td)/"guard.o"
            hdr=bytearray(64)
            hdr[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",hdr,16,1)
            struct.pack_into("<H",hdr,18,183)
            elf.write_bytes(hdr)
            gate.require_elf64_aarch64_rel(elf)

    def test_synthetic_x86_object_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            elf=Path(td)/"wrong.o"
            hdr=bytearray(64)
            hdr[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",hdr,16,1)
            struct.pack_into("<H",hdr,18,62)
            elf.write_bytes(hdr)
            with self.assertRaises(gate.Port1Unqualified):
                gate.require_elf64_aarch64_rel(elf)

    def test_no_hardware_apis_in_python_gate(self):
        text=TOOL.read_text()
        # The tool intentionally matches literal strings "writel(" and
        # "readl(" inside its source-text hazard scanner. Those are not
        # actual Python calls.
        for excluded in ("mmap(", "subprocess.run(", "write_bytes(",
                         "socket.", "modprobe ", "insmod ",
                         "/dev/mem", "git push"):
            self.assertNotIn(excluded,text)

if __name__=="__main__":
    unittest.main()
