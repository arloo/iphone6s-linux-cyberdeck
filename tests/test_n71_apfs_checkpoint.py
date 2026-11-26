# SPDX-License-Identifier: MIT
"""Single retained APFS descriptor; synthetic CPU fixtures, no device I/O."""
from pathlib import Path
import ctypes as C
import re
import struct
import subprocess
import tempfile
import unittest
import test_n71_apfs_superblock as af
ROOT=Path(__file__).resolve().parents[1]
FIELDS="anchor_valid all_zero all_ff checksum_ok kind object_header_ok inside_anchor_descriptor_area descriptor_shape_valid same_container_uuid candidate_geometry_ok candidate_ring_ok mapping_count mapping_last mapping_flags_ok mapping_bounds_ok mappings_ephemeral mappings_inside_anchor_data transaction_newer_than_anchor transaction_equal_anchor".split()
class Result(C.Structure):
    _fields_=[(k,C.c_uint) for k in FIELDS]
def mapping():
    p=bytearray(4096);struct.pack_into('<QQIIII',p,8,1,100,0x4000000c,0,1,2)
    struct.pack_into('<IIIIQQQ',p,40,0x80000005,0,4096,0xfeedface,0,1<<58,20)
    struct.pack_into('<IIIIQQQ',p,80,0x80000003,0,2048,0,1<<55,1<<57,40)
    af.stamp(p);return p
def nxsb():
    p=af.fixture();struct.pack_into('<Q',p,16,100)
    struct.pack_into('<IIIIII',p,128,2,2,0,2,0,2);af.stamp(p);return p
