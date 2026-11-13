"""Adversarial *offline* S5L8960X DART IOVA and packed TCR lock tests.

Pure synthetic arithmetic and synthetic ELF headers. Does not import a
kernel module, access a device or cause a DART MMIO write.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import random
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s5l8960x_dart_window_tcr_offline_gate.py"
spec=importlib.util.spec_from_file_location("n71_s5l_offline_guard",SRC)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

class TestN71S5L8960xIsolatedDart(unittest.TestCase):
    def test_stock_a9_dma_window_accept(self):
        self.assertTrue(M.legacy_window_allowed(0x80000000,0xBBFFFFFF))
    def test_stock_a9_dma_window_page_end_accept(self):
        self.assertTrue(M.legacy_window_allowed(0x80000000,0xBFFFF000))
    def test_unaligned_window_rejected(self):
        self.assertFalse(M.legacy_window_allowed(0x90000000,0xCFFFF000))
    def test_zero_base_not_rejected_for_alignment(self):
        self.assertTrue(M.legacy_window_allowed(0,0x3FFFF000))
    def test_exact_boundary_rejected_not_off_by_one(self):
        for base in (0x1000,0x10000,0x80000000,0xC0000000):
            with self.subTest(base=base):
                span=base&-base
                self.assertTrue(M.legacy_window_allowed(base,base+span-1))
                self.assertFalse(M.legacy_window_allowed(base,base+span))
    def test_bad_window_args_fail_closed(self):
        for base,end in ((-1,0),(5,4),(0,1<<64),(1<<65,1<<65),
                         (True,100),(0,None),(0,3.0)):
            with self.subTest(base=base,end=end):
                with self.assertRaises(M.UnqualifiedDartPatch):
                    M.legacy_window_allowed(base,end)
    def test_each_packed_tcr_lane_isolated(self):
        old=0xA1B2C3D4
        for sid in range(4):
            with self.subTest(sid=sid):
                new=M.packed_tcr_assign(old,sid,0x80)
                mask=0xff<<(8*sid)
                self.assertEqual(new&~mask,old&~mask)
                self.assertEqual((new>>8*sid)&255,128)
    def test_fifty_thousand_randomized_tcr_register_assignments(self):
        rnd=random.Random(20261113)
        for _ in range(50_000):
            old=rnd.getrandbits(32)
            sid=rnd.randrange(4)
            value=rnd.randrange(256)
            result=M.packed_tcr_assign(old,sid,value)
            self.assertEqual((result>>(8*sid))&255,value)
            for other_sid in range(4):
                if other_sid!=sid:
                    self.assertEqual((result>>(8*other_sid))&255,
                                     (old>>(8*other_sid))&255)
    def test_bad_tcr_parameters_rejected(self):
        for word,sid,value in ((-1,1,0),(1<<33,2,0),(0,-1,0),
                               (0,4,0),(0,1,-1),(0,1,256),
                               (0,True,1),(0,0,1.0)):
            with self.subTest(word=word,sid=sid,value=value):
                with self.assertRaises(M.UnqualifiedDartPatch):
                    M.packed_tcr_assign(word,sid,value)
    def test_legitimate_arm64_elf_relocatable_accepted(self):
        b=bytearray(2048)
        b[:6]=b"\x7fELF\x02\x01"
        struct.pack_into("<HH",b,16,1,183)
        self.assertTrue(M.real_arm64_relocatable(bytes(b)))
    def test_host_x86_object_rejected(self):
        b=bytearray(2048);b[:6]=b"\x7fELF\x02\x01"
        struct.pack_into("<HH",b,16,1,62)
        with self.assertRaises(M.UnqualifiedDartPatch):
            M.real_arm64_relocatable(bytes(b))
    def test_not_a_kernel_elf_rejected(self):
        with self.assertRaises(M.UnqualifiedDartPatch):
            M.real_arm64_relocatable(b"faked")
    def test_public_patch_four_scoped_hunks_only(self):
        src=M.PATCH.read_text()
        self.assertEqual(src.count("\n@@ "),4)
        self.assertIn("spinlock_t tcr_lock;",src)
        self.assertIn("spin_lock_init(&dart->tcr_lock);",src)
        self.assertIn("cfg->dma_max - cfg->dma_min >=",src)
        self.assertIn("goto done;",src)
    def test_patch_contains_no_new_hardware_activation(self):
        lines=[l for l in M.PATCH.read_text().splitlines()
               if l.startswith("+") and not l.startswith("+++")]
        added="\n".join(lines)
        for action in ("ioremap","writel(","apple_dart_hw_reset(",
                       "insmod","modprobe","devmem","gpio_set_value",
                       "pm_runtime_get","pci_host_probe"):
            self.assertNotIn(action,added)
        self.assertIn("N71_ALL_STREAM_RESET_ISOLATION_PROVEN=NO",SRC.read_text())
    def test_proven_compiled_object_cannot_prove_wifi_link(self):
        src=SRC.read_text()
        self.assertIn("N71_PHYSICAL_PCIE_DART1_SID_DMA_WIFI_TEST_AUTHORIZED=NO",src)
        self.assertIn("N71_PHONE_ORIGINAL_BOOT_AND_NAND_UNMODIFIED=YES",src)

if __name__=="__main__":
    unittest.main()
