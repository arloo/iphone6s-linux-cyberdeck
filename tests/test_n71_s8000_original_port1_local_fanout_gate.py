"""Adversarial original Apple S8000 port-instance fanout, OFFLINE only."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import random
import struct
import sys
import unittest
from unittest.mock import patch

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_original_port1_local_fanout_gate.py"
SP=importlib.util.spec_from_file_location("n71_a9_port_local",SRC)
assert SP and SP.loader
A=importlib.util.module_from_spec(SP)
sys.modules[SP.name]=A
SP.loader.exec_module(A)

def fake_source():
    shared=bytearray(18552)
    for off,value in A.SHARED_WORDS.items():
        struct.pack_into("<I",shared,off,value)
    return shared

def bank(seed=23):
    return {(p,i):((seed*0x1f2135)^(p<<22)^(i<<17)^(p*i))&0xffffffff
            for p in range(4) for i in (2,3,4,5)}

class TestN71OriginalPortLocalFanout(unittest.TestCase):
    def test_original_shared_code_match(self):
        self.assertTrue(A.check_words(bytes(fake_source())))

    def test_every_pinned_arm64_opcode_mutation_refused(self):
        for offset in A.SHARED_WORDS:
            with self.subTest(offset=offset):
                src=fake_source()
                src[offset]^=1
                with self.assertRaises(A.UnqualifiedPortFanout):
                    A.check_words(bytes(src))

    def test_unexpected_original_source_size_rejected(self):
        with self.assertRaises(A.UnqualifiedPortFanout):
            A.check_words(bytes(fake_source())[:-4])

    def test_original_port_instance_target_count(self):
        self.assertEqual(len(A.EXPECTED_PORT_METHODS),8)
        self.assertEqual(tuple(sorted(A.EXPECTED_PORT_METHODS)),
                         (1504,1528,1568,1848,1864,2000,2008,2016))

    def test_original_root_target_count(self):
        self.assertEqual(len(A.EXPECTED_ROOT_DISPATCH),3)

    def test_port1_original_dispatch_first_100us_bit0_set(self):
        original=bank()
        after=A.model_followed_port1_effects(original,False)
        self.assertEqual(after[1,2]&1,1)
        self.assertEqual(after[1,3],original[1,3])

    def test_later_conditional_port1848_id3_bit8_cleared(self):
        original=bank()
        after=A.model_followed_port1_effects(original,True)
        self.assertEqual(after[1,3]&0x100,0)

    def test_port1_id2_preserves_every_non_bit0_bit(self):
        v=bank()
        a=A.model_followed_port1_effects(v,False)
        self.assertEqual((a[1,2]^v[1,2])&~1,0)

    def test_port1_id3_preserves_every_non_bit8_bit(self):
        v=bank()
        a=A.model_followed_port1_effects(v,True)
        self.assertEqual((a[1,3]^v[1,3])&~0x100,0)

    def test_all_storage_port0_fake_state_preserved(self):
        v=bank()
        for branch in (False,True):
            a=A.model_followed_port1_effects(v,branch)
            self.assertTrue(all(a[0,i]==v[0,i] for i in (2,3,4,5)))

    def test_all_baseband_port2_fake_state_preserved(self):
        v=bank()
        for branch in (False,True):
            a=A.model_followed_port1_effects(v,branch)
            self.assertTrue(all(a[2,i]==v[2,i] for i in (2,3,4,5)))

    def test_all_unknown_port3_fake_state_preserved(self):
        v=bank()
        for branch in (False,True):
            a=A.model_followed_port1_effects(v,branch)
            self.assertTrue(all(a[3,i]==v[3,i] for i in (2,3,4,5)))

    def test_one_thousand_deterministic_fake_register_vectors(self):
        rng=random.Random(20261112)
        for _ in range(1000):
            v={(p,i):rng.getrandbits(32) for p in range(4)
               for i in (2,3,4,5)}
            after=A.model_followed_port1_effects(v,bool(rng.getrandbits(1)))
            self.assertEqual({k:x for k,x in after.items() if k[0]!=1},
                             {k:x for k,x in v.items() if k[0]!=1})

    def test_missing_storage_port_slot_rejected(self):
        v=bank()
        v.pop((0,2))
        with self.assertRaises(A.UnqualifiedPortFanout):
            A.model_followed_port1_effects(v,True)

    def test_forbidden_extra_synthetic_global_shared_register_rejected(self):
        v=bank()
        v[(0,1)]=0
        with self.assertRaises(A.UnqualifiedPortFanout):
            A.model_followed_port1_effects(v,False)

    def test_bad_width_malformed_register_rejected(self):
        v=bank()
        v[(1,3)]=1<<48
        with self.assertRaises(A.UnqualifiedPortFanout):
            A.model_followed_port1_effects(v,False)

    def test_bad_negative_register_rejected(self):
        v=bank()
        v[(1,2)]=-1
        with self.assertRaises(A.UnqualifiedPortFanout):
            A.model_followed_port1_effects(v,False)

    def test_non_boolean_conditional_rejected(self):
        for value in (0,1,2,None,"yes"):
            with self.subTest(value=value):
                with self.assertRaises(A.UnqualifiedPortFanout):
                    A.model_followed_port1_effects(bank(),value)

    def test_offline_gate_disallows_shared_root_write_as_safe(self):
        source=SRC.read_text()
        self.assertIn("N71_ROOT_COMMON_0X4060_REGISTER_WRITE_AUTHORIZED=NO",source)
        self.assertIn("N71_NATIVE_WIFI_PCIE_DMA_MMIO_TEST_AUTHORIZED=NO",source)

    def test_all_real_port_root_bit_selector_offsets(self):
        self.assertEqual(A.KNOWN_PORT1_ROOT_SELECTOR_OFFSETS,
         {"ID2_PORT1_BIT0":0x180,"ID3_PORT1_BIT8":0x194,
          "PORT_SCOPED_WRITE_3_RELATIVE":0x4060})

    def test_static_gate_has_no_iphone_or_hardware_call(self):
        src=SRC.read_text()
        for name in ("insmod","modprobe","rmmod","devmem",
                     "writel(","ioremap(","setpci",
                     "flash_erase","dd if=","iw dev ","ip link set"):
            self.assertNotIn(name,src)

if __name__=="__main__":unittest.main()
