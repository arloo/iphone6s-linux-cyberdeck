# SPDX-License-Identifier: MIT
"""Pure classifier faults; no phone, firmware, filesystem or kernel memory."""
from pathlib import Path
import ctypes as C
import re
import struct
import subprocess
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
class Result(C.Structure):
    _fields_=[(k,C.c_uint) for k in ['mbr_signature','protective_mbr','gpt_signature','gpt_crc_ok','gpt_geometry_ok','gpt_primary_header_ok']]+[(k,C.c_uint*2) for k in ['apfs_container_signature','apfs_volume_signature','all_zero','all_ff']]+[('different_sectors',C.c_uint)]
class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();d=Path(cls.tmp.name)
        (d/'test.c').write_text('#include "n71-retained-layout-core.h"\nint run(const unsigned char *a,const unsigned char *b,unsigned n,unsigned long long z,struct n71_layout_result *o){return n71_layout_classify(a,b,n,z,o);}\nint inside(unsigned long long a,unsigned long long n,unsigned long long b,unsigned long long s){return n71_cpu_range_inside(a,n,b,s);}\n')
        p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(d/'test.c'),'-o',str(d/'test.so')],text=True,capture_output=True)
        if p.returncode:raise AssertionError(p.stderr)
        cls.lib=C.CDLL(str(d/'test.so'));cls.lib.run.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.c_ulonglong,C.POINTER(Result)];cls.lib.run.restype=C.c_int
        cls.lib.inside.argtypes=[C.c_ulonglong]*4;cls.lib.inside.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_layout(self,a,b):
        aa=C.create_string_buffer(bytes(a));bb=C.create_string_buffer(bytes(b));before=(aa.raw,bb.raw);o=Result()
        self.assertEqual(self.lib.run(aa,bb,4096,15625000,C.byref(o)),0)
        self.assertEqual((aa.raw,bb.raw),before)
        return o
    def gpt(self):
        a=bytearray(4096);b=bytearray(4096);a[510:512]=b'\x55\xaa';a[450]=0xee;struct.pack_into('<I',a,454,1)
        b[:8]=b'EFI PART';struct.pack_into('<II',b,8,0x10000,92)
        struct.pack_into('<QQQQ',b,24,1,15624999,6,15624994)
        struct.pack_into('<QII',b,72,2,128,128);self.crc(b)
        return a,b
    @staticmethod
    def crc(b):
        struct.pack_into('<I',b,16,0);n=struct.unpack_from('<I',b,12)[0]
        if 92<=n<=4096:struct.pack_into('<I',b,16,zlib.crc32(b[:n]))
    def test_independent_crc_gpt_header_and_input_immutability(self):
        a,b=self.gpt();o=self.run_layout(a,b)
        for k in ['mbr_signature','protective_mbr','gpt_signature','gpt_crc_ok','gpt_geometry_ok','gpt_primary_header_ok','different_sectors']:self.assertEqual(getattr(o,k),1,k)
        self.assertEqual(list(o.all_zero),[0,0])
    def test_all_header_bit_corruptions_fail_crc_or_signature(self):
        a,b=self.gpt()
        for bit in range(92*8):
            bad=bytearray(b);bad[bit//8]^=1<<(bit%8);o=self.run_layout(a,bad)
            self.assertFalse(o.gpt_primary_header_ok,bit)
    def test_malformed_geometry_with_recomputed_crc(self):
        a,b=self.gpt()
        cases=[(8,'I',0),(12,'I',0),(12,'I',91),(12,'I',4097),(12,'I',0xffffffff),(20,'I',1),(24,'Q',0),(32,'Q',15625000),(40,'Q',2),(40,'Q',15624995),(48,'Q',15624999),(72,'Q',0),(72,'Q',0xffffffffffffffff),(80,'I',0),(80,'I',4097),(80,'I',0xffffffff),(84,'I',0),(84,'I',127),(84,'I',256),(84,'I',0xffffffff)]
        for off,fmt,val in cases:
            bad=bytearray(b);struct.pack_into('<'+fmt,bad,off,val);self.crc(bad);o=self.run_layout(a,bad)
            self.assertFalse(o.gpt_primary_header_ok,(off,val))
    def test_unknown_zero_ff_and_signature_hints_are_not_gpt(self):
        z=bytearray(4096);f=bytearray(b'\xff'*4096)
        o=self.run_layout(z,z);self.assertEqual(list(o.all_zero),[1,1]);self.assertFalse(o.different_sectors)
        o=self.run_layout(z,f);self.assertEqual(list(o.all_ff),[0,1]);self.assertTrue(o.different_sectors)
        a=bytearray(z);b=bytearray(z);a[32:36]=b'NXSB';b[32:36]=b'APSB';o=self.run_layout(a,b)
        self.assertEqual(list(o.apfs_container_signature),[1,0]);self.assertEqual(list(o.apfs_volume_signature),[0,1]);self.assertFalse(o.gpt_primary_header_ok)
    def test_bad_arguments_and_overflow_safe_owner_ranges(self):
        a,b=self.gpt();aa=C.create_string_buffer(bytes(a));bb=C.create_string_buffer(bytes(b));o=Result();C.memset(C.byref(o),0x5a,C.sizeof(o));old=bytes(o)
        for n,z in [(4095,15625000),(4097,15625000),(4096,0),(4096,15624999)]:
            self.assertEqual(self.lib.run(aa,bb,n,z,C.byref(o)),-1);self.assertEqual(bytes(o),old)
        self.assertEqual(self.lib.run(None,bb,4096,15625000,C.byref(o)),-1)
        M=(1<<64)-1
        for a,n,b,s,ok in [(100,1,100,16,1),(115,1,100,16,1),(116,1,100,16,0),(100,17,100,16,0),(99,1,100,16,0),(100,0,100,16,0),(M,1,M,1,1),(M,1,M,2,0),(0,1,0,1,0)]:self.assertEqual(self.lib.inside(a,n,b,s),ok)
    def test_exact_owner_field_mirror_and_no_hardware_or_payload_operations(self):
        owner=(ROOT/'experimental/port0/n71_s3e_ro_block_runtime.h').read_text();observer=(ROOT/'experimental/storage/n71-retained-layout-ro.c').read_text()
        a=owner[owner.index('static struct {')+len('static struct {'):owner.index('} n71_ro_block_memory;')]
        b=observer[observer.index('struct n71_retained_owner {')+len('struct n71_retained_owner {'):observer.index('};',observer.index('struct n71_retained_owner {'))]
        normalize=lambda s:re.sub(r'\s+','',re.sub(r'/\*.*?\*/','',s,flags=re.S))
        self.assertEqual(normalize(a),normalize(b))
        for bad in ['ioremap(', 'readl(', 'writel(', 'dma_map', 'dma_unmap', 'module_put(', 'print_hex_dump', 'filp_open(', 'register_blkdev(', 'copy_to_user(']:self.assertNotIn(bad,observer)
        self.assertIn('sizeof(struct n71_retained_owner)!=176',observer);self.assertIn('offsetof(struct n71_retained_owner,target)!=48',observer)
        self.assertLess(observer.index('!owner_hash_attested'),observer.index('copy_from_kernel_nofault(meta'))
        self.assertIn('memzero_explicit(copies,8*PAGE_SIZE)',observer)
        self.assertIn('memcmp(&before,&after,sizeof(before))',observer)
