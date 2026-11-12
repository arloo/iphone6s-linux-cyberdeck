"""Original iPhone 6s A9 root port1 bit-control chain: adversarial tests.

All inputs in this module are SYNTHETIC; no original proprietary source,
firmware/ADT, device ID, driver, MMIO address mapping or radio is accessed.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import random
import struct
import sys
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"tools/n71_s8000_original_port1_root_bit_control_chain_gate.py"
spec=importlib.util.spec_from_file_location("n71_s8000_bit_chain",PATH)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

def code_fixture():
    sh=bytearray(18552)
    embedded=bytearray(46924)
    for off,word in M.PINNED.items():
        struct.pack_into("<I",sh,off,word)
    struct.pack_into("<I",embedded,0x4704,0xf940d688)
    struct.pack_into("<I",embedded,0x4708,0xb8356913)
    return sh,embedded

def seeded(seed=0x5a):
    return {(p,k):(seed ^ p*0x01020408 ^ k*0x13579bdf)&0xffffffff
            for p in range(4) for k in (2,3,4,5)}

class TestN71OriginalS8000RootBitControl(unittest.TestCase):
    def test_all_original_root_control_signature_words(self):
        s,e=code_fixture()
        self.assertTrue(M.check_control_rmw_original(bytes(s),bytes(e)))

    def test_any_original_root_control_word_change_fails_closed(self):
        for off in M.PINNED:
            with self.subTest(offset=off):
                s,e=code_fixture()
                s[off]^=1
                with self.assertRaises(M.OriginalRootControlNotQualified):
                    M.check_control_rmw_original(bytes(s),bytes(e))

    def test_original_root_write32_mapped_pointer_field_must_match(self):
        s,e=code_fixture()
        e[0x4704]^=0x10
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.check_control_rmw_original(bytes(s),bytes(e))

    def test_original_root_write32_memory_store_must_match(self):
        s,e=code_fixture()
        e[0x4708]^=0x10
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.check_control_rmw_original(bytes(s),bytes(e))

    def test_invalid_original_kext_lengths_rejected(self):
        s,e=code_fixture()
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.check_control_rmw_original(bytes(s[:-1]),bytes(e))
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.check_control_rmw_original(bytes(s),bytes(e[:-1]))

    def test_all_four_ports_selector_offsets(self):
        for port in range(4):
            self.assertEqual(M.offsets(port),
                {2:0x100+port*0x80,3:0x114+port*0x80,
                 4:0x124+port*0x80,5:0x12c+port*0x80})

    def test_real_port1_static_known_offsets(self):
        self.assertEqual(M.offsets(1),
            {2:0x180,3:0x194,4:0x1a4,5:0x1ac})

    def test_bad_port_indices_refused(self):
        for port in (-1,4,8,1.0,"1",True,None):
            with self.subTest(port=port):
                with self.assertRaises(M.OriginalRootControlNotQualified):
                    M.offsets(port)

    def test_root_vtable_eight_method_target_check(self):
        mods={"a9":{"vm":0x100000,"vptr":0x900000},
              "shared":{"vm":0x200000},
              "embedded":{"vm":0x300000}}
        table={slot:mods[owner]["vm"]+offset
               for slot,(owner,offset) in M.EXPECTED_ROOT_SLOT_TARGETS.items()}
        def read(_bin,_main,address):
            return table[(address-mods["a9"]["vptr"])]
        with patch.object(M.ROOT.G,"read_data_pointer",side_effect=read):
            self.assertTrue(M.check_vtables(b"",{},mods))

    def test_each_root_vtable_target_mutation_rejected(self):
        mods={"a9":{"vm":0x100000,"vptr":0x900000},
              "shared":{"vm":0x200000},
              "embedded":{"vm":0x300000}}
        original={slot:mods[owner]["vm"]+offset
                  for slot,(owner,offset) in M.EXPECTED_ROOT_SLOT_TARGETS.items()}
        for slot in original:
            with self.subTest(slot=slot):
                table=original.copy()
                table[slot]+=4
                with patch.object(M.ROOT.G,"read_data_pointer",
                     side_effect=lambda _a,_b,addr:table[addr-mods["a9"]["vptr"]]):
                    with self.assertRaises(M.OriginalRootControlNotQualified):
                        M.check_vtables(b"",{},mods)

    def test_no_optional_root_id2_bit20_write(self):
        original=seeded()
        after,ops=M.symbolic_port1_only_rmw(original,False)
        self.assertEqual(ops,((4,0,0),(3,0,1),(2,8,0),(4,0,1)))
        self.assertEqual(len(ops),4)
        self.assertEqual(after[(1,2)]&0x100,0)

    def test_with_optional_root_id2_bit20_write(self):
        original=seeded()
        after,ops=M.symbolic_port1_only_rmw(original,True)
        self.assertEqual(ops,((4,0,0),(3,0,1),(2,8,0),
                              (2,20,1),(4,0,1)))
        self.assertEqual(after[(1,2)]&(1<<20),1<<20)

    def test_port1_id3_bit0_set(self):
        after,_=M.symbolic_port1_only_rmw(seeded(),True)
        self.assertEqual(after[(1,3)]&1,1)

    def test_port1_id4_inverted_bit0_last_action_set(self):
        after,ops=M.symbolic_port1_only_rmw(seeded(),False)
        self.assertEqual(ops[0],(4,0,0))
        self.assertEqual(ops[-1],(4,0,1))
        self.assertEqual(after[(1,4)]&1,1)

    def test_port1_id2_preserves_all_other_bits(self):
        values=seeded()
        after,_=M.symbolic_port1_only_rmw(values,True)
        self.assertEqual(
            (after[(1,2)] ^ values[(1,2)])&~((1<<8)|(1<<20)),0)

    def test_protected_port0_storage_unchanged(self):
        values=seeded()
        after,_=M.symbolic_port1_only_rmw(values,True)
        for k in (2,3,4,5):
            self.assertEqual(values[(0,k)],after[(0,k)])

    def test_protected_port2_baseband_unchanged(self):
        values=seeded()
        after,_=M.symbolic_port1_only_rmw(values,True)
        for k in (2,3,4,5):
            self.assertEqual(values[(2,k)],after[(2,k)])

    def test_protected_port3_unchanged(self):
        values=seeded()
        after,_=M.symbolic_port1_only_rmw(values,True)
        for k in (2,3,4,5):
            self.assertEqual(values[(3,k)],after[(3,k)])

    def test_fake_global_shared_status_is_never_written(self):
        values=seeded()
        for enabled in (False,True):
            after,_=M.symbolic_port1_only_rmw(values,enabled)
            self.assertEqual(set(after),set(values))
            self.assertTrue(all(port in (0,1,2,3) for port,_ in after))
            self.assertNotIn((1,1),after)

    def test_1000_randomized_synthetic_port0_and_port2_isolation(self):
        randomizer=random.Random(20261112)
        for _ in range(1000):
            v={(port,k):randomizer.getrandbits(32)
               for port in range(4) for k in (2,3,4,5)}
            output,_=M.symbolic_port1_only_rmw(v,bool(randomizer.randrange(2)))
            self.assertEqual({x:y for x,y in output.items() if x[0]!=1},
                             {x:y for x,y in v.items() if x[0]!=1})

    def test_reject_missing_register_key(self):
        x=seeded();x.pop((0,2))
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.symbolic_port1_only_rmw(x,True)

    def test_reject_unexpected_register(self):
        x=seeded();x[(9,2)]=0
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.symbolic_port1_only_rmw(x,True)

    def test_reject_nonsensical_register_width(self):
        x=seeded();x[(1,4)]=1<<40
        with self.assertRaises(M.OriginalRootControlNotQualified):
            M.symbolic_port1_only_rmw(x,True)

    def test_reject_missing_bool_optional_gate(self):
        for flag in (0,1,None,"yes"):
            with self.subTest(flag=flag):
                with self.assertRaises(M.OriginalRootControlNotQualified):
                    M.symbolic_port1_only_rmw(seeded(),flag)

    def test_source_does_not_operate_phone_or_print_private_sources(self):
        src=PATH.read_text()
        for danger in ("insmod","modprobe","devmem","ioremap",
                       "setpci","writel(","dd if=","flash_erase",
                       "print(original)","print(adt)","print(blobs)"):
            self.assertNotIn(danger,src)
        self.assertIn("N71_SAFE_PCIE_MMIO_DART_DMA_NATIVE_WIFI_AUTHORIZED=NO",src)
        self.assertIn("N71_ORIGINAL_POLL_TIMEOUT_IN_CALLER_PROVEN=NO",src)

if __name__=="__main__":unittest.main()
