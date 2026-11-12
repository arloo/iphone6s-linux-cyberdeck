"""Execute the actual C A9/S8000 83-record offline Apple tunable RMW model.

All records in this public test are SYNTHETIC. Neither private Apple
tuning bytes nor real phone/network/firmware information is used.
"""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"examples/n71-pcie-port1/port1_original_tunable_replay_model.c"

class Tunable(C.Structure):
    _fields_=[("offset",C.c_uint32),("width",C.c_uint32),
              ("mask",C.c_uint64),("value",C.c_uint64)]

class Result(C.Structure):
    _fields_=[("examined",C.c_uint32),
              ("synthetic_changes",C.c_uint32),
              ("synthetic_unchanged",C.c_uint32),
              ("protected_status_offset_reached",C.c_uint32),
              ("physical_hardware_authorized",C.c_uint32)]

EXPECTED={0:34,1:41,2:6,3:2}

def synthetic(bank,offset=0x100):
    count=EXPECTED[bank]
    # Non-private data, intentionally unrelated to genuine Apple masks.
    return [Tunable(offset+4*i,4,0xff,(i*3)&0xff)
            for i in range(count)]

class TestN71Apple83ReplayModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory(prefix="n71-pcie-replay-only-")
        cls.addClassCleanup(tmp.cleanup)
        gcc=shutil.which("gcc")
        if not gcc:raise RuntimeError("gcc required to execute actual C")
        object_path=Path(tmp.name)/"n71_replay.so"
        subprocess.run([gcc,"-std=c11","-Wall","-Wextra","-Werror",
                        "-O2","-fPIC","-shared",str(SOURCE),"-o",
                        str(object_path)],capture_output=True,text=True,
                        check=True,timeout=20)
        library=C.CDLL(str(object_path))
        library.n71_s8000_replay_original_tunables.argtypes=[
            C.c_uint,C.POINTER(Tunable),C.c_size_t,
            C.c_uint32,C.POINTER(Result)]
        library.n71_s8000_replay_original_tunables.restype=C.c_int
        library.n71_s8000_replay_authorizes_pcie_mmio_or_dma.argtypes=[]
        library.n71_s8000_replay_authorizes_pcie_mmio_or_dma.restype=C.c_int
        cls.lib=library

    def attempt(self,bank,records=None,seed=0x12345678,
                amount=None,arr_null=False,res_null=False):
        if records is None:records=synthetic(bank)
        arr=(Tunable*max(1,len(records)))(*records)
        result=Result(333,333,333,333,333)
        rc=self.lib.n71_s8000_replay_original_tunables(
            bank,None if arr_null else arr,
            len(records) if amount is None else amount,
            seed,None if res_null else C.byref(result))
        return rc,result

    def test_all_four_banks_sum_to_83(self):
        total=0
        for bank,count in EXPECTED.items():
            with self.subTest(bank=bank):
                code,res=self.attempt(bank)
                self.assertEqual(code,0)
                self.assertEqual(res.examined,count)
                self.assertEqual(res.synthetic_changes+
                                 res.synthetic_unchanged,count)
                self.assertEqual(res.physical_hardware_authorized,0)
                total+=res.examined
        self.assertEqual(total,83)

    def test_no_physical_hardware_authorization_after_replay(self):
        self.assertEqual(self.attempt(2)[0],0)
        self.assertEqual(
            self.lib.n71_s8000_replay_authorizes_pcie_mmio_or_dma(),0)

    def test_unknown_bank_rejected(self):
        for bank in (4,17,255,2**32-1):
            with self.subTest(bank=bank):
                self.assertEqual(self.attempt(bank,synthetic(2))[0],-22)

    def test_count_must_match_original_apple_block(self):
        for bank in EXPECTED:
            with self.subTest(bank=bank):
                records=synthetic(bank)
                self.assertEqual(self.attempt(bank,records[:-1])[0],-22)
                self.assertEqual(self.attempt(bank,records+[records[0]])[0],
                                 -22)

    def test_reject_null_record_ptr(self):
        self.assertEqual(self.attempt(2,arr_null=True)[0],-22)

    def test_reject_null_result_ptr(self):
        self.assertEqual(self.attempt(2,res_null=True)[0],-22)

    def test_reject_zero_expected_record_count(self):
        self.assertEqual(self.attempt(2,amount=0)[0],-22)

    def test_reject_declared_count_above_83(self):
        self.assertEqual(self.attempt(2,amount=90)[0],-22)

    def mutated(self,bank,field,value,idx=0):
        arr=synthetic(bank)
        setattr(arr[idx],field,value)
        return self.attempt(bank,arr)

    def test_reject_width_8(self):
        self.assertEqual(self.mutated(2,"width",8)[0],-34)

    def test_reject_width_zero(self):
        self.assertEqual(self.mutated(2,"width",0)[0],-34)

    def test_reject_unaligned_offset(self):
        self.assertEqual(self.mutated(2,"offset",0x101)[0],-34)

    def test_reject_out_of_bank_offset(self):
        for bank,offset in ((0,0x8000),(1,0x4000),(2,0x4000),(3,0x4000)):
            with self.subTest(bank=bank):
                self.assertEqual(self.mutated(bank,"offset",offset)[0],-34)

    def test_reject_high_64bit_mask(self):
        self.assertEqual(self.mutated(2,"mask",0x100000000)[0],-34)

    def test_reject_high_64bit_value(self):
        self.assertEqual(self.mutated(2,"value",0x100000000)[0],-34)

    def test_reject_value_bits_not_covered_by_mask(self):
        arr=synthetic(2);arr[0].mask=1;arr[0].value=2
        self.assertEqual(self.attempt(2,arr)[0],-34)

    def test_reject_same_offset_in_same_bank(self):
        for bank in EXPECTED:
            arr=synthetic(bank)
            arr[-1].offset=arr[0].offset
            with self.subTest(bank=bank):
                self.assertEqual(self.attempt(bank,arr)[0],-17)

    def test_reject_shared_status_offset_write(self):
        self.assertEqual(self.mutated(0,"offset",0x2c)[0],-1)

    def test_root_common_not_equated_to_port1(self):
        arr=synthetic(0)
        self.assertNotEqual(self.attempt(2,arr)[0],0)

    def test_no_early_partial_results_on_bad_last_record(self):
        arr=synthetic(0);arr[-1].width=8
        code,result=self.attempt(0,arr)
        self.assertNotEqual(code,0)
        self.assertEqual((result.examined,result.synthetic_changes,
                          result.synthetic_unchanged,
                          result.physical_hardware_authorized),(0,0,0,0))

    def test_zero_masks_apply_no_changes(self):
        arr=[Tunable(0x100+i*4,4,0,0) for i in range(6)]
        code,res=self.attempt(2,arr)
        self.assertEqual(code,0)
        self.assertEqual(res.synthetic_changes,0)
        self.assertEqual(res.synthetic_unchanged,6)

    def test_zero_mask_nonzero_value_rejected(self):
        arr=[Tunable(0x100+i*4,4,0,0) for i in range(6)]
        arr[1].value=1
        self.assertEqual(self.attempt(2,arr)[0],-34)

    def test_all_register_bits_preserved_when_not_masked(self):
        for bit in range(32):
            arr=[Tunable(0x100+i*4,4,1<<bit,0) for i in range(6)]
            code,res=self.attempt(2,arr,seed=bit)
            with self.subTest(bit=bit):
                self.assertEqual(code,0)
                self.assertEqual(res.examined,6)

    def test_50000_reproducible_synthetic_seed_vectors(self):
        arr=synthetic(3)
        for seed in range(50000):
            code,res=self.attempt(3,arr,seed=seed*0x9e3779b1)
            self.assertEqual(code,0)
            self.assertEqual(res.synthetic_changes+
                             res.synthetic_unchanged,2)
            self.assertEqual(res.physical_hardware_authorized,0)

    def test_hardware_effect_free_source(self):
        src=SOURCE.read_text().lower()
        for forbidden in ("ioremap(", "readl(", "writel(", "mmap(",
                          "ioctl(", "socket(", "open(", "/dev/mem",
                          "usb", "popen(", "system(", "kallsyms"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,src)

    def test_physical_hardware_access_is_never_granted(self):
        src=SOURCE.read_text()
        self.assertIn("n71_s8000_replay_authorizes_pcie_mmio_or_dma",src)
        self.assertIn("return 0;",src)

if __name__=="__main__":
    unittest.main()
