"""Execute real portable C N71/S8000 PCIe shared-status model on synthetic snapshots.

No Apple or iPhone binary data, actual registers, devices, paths, firmware
or private material are accessed by the compiled program.
"""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"examples/n71-pcie-port1/port1_shared_status_snapshot_model.c"


class Resource(C.Structure):
    _fields_=[("port",C.c_uint32),("provider_index",C.c_uint32),
              ("offset",C.c_uint32),("base",C.c_uint64),
              ("length",C.c_uint64)]


class Result(C.Structure):
    _fields_=[("examined",C.c_uint32),("last_value",C.c_uint32),
              ("bit4_observed",C.c_uint32)]


class TestSharedStatusSnapshottedC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="n71-port1-shared-offline-")
        cls.addClassCleanup(cls.tmp.cleanup)
        target=Path(cls.tmp.name)/"shared_status_model.so"
        compiler=shutil.which("gcc")
        if compiler is None:
            raise RuntimeError("A native C compiler is required for real-C safety tests")
        subprocess.run([compiler,"-std=c11","-Wall","-Wextra","-Werror",
                        "-O2","-fPIC","-shared",str(SRC),"-o",str(target)],
                       check=True,capture_output=True,timeout=15)
        lib=C.CDLL(str(target))
        lib.n71_port1_check_shared_snapshots.argtypes=[
            C.POINTER(Resource), C.POINTER(C.c_uint32), C.c_size_t,
            C.POINTER(Result)]
        lib.n71_port1_check_shared_snapshots.restype=C.c_int
        lib.n71_port1_shared_snapshot_authorizes_hardware.argtypes=[]
        lib.n71_port1_shared_snapshot_authorizes_hardware.restype=C.c_int
        cls.lib=lib

    @staticmethod
    def resource(**values):
        fields=dict(port=1,provider_index=9,offset=0x2c,
                    base=0x600000000,length=0x8000)
        fields.update(values)
        return Resource(**fields)

    def sample(self,values,resource=None,amount=None):
        values=list(values)
        array=(C.c_uint32*max(1,len(values)))(*values)
        state=Result(55,99,88)
        obj=resource if resource is not None else self.resource()
        code=self.lib.n71_port1_check_shared_snapshots(
            C.byref(obj),array,len(values) if amount is None else amount,
            C.byref(state))
        return code,state

    def test_bit4_direct_match(self):
        status,state=self.sample([0x10])
        self.assertEqual(status,0)
        self.assertEqual((state.examined,state.last_value,state.bit4_observed),
                         (1,0x10,1))

    def test_zero_not_ready(self):
        status,state=self.sample([0,0,0])
        self.assertEqual(status,-110)  # ETIMEDOUT on Linux
        self.assertEqual((state.examined,state.last_value,state.bit4_observed),
                         (3,0,0))

    def test_bit0_not_equivalent_to_bit4(self):
        status,state=self.sample([1,2,4,8,0x1000,0x80000000])
        self.assertEqual(status,-110)
        self.assertEqual(state.bit4_observed,0)

    def test_bit4_with_unrelated_bits(self):
        status,state=self.sample([0xFFFFFFEF,0xFFFFFFFF])
        self.assertEqual(status,0)
        self.assertEqual(state.examined,2)

    def test_stops_at_first_bit4(self):
        status,state=self.sample([0x200,0x10,0,0x10])
        self.assertEqual(status,0)
        self.assertEqual(state.examined,2)

    def test_accepts_max_count(self):
        status,state=self.sample([0]*4095+[0x10])
        self.assertEqual(status,0)
        self.assertEqual(state.examined,4096)

    def test_over_limit_rejected(self):
        status,state=self.sample([0x10],amount=4097)
        self.assertEqual(status,-22)  # EINVAL
        self.assertEqual(tuple(state.__getattribute__(k) for k in
                         ("examined","last_value","bit4_observed")),(0,0,0))

    def test_empty_rejected(self):
        status,_=self.sample([])
        self.assertEqual(status,-22)

    def test_only_port1(self):
        for p in (0,2,3,9):
            with self.subTest(port=p):
                self.assertEqual(self.sample([0x10],self.resource(port=p))[0],
                                 -22)

    def test_only_correct_provider_index(self):
        for index in (0,1,2,8,10,11):
            with self.subTest(index=index):
                self.assertEqual(self.sample([0x10],self.resource(
                    provider_index=index))[0],-22)

    def test_shared_register_only_not_port1_register(self):
        for offset in (0,0x24,0x180,0x194,0x1a4,0x1ac,0x30):
            with self.subTest(offset=offset):
                self.assertEqual(self.sample([0x10],self.resource(
                    offset=offset))[0],-22)

    def test_only_proven_original_physical_base(self):
        for base in (0,0x602000000,0x601000000,0x600008000,0x600000004):
            with self.subTest(base=base):
                self.assertEqual(self.sample([0x10],self.resource(base=base))[0],
                                 -22)

    def test_length_including_overflow_rejected(self):
        for length in (0,0x4000,0x7ffc,0x10000,2**64-1):
            with self.subTest(length=length):
                self.assertEqual(self.sample([0x10],self.resource(
                    length=length))[0],-22)

    def test_result_null_is_rejected(self):
        data=(C.c_uint32*1)(16)
        self.assertEqual(self.lib.n71_port1_check_shared_snapshots(
            C.byref(self.resource()),data,1,None),-22)

    def test_null_resource_is_rejected(self):
        data=(C.c_uint32*1)(16)
        state=Result(1,2,3)
        self.assertEqual(self.lib.n71_port1_check_shared_snapshots(
            None,data,1,C.byref(state)),-22)
        self.assertEqual((state.examined,state.last_value,state.bit4_observed),
                         (0,0,0))

    def test_null_data_is_rejected(self):
        state=Result(1,2,3)
        self.assertEqual(self.lib.n71_port1_check_shared_snapshots(
            C.byref(self.resource()),None,1,C.byref(state)),-22)
        self.assertEqual(state.bit4_observed,0)

    def test_no_hardware_authorization_even_after_success(self):
        self.assertEqual(self.sample([0x10])[0],0)
        self.assertEqual(self.lib.n71_port1_shared_snapshot_authorizes_hardware(),0)

    def test_all_32_individual_bits_against_actual_c(self):
        for bit in range(32):
            with self.subTest(bit=bit):
                status,state=self.sample([1<<bit])
                self.assertEqual(status,0 if bit==4 else -110)
                self.assertEqual(state.bit4_observed,1 if bit==4 else 0)

    def test_50000_synthetic_mask_vectors(self):
        # Fixed deterministic vectors, not radio/per-device or private data.
        for n in range(50000):
            value=((n*0x9E3779B1) ^ (n>>3))&0xffffffff
            rc,state=self.sample([value])
            self.assertEqual(rc,0 if value&0x10 else -110)
            self.assertEqual(state.last_value,value)

    def test_source_cannot_access_mmio_or_network(self):
        src=SRC.read_text()
        for forbidden in ("ioremap(", "readl(", "writel(", "mmap(",
                          "open(", "ioctl(", "socket(", "fork(", "system(",
                          "usb", "/dev/mem", "popen(", "dlsym("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,src.lower())

    def test_original_provenance_is_explicit(self):
        src=SRC.read_text()
        for text in ("0x600000000","0x8000","0x2c","4096U",
                     "N71_COMMON_RESOURCE_INDEX", "NEVER permission"):
            self.assertIn(text,src)


if __name__=="__main__":
    unittest.main()
