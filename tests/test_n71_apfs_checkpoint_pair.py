# SPDX-License-Identifier: MIT
"""Real paired descriptor parser/helper; synthetic objects and mocked syscalls."""
from pathlib import Path
import ctypes as C
import struct
import subprocess
import tempfile
import unittest
import test_n71_apfs_superblock as af
import test_n71_s3e_ro_probe as probe
ROOT=Path(__file__).resolve().parents[1]
FIELDS="nxsb_valid checksum_pair_ok object_headers_ok same_transaction descriptor_ring_ok descriptor_pair_complete data_ring_ok mapping_count mapping_extents_in_data_window mapping_keys_unique mapping_extents_nonoverlap spaceman_mapping_present reaper_mapping_present omap_reference_present volume_slot_count max_volume_slots".split()
class Result(C.Structure):
    _fields_=[(k,C.c_uint) for k in FIELDS]
class Refs(C.Structure):
    _fields_=[(k,C.c_ulonglong) for k in ['container_blocks','desc_base','data_base','omap_block','spaceman_block','reaper_block']]+[(k,C.c_uint) for k in ['desc_blocks','data_blocks','spaceman_blocks','reaper_blocks']]
TX=0x123456789abcdef0
def fixture():
    nx=af.fixture();struct.pack_into('<Q',nx,16,TX);struct.pack_into('<Q',nx,96,TX+1)
    struct.pack_into('<IIIIII',nx,128,2,0,0,2,0,32);af.stamp(nx)
    m=bytearray(4096);struct.pack_into('<QQIIII',m,8,1,TX,0x4000000c,0,1,3)
    struct.pack_into('<IIIIQQQ',m,40,0x80000005,0,8192,0xfeedface,0,1<<58,20)
    struct.pack_into('<IIIIQQQ',m,80,0x80000011,0,4096,0,0,1<<59,40)
    struct.pack_into('<IIIIQQQ',m,120,0x80000003,0,2048,0,1<<55,1<<57,44)
    af.stamp(m);return m,nx
class CheckpointPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();d=Path(cls.tmp.name)
        (d/'case.c').write_text('#include "n71-apfs-checkpoint-pair-core.h"\nint parse(const unsigned char *m,const unsigned char *n,unsigned b,unsigned long long p,unsigned long long r,struct n71_apfs_checkpoint_pair_result *o,struct n71_apfs_checkpoint_pair_refs *f){return n71_apfs_checkpoint_pair_parse(m,n,b,p,r,o,f);}\nint extent(unsigned i,unsigned l,unsigned s,unsigned a,unsigned n){return n71_apfs_ring_extent(i,l,s,a,n);}')
        q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(d/'case.c'),'-o',str(d/'case.so')],text=True,capture_output=True)
        if q.returncode:raise AssertionError(q.stderr)
        cls.lib=C.CDLL(str(d/'case.so'));cls.lib.parse.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.c_ulonglong,C.c_ulonglong,C.POINTER(Result),C.POINTER(Refs)];cls.lib.parse.restype=C.c_int;cls.lib.extent.argtypes=[C.c_uint]*5;cls.lib.extent.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def parse(self,m,n,part=1000,relative=1,bytes_=4096):
        a=C.create_string_buffer(bytes(m));b=C.create_string_buffer(bytes(n));before=(a.raw,b.raw);o=Result();p=Refs();C.memset(C.byref(o),0xa5,C.sizeof(o));C.memset(C.byref(p),0xa5,C.sizeof(p))
        rc=self.lib.parse(a,b,bytes_,part,relative,C.byref(o),C.byref(p));self.assertEqual((a.raw,b.raw),before)
        if rc:self.assertEqual((bytes(o),bytes(p)),(bytes(C.sizeof(o)),bytes(C.sizeof(p))))
        return rc,o,p
    def compile_run(self,s):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'case.c').write_text(s)
            q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'experimental/port0'),'-I',str(ROOT),str(d/'case.c'),'-o',str(d/'case')],text=True,capture_output=True);self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(d/'case')],text=True,capture_output=True,timeout=5);self.assertEqual(q.returncode,0,q.stderr);return q
    def test_valid_complete_descriptor_pair_and_private_references(self):
        rc,o,p=self.parse(*fixture());self.assertEqual(rc,0)
        for k in FIELDS:
            if k not in ['mapping_count','volume_slot_count','max_volume_slots']:self.assertEqual(getattr(o,k),1,k)
        self.assertEqual((o.mapping_count,o.volume_slot_count,o.max_volume_slots),(3,2,8))
        self.assertEqual((p.container_blocks,p.spaceman_block,p.spaceman_blocks,p.reaper_block,p.reaper_blocks),(512,20,2,40,1))
    def test_checksums_and_transaction_equality_are_independent(self):
        m,n=fixture()
        for target in range(2):
            for off in [0,8,16,24,72,500,4095]:
                pair=[bytearray(m),bytearray(n)];pair[target][off]^=1;self.assertNotEqual(self.parse(*pair)[0],0)
        struct.pack_into('<Q',m,16,TX-1);af.stamp(m);self.assertEqual(self.parse(m,n)[0],-5)
    def test_headers_and_supported_geometry_fail_closed(self):
        for target,off,fmt,value in [(1,32,'I',0),(1,8,'Q',2),(1,24,'I',0x40000001),(1,28,'I',1),(1,36,'I',8192),(1,64,'Q',0x102),(1,40,'Q',1001),(0,8,'Q',2),(0,24,'I',0x8000000c),(0,28,'I',1),(0,36,'I',102)]:
            pair=[bytearray(x) for x in fixture()];struct.pack_into('<'+fmt,pair[target],off,value);af.stamp(pair[target]);self.assertNotEqual(self.parse(*pair)[0],0,(target,off,value))
    def test_descriptor_and_data_ring_cursor_limits_and_last_flag(self):
        for off,value in [(128,16),(132,32),(136,16),(140,0),(140,3),(144,32),(148,0),(148,33)]:
            m,n=fixture();struct.pack_into('<I',n,off,value);af.stamp(n);self.assertNotEqual(self.parse(m,n)[0],0,(off,value))
        m,n=fixture();struct.pack_into('<I',m,32,0);af.stamp(m);self.assertEqual(self.parse(m,n)[0],-6)
        m,n=fixture();struct.pack_into('<II',n,136,15,2);af.stamp(n);self.assertEqual(self.parse(m,n)[0],-6)
    def test_mapping_data_window_and_wrapped_window(self):
        m,n=fixture();struct.pack_into('<II',n,144,2,24);af.stamp(n);self.assertEqual(self.parse(m,n)[0],-7)
        m,n=fixture();struct.pack_into('<II',n,144,31,9);struct.pack_into('<Q',m,112,17);struct.pack_into('<Q',m,152,23);af.stamp(m);af.stamp(n);self.assertEqual(self.parse(m,n)[0],0)
        for off,fmt,value in [(48,'I',0),(48,'I',0xffffffff),(72,'Q',512),(72,'Q',(1<<64)-1),(72,'Q',16),(72,'Q',48)]:
            m,n=fixture();struct.pack_into('<'+fmt,m,off,value);af.stamp(m);self.assertNotEqual(self.parse(m,n)[0],0,(off,value))
    def test_duplicate_keys_and_overlapping_extents_but_large_ids_are_not_addresses(self):
        m,n=fixture();struct.pack_into('<QQ',m,136,0,1<<58);af.stamp(m);self.assertEqual(self.parse(m,n)[0],-8)
        m,n=fixture();struct.pack_into('<Q',m,144,1<<58);af.stamp(m);self.assertEqual(self.parse(m,n)[0],0)
        m,n=fixture();struct.pack_into('<Q',m,112,21);af.stamp(m);self.assertEqual(self.parse(m,n)[0],-8)
    def test_required_container_links_and_preserved_padding(self):
        for target,off,fmt,value in [(0,40,'I',0x80000003),(0,44,'I',1),(0,56,'Q',1<<55),(1,152,'Q',0),(1,152,'Q',1<<57),(1,168,'Q',1<<57)]:
            pair=[bytearray(x) for x in fixture()];struct.pack_into('<'+fmt,pair[target],off,value);af.stamp(pair[target]);self.assertEqual(self.parse(*pair)[0],-9,(target,off,value))
        m,n=fixture();struct.pack_into('<Q',n,168,0);af.stamp(n);rc,o,p=self.parse(m,n);self.assertEqual((rc,o.reaper_mapping_present,p.reaper_block),(0,0,0))
        m,n=fixture();struct.pack_into('<I',m,52,0xffffffff);af.stamp(m);self.assertEqual(self.parse(m,n)[0],0)
    def test_ring_extent_matches_independent_block_set_model(self):
        for slots in range(1,12):
            for index in range(slots):
                for length in range(1,slots+1):
                    members={(index+j)%slots for j in range(length)}
                    for at in range(slots):
                        for count in range(1,slots-at+1):self.assertEqual(self.lib.extent(index,length,slots,at,count),int(set(range(at,at+count))<=members))
        for args in [(0,0,4,0,1),(4,1,4,0,1),(0,5,4,0,1),(0,1,0,0,1),(0,4,4,4,1),(0,4,4,3,2),(0,4,4,0,0)]:self.assertEqual(self.lib.extent(*args),0)
        self.assertEqual(self.lib.extent(0xfffffffe,2,0xffffffff,0,1),1)
        self.assertEqual(self.lib.extent(0xfffffffe,1,0xffffffff,0,1),0)
    def test_bad_arguments_clear_both_result_objects(self):
        m,n=fixture()
        for b,z,r in [(4095,1000,1),(4097,1000,1),(4096,0,1),(4096,15625001,1),(4096,1000,0),(4096,1000,999),(4096,1000,(1<<64)-1)]:self.assertEqual(self.parse(m,n,part=z,relative=r,bytes_=b)[0],-1)
        a=C.create_string_buffer(bytes(m));b=C.create_string_buffer(bytes(n));o=Result();p=Refs()
        for aa,bb,oo,pp in [(None,b,C.byref(o),C.byref(p)),(a,None,C.byref(o),C.byref(p)),(a,b,None,C.byref(p)),(a,b,C.byref(o),None)]:self.assertEqual(self.lib.parse(aa,bb,4096,1000,1,oo,pp),-1)
    def test_explicit_strict_argument_bounds_before_device_access(self):
        self.compile_run(r'''#define main helper_main
#include "experimental/storage/n71-nand-private-probe.c"
#undef main
#include <assert.h>
int main(void){unsigned b;unsigned long long n,r;char *a[]={"probe","--checkpoint","4000","4999","1",0};
 assert(!select_checkpoint(5,a,&b,&n,&r)&&b==4001&&n==1000&&r==1);
 {const char *bad[]={"","0","-1","+1"," 1","999","1000","18446744073709551615","18446744073709551616","1x"};unsigned i;
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++){a[4]=(char *)bad[i];assert(select_checkpoint(5,a,&b,&n,&r)==-1);}}
 a[4]="998";assert(!select_checkpoint(5,a,&b,&n,&r)&&b==4998);a[4]="1";a[2]="5";assert(select_checkpoint(5,a,&b,&n,&r)==-1);
 a[2]="15624997";a[3]="15624999";assert(!select_checkpoint(5,a,&b,&n,&r)&&b==15624998);a[3]="15625000";assert(select_checkpoint(5,a,&b,&n,&r)==-1);return 0;}''')
    def helper_source(self):
        m,n=fixture();arrays='static unsigned char map_fixture[4096]={'+','.join(map(str,m))+'};\nstatic unsigned char nx_fixture[4096]={'+','.join(map(str,n))+'};\n'
        s=probe.HELPER.replace('static ssize_t fake_pread(',arrays+'static ssize_t fake_pread(',1).replace('if(unsafe)return 0;errno=ENOENT;return -1;','if(unsafe){return 0;}\n errno=ENOENT;return -1;',1).replace('memset(out,(step&1U)?0x31:0x17,4096);','memcpy(out,(step&1U)?nx_fixture:map_fixture,4096);',1)
        return s[:s.index('int main(void) {')]
    def test_actual_helper_pair_result_private_refs_and_output_privacy(self):
        q=self.compile_run(self.helper_source()+r'''
int main(void){char *a[]={"probe","--checkpoint","4000","4999","1",0};base=4001;
 assert(!helper_main(5,a));assert(reads==6&&opened==2&&created==1&&unlinked==1&&closed==1);return 0;}
''');self.assertEqual(q.stdout.count('APFS_CHECKPOINT_PAIR_PASS '),1);self.assertEqual(q.stdout.count('PRIVATE_CHECKPOINT_REFS '),1)
        self.assertIn('same_transaction=1',q.stdout);self.assertIn('block_zero_UUID_compared=0 complete_scan=0 latest_checkpoint_selected=0 checkpoint_data_objects_read=0 filesystem_mounted=0',q.stdout)
        for value in [str(TX),str(1<<55),str(1<<57),str(1<<58),str(1<<59),bytes(range(1,17)).hex(),'checksum_value=','fletcher64=','UUID=','xid=','oid=']:self.assertNotIn(value,q.stdout)
    def test_actual_helper_failed_short_reads_and_metadata_failure_stop_and_clean(self):
        s=self.helper_source().replace('if(fail_at==step+1){errno=EIO;return -1;}','if(fail_at==step+1){errno=EIO;return -1;}if(fail_at==5&&step==1)return 2048;',1)+r'''
int main(void){char *a[]={"probe","--checkpoint","4000","4999","1",0};unsigned j;
 for(j=1;j<=5;j++){base=4001;opened=reads=created=unlinked=closed=0;fail_at=j;assert(helper_main(5,a)==1);assert(opened==2&&created==1&&unlinked==1&&closed==1);assert(reads==(j==5?4:2+j));}
 base=4001;opened=reads=created=unlinked=closed=0;fail_at=0;nx_fixture[72]^=1;assert(helper_main(5,a)==1);assert(reads==6&&unlinked==1&&closed==1);return 0;}
'''
        q=self.compile_run(s);self.assertNotIn('APFS_CHECKPOINT_PAIR_PASS ',q.stdout);self.assertIn('APFS_CHECKPOINT_PAIR_FAILED',q.stderr)