class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();d=Path(cls.tmp.name)
        (d/'case.c').write_text('#include "n71-apfs-checkpoint-core.h"\nint observe(const unsigned char *a,const unsigned char *p,unsigned n,unsigned long long z,unsigned long long b,struct n71_apfs_checkpoint_result *o){return n71_apfs_checkpoint_observe(a,p,n,z,b,o);}\nint ring(unsigned i,unsigned n,unsigned s,unsigned a){return n71_apfs_ring_contains(i,n,s,a);}')
        q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(d/'case.c'),'-o',str(d/'case.so')],text=True,capture_output=True)
        if q.returncode:raise AssertionError(q.stderr)
        cls.lib=C.CDLL(str(d/'case.so'));cls.lib.observe.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.c_ulonglong,C.c_ulonglong,C.POINTER(Result)];cls.lib.observe.restype=C.c_int
        cls.lib.ring.argtypes=[C.c_uint]*4;cls.lib.ring.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def observe(self,p,anchor=None,n=4096,part=1000,block=1):
        a=C.create_string_buffer(bytes(af.fixture() if anchor is None else anchor));b=C.create_string_buffer(bytes(p));before=(a.raw,b.raw);o=Result();C.memset(C.byref(o),0xa5,C.sizeof(o))
        rc=self.lib.observe(a,b,n,part,block,C.byref(o));self.assertEqual((a.raw,b.raw),before)
        if rc:self.assertEqual(bytes(o),bytes(C.sizeof(o)))
        return rc,o
    def test_mapping_checksum_header_extent_and_large_ids(self):
        rc,o=self.observe(mapping());self.assertEqual(rc,0)
        for k in ['anchor_valid','checksum_ok','object_header_ok','inside_anchor_descriptor_area','descriptor_shape_valid','mapping_last','mapping_flags_ok','mapping_bounds_ok','mappings_ephemeral','mappings_inside_anchor_data','transaction_newer_than_anchor']:self.assertEqual(getattr(o,k),1,k)
        self.assertEqual((o.kind,o.mapping_count,o.transaction_equal_anchor),(2,2,0))
    def test_map_faults_with_recomputed_checksums(self):
        cases=[(36,'I',102),(32,'I',2),(8,'Q',2),(16,'Q',0),(24,'I',0x8000000c),(28,'I',1),(48,'I',0),(64,'Q',0),(72,'Q',512),(72,'Q',(1<<64)-1),(40,'I',0x40000005),(40,'I',0x80000000),(48,'I',0xffffffff)]
        for off,fmt,val in cases:
            p=mapping();struct.pack_into('<'+fmt,p,off,val);af.stamp(p);rc,o=self.observe(p)
            self.assertEqual(rc,0);self.assertFalse(o.descriptor_shape_valid,(off,val))
        p=mapping();struct.pack_into('<Q',p,72,100);af.stamp(p);rc,o=self.observe(p)
        self.assertTrue(o.descriptor_shape_valid);self.assertFalse(o.mappings_inside_anchor_data)
        p=mapping();struct.pack_into('<Q',p,16,77);af.stamp(p);o=self.observe(p)[1]
        self.assertEqual((o.transaction_newer_than_anchor,o.transaction_equal_anchor),(0,1))
    def test_zero_ff_unknown_and_corruption_are_observations(self):
        for p,zero,ff in [(bytearray(4096),1,0),(bytearray(b'\xff'*4096),0,1)]:
            rc,o=self.observe(p);self.assertEqual((rc,o.all_zero,o.all_ff,o.descriptor_shape_valid),(0,zero,ff,0))
        p=mapping();p[300]^=1;o=self.observe(p)[1];self.assertFalse(o.checksum_ok or o.descriptor_shape_valid)
        p=bytearray(4096);struct.pack_into('<QQII',p,8,1,100,0x40000002,0);af.stamp(p);o=self.observe(p)[1]
        self.assertTrue(o.checksum_ok);self.assertEqual((o.kind,o.descriptor_shape_valid),(0,0))
    def test_nxsb_candidate_requires_uuid_geometry_and_ring(self):
        rc,o=self.observe(nxsb());self.assertEqual(rc,0)
        self.assertEqual((o.kind,o.checksum_ok,o.object_header_ok,o.same_container_uuid,o.candidate_geometry_ok,o.candidate_ring_ok,o.descriptor_shape_valid,o.transaction_newer_than_anchor),(1,1,1,1,1,1,1,1))
        for off,fmt,val in [(72,'B',255),(128,'I',16),(132,'I',32),(136,'I',16),(140,'I',0),(140,'I',17),(144,'I',32),(148,'I',0),(148,'I',33),(40,'Q',1001)]:
            p=nxsb();struct.pack_into('<'+fmt,p,off,val);af.stamp(p);self.assertFalse(self.observe(p)[1].descriptor_shape_valid,(off,val))
        p=nxsb();struct.pack_into('<IIII',p,136,15,2,31,2);af.stamp(p);self.assertTrue(self.observe(p)[1].descriptor_shape_valid)
    def test_anchor_membership_and_bad_arguments(self):
        p=mapping();struct.pack_into('<Q',p,8,20);af.stamp(p);o=self.observe(p,block=20)[1]
        self.assertTrue(o.object_header_ok);self.assertFalse(o.inside_anchor_descriptor_area or o.descriptor_shape_valid)
        for n,part,block in [(4095,1000,1),(4097,1000,1),(4096,0,1),(4096,1000,512),(4096,1000,(1<<64)-1)]:self.assertEqual(self.observe(p,n=n,part=part,block=block)[0],-1)
        a=af.fixture();a[72]^=1;self.assertEqual(self.observe(p,anchor=a)[0],-1)
        o=Result();b=C.create_string_buffer(bytes(p));a=C.create_string_buffer(bytes(af.fixture()))
        self.assertEqual(self.lib.observe(None,b,4096,1000,1,C.byref(o)),-1)
        self.assertEqual(self.lib.observe(a,None,4096,1000,1,C.byref(o)),-1)
        self.assertEqual(self.lib.observe(a,b,4096,1000,1,None),-1)
    def test_ring_matches_independent_enumerated_model(self):
        for slots in range(1,18):
            for index in range(slots):
                for length in range(1,slots+1):
                    members={(index+i)%slots for i in range(length)}
                    for at in range(slots):self.assertEqual(self.lib.ring(index,length,slots,at),int(at in members))
        for args in [(0,0,4,0),(4,1,4,0),(0,5,4,0),(0,1,0,0),(0,1,4,4)]:self.assertEqual(self.lib.ring(*args),0)
        self.assertEqual(self.lib.ring(0xfffffffe,2,0xffffffff,0),1)
        self.assertEqual(self.lib.ring(0xfffffffe,1,0xffffffff,0),0)
    def test_exact_owner_abi_and_cpu_only_guarded_observer(self):
        s=(ROOT/'experimental/storage/n71-retained-apfs-checkpoint-ro.c').read_text();owner=(ROOT/'experimental/port0/n71_s3e_ro_block_runtime.h').read_text()
        a=owner[owner.index('static struct {')+len('static struct {'):owner.index('} n71_ro_block_memory;')]
        b=s[s.index('struct n71_retained_owner {')+len('struct n71_retained_owner {'):s.index('};',s.index('struct n71_retained_owner {'))]
        a=subprocess.check_output(['cc','-E','-P','-x','c','-'],input='#define N71_GPT_FULL_PLAN 0\n#define N71_READ_SERIES_COUNT 4\n'+a,text=True)
        normalize=lambda x:re.sub(r'\s+','',re.sub(r'/\*.*?\*/','',x,flags=re.S))
        self.assertEqual(normalize(a),normalize(b))
        for bad in ['ioremap(', 'readl(', 'writel(', 'dma_map', 'dma_unmap', 'module_put(', 'print_hex_dump', 'filp_open(', 'register_blkdev(', 'copy_to_user(', '%px','%pK','%llx','%llu']:self.assertNotIn(bad,s)
        self.assertIn('if(!armed)',s);self.assertIn('sizeof(struct n71_retained_owner)!=176',s);self.assertIn('offsetof(struct n71_retained_owner,target)!=48',s)
        self.assertLess(s.index('!owner_hash_attested'),s.index('copy_from_kernel_nofault(meta'))
        self.assertLess(s.index('!is_vmalloc_or_module_addr('),s.index('vmalloc_to_page('))
        self.assertIn('memcmp(&before,&after,sizeof(before))',s);self.assertIn('memzero_explicit(copies,8*PAGE_SIZE)',s)
        self.assertIn('latest_checkpoint_selected=0 complete_scan=0',s)
    def test_result_schema_contains_only_flags_and_count(self):
        self.assertEqual(C.sizeof(Result),19*4)
        header=(ROOT/'experimental/storage/n71-apfs-checkpoint-core.h').read_text()
        body=header[header.index('struct n71_apfs_checkpoint_result {'):header.index('};')]
        for forbidden in ['long long','uuid[','checksum_value','paddr','oid;','xid;']:self.assertNotIn(forbidden,body)
