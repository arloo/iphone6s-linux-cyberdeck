"""Adversarial original-S8000 port configuration MMIO-pointer source tests.

All fake original bytes are **synthetic** code-signature fixtures, not
proprietary Apple kernel, NVRAM, real registers or phone MMIO.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_original_port_config_pointer_provenance_gate.py"
sp=importlib.util.spec_from_file_location("n71_s8000_port_config_pointer_test",SRC)
assert sp and sp.loader
M=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=M
sp.loader.exec_module(M)

def synthesized():
    b=bytearray(18552)
    for group in M.GROUPS:
        for offset,word in group.items():
            struct.pack_into("<I",b,offset,word)
    return bytes(b)

class TestN71PortConfigPointerProvenance(unittest.TestCase):
    def test_known_selected_arm64_signatures(self):
        self.assertTrue(M.audit_words(synthesized()))
    def test_every_original_opcode_mutation_rejected(self):
        known=synthesized()
        for group in M.GROUPS:
            for at in group:
                with self.subTest(offset=hex(at)):
                    bad=bytearray(known)
                    word=struct.unpack_from("<I",bad,at)[0]
                    struct.pack_into("<I",bad,at,word^0x1)
                    with self.assertRaises(M.UnqualifiedPortMMIO):
                        M.audit_words(bytes(bad))
    def test_source_size_mismatch_rejected(self):
        with self.assertRaises(M.UnqualifiedPortMMIO):
            M.audit_words(synthesized()[:-4])
    def test_non_bytes_source_rejected(self):
        with self.assertRaises(M.UnqualifiedPortMMIO):
            M.audit_words(bytearray(synthesized()))
    def test_duplicated_source_signature_offsets_not_accepted(self):
        offsets=[k for group in M.GROUPS for k in group]
        self.assertEqual(len(offsets),len(set(offsets)))
    def test_method1568_uses_two_source_relative_offsets(self):
        self.assertEqual(M.CONFIG_SWITCH_OPS[0xc10],0x52802481)
        self.assertEqual(M.CONFIG_SWITCH_OPS[0xc78],0x52802501)
    def test_config_writer_has_access_validation_before_store(self):
        self.assertLess(0x1bc0,0x1bc8)
        self.assertEqual(M.CONFIG_WRITE_OPS[0x1bc4],0x36000120)
        self.assertEqual(M.CONFIG_WRITE_OPS[0x1bcc],0xb8334915)
    def test_provider_result_pointer_assigned_before_writer(self):
        self.assertEqual(M.PROVIDER_INIT_OPS[0x2060],0xf941e908)
        self.assertEqual(M.PROVIDER_INIT_OPS[0x2074],0xf9006a60)
        self.assertEqual(M.CONFIG_WRITE_OPS[0x1bc8],0xf9406a88)
    def test_second_mapping_result_distinct(self):
        self.assertEqual(M.PROVIDER_INIT_OPS[0x2088],0xf9006e60)
    def test_physical_provider_not_proven_denies_any_symbolic_write(self):
        for offset in (0x124,0x128):
            with self.subTest(offset=offset):
                with self.assertRaises(M.UnqualifiedPortMMIO):
                    M.symbolic_port_config(offset,0x12345678,False)
    def test_synthetic_only_proven_scope_values(self):
        self.assertEqual(M.symbolic_port_config(0x124,1,True),(0x124,1))
        self.assertEqual(M.symbolic_port_config(0x128,0xffffffff,True),
                         (0x128,0xffffffff))
    def test_unknown_offsets_fail_even_with_synthetic_proof(self):
        for at in (0,0x120,0x126,0x200,0x10000,-1):
            with self.subTest(at=at):
                with self.assertRaises(M.UnqualifiedPortMMIO):
                    M.symbolic_port_config(at,1,True)
    def test_overwide_values_rejected(self):
        for val in (-1,1<<32,1<<64):
            with self.subTest(val=val):
                with self.assertRaises(M.UnqualifiedPortMMIO):
                    M.symbolic_port_config(0x124,val,True)
    def test_invalid_argument_type_rejected(self):
        for value,known in ((True,True),(1,"true"),(None,True),(1,1),(1,None)):
            with self.subTest(value=value,known=known):
                with self.assertRaises(M.UnqualifiedPortMMIO):
                    M.symbolic_port_config(0x128,value,known)
    def test_no_physical_mmio_success_claim(self):
        source=SRC.read_text()
        for k in ("N71_PORT1_PHYSICAL_MMIO_PROVIDER_REGION_BOUNDARY_PROVEN=NO",
                  "N71_PORT1_0X124_0X128_CROSSPORT_EFFECTS_SAFE=NO",
                  "N71_S8000_PCIE_DART1_REQUESTER_SID_PROVEN=NO",
                  "N71_PHYSICAL_PCIE_OR_NATIVE_BCM4350_WIFI_ACTIVATION_AUTHORIZED=NO"):
            self.assertIn(k,source)
    def test_source_only_no_phone_commands(self):
        src=SRC.read_text()
        for unsafe in ("import subprocess","os.system(","open(\"/dev/mem\"",
                       "palera1n -", "ssh root@","writel(", "ioremap("):
            self.assertNotIn(unsafe,src)

if __name__=="__main__":unittest.main()
