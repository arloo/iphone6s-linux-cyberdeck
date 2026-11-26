# SPDX-License-Identifier: MIT
"""Original NXSB observer: independent Fletcher oracle and actual helper syscalls."""
from pathlib import Path
import ctypes as C
import random
import struct
import subprocess
import tempfile
import unittest
from test_n71_s3e_ro_probe import HELPER
ROOT=Path(__file__).resolve().parents[1]

class Result(C.Structure):
    _fields_=[(k,C.c_uint) for k in ['magic_ok','checksum_ok','object_header_ok','geometry_ok','checkpoint_ranges_ok','omap_present','omap_reference_ok','block_size','max_volume_slots','used_volume_slots','desc_blocks','data_blocks']]+[(k,C.c_ulonglong) for k in ['container_blocks','desc_base','data_base','omap_block']]

def checksum(p):
    # Closed-form weighted word sum is independent of the C running-sums loop.
    words=struct.unpack('<1022I',p[8:]);mod=(1<<32)-1
    a=sum(words)%mod;b=sum((len(words)-i)*x for i,x in enumerate(words))%mod
    lo=mod-(a+b)%mod;hi=mod-(a+lo)%mod
    return lo|(hi<<32)

def stamp(p):
    struct.pack_into('<Q',p,0,checksum(p))

def fixture():
    p=bytearray(4096);struct.pack_into('<QQII',p,8,1,77,0x80000001,0)
    p[32:36]=b'NXSB';struct.pack_into('<IQ',p,36,4096,512)
    struct.pack_into('<Q',p,64,2);p[72:88]=bytes(range(1,17))
    struct.pack_into('<QQ',p,88,1024,78)
    struct.pack_into('<IIQQ',p,104,16,32,1,17)
    struct.pack_into('<QQQII',p,152,1<<58,100,1<<59,0,8)
    struct.pack_into('<QQ',p,184,1<<55,1<<56)
    stamp(p);return p

class APFSTests(unittest.TestCase):
    def compile_run(self,source):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'case.c').write_text(source)
            result=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'experimental/port0'),'-I',str(ROOT),str(d/'case.c'),'-o',str(d/'case')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(d/'case')],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();d=Path(cls.tmp.name)
        (d/'case.c').write_text('#include "n71-apfs-superblock-core.h"\nint parse(const unsigned char *p,unsigned b,unsigned long long n,struct n71_apfs_superblock_result *o){return n71_apfs_superblock_parse(p,b,n,o);}\nunsigned long long csum(const unsigned char *p,unsigned n){return n71_apfs_fletcher64(p,n);}\n')
        q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(d/'case.c'),'-o',str(d/'case.so')],text=True,capture_output=True)
        if q.returncode:raise AssertionError(q.stderr)
        cls.lib=C.CDLL(str(d/'case.so'));cls.lib.parse.argtypes=[C.c_void_p,C.c_uint,C.c_ulonglong,C.POINTER(Result)];cls.lib.parse.restype=C.c_int;cls.lib.csum.argtypes=[C.c_void_p,C.c_uint];cls.lib.csum.restype=C.c_ulonglong
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def parse(self,p,blocks=1000,bytes_=4096):
        buf=C.create_string_buffer(bytes(p));before=buf.raw;o=Result();C.memset(C.byref(o),0xa5,C.sizeof(o));rc=self.lib.parse(buf,bytes_,blocks,C.byref(o));self.assertEqual(buf.raw,before)
        if rc:self.assertEqual(bytes(o),bytes(C.sizeof(o)))
        return rc,o
    def test_real_checksum_known_vectors_and_random_weighted_oracle(self):
        p=bytearray(4096);self.assertEqual(self.lib.csum(C.create_string_buffer(bytes(p)),4096),0xffffffffffffffff)
        struct.pack_into('<I',p,8,1);self.assertEqual(self.lib.csum(C.create_string_buffer(bytes(p)),4096),0x000003fefffffc00)
        p=bytearray(4096);struct.pack_into('<I',p,4092,1);self.assertEqual(self.lib.csum(C.create_string_buffer(bytes(p)),4096),0x00000001fffffffd)
        rng=random.Random(7138000)
        for _ in range(24):
            p=bytearray(rng.randbytes(4096));self.assertEqual(self.lib.csum(C.create_string_buffer(bytes(p)),4096),checksum(p))
        self.assertEqual(self.lib.csum(None,4096),0)
    def test_valid_anchor_bounded_physical_references_and_large_nonphysical_ids(self):
        rc,o=self.parse(fixture());self.assertEqual(rc,0)
        self.assertEqual((o.magic_ok,o.checksum_ok,o.object_header_ok,o.geometry_ok,o.checkpoint_ranges_ok),(1,1,1,1,1))
        self.assertEqual((o.container_blocks,o.desc_base,o.desc_blocks,o.data_base,o.data_blocks,o.omap_block),(512,1,16,17,32,100))
        self.assertEqual((o.block_size,o.max_volume_slots,o.used_volume_slots),(4096,8,2))
    def test_corrupt_payload_and_every_stored_checksum_bit_fail(self):
        p=fixture()
        for i in [8,24,40,72,104,180,512,2048,4095]:
            bad=bytearray(p);bad[i]^=1;self.assertEqual(self.parse(bad)[0],-4)
        for bit in range(64):
            bad=bytearray(p);bad[bit//8]^=1<<(bit%8);self.assertEqual(self.parse(bad)[0],-4)
    def test_object_magic_size_type_and_partition_geometry_are_fail_closed(self):
        cases=[(32,0,'I',-2),(36,8192,'I',-3),(8,2,'Q',-5),(16,0,'Q',-5),(24,0x40000001,'I',-5),(28,1,'I',-5),(40,0,'Q',-6),(40,1001,'Q',-6),(40,255,'Q',-6),(180,0,'I',-6),(180,101,'I',-6)]
        for off,val,fmt,want in cases:
            p=fixture();struct.pack_into('<'+fmt,p,off,val);stamp(p);self.assertEqual(self.parse(p)[0],want,(off,val))
        for n in [0,1,15625001,(1<<64)-1]:self.assertEqual(self.parse(fixture(),n)[0],-1)
        for size in [0,512,4095,4097]:self.assertEqual(self.parse(fixture(),bytes_=size)[0],-1)
        o=Result();self.assertEqual(self.lib.parse(None,4096,1000,C.byref(o)),-1)
    def test_unsupported_version_fusion_and_checkpoint_trees_are_not_claimed_supported(self):
        for val in [0,1,3,0x102,1<<63]:
            p=fixture();struct.pack_into('<Q',p,64,val);stamp(p);self.assertEqual(self.parse(p)[0],-7)
        for off in [104,108]:
            p=fixture();struct.pack_into('<I',p,off,0x80000010);stamp(p);self.assertEqual(self.parse(p)[0],-8)
    def test_checkpoint_ranges_overlap_overflow_and_optional_physical_omap(self):
        for off,val,fmt in [(104,0,'I'),(108,0,'I'),(112,0,'Q'),(120,512,'Q'),(112,(1<<64)-1,'Q'),(104,513,'I'),(120,16,'Q')]:
            p=fixture();struct.pack_into('<'+fmt,p,off,val);stamp(p);self.assertEqual(self.parse(p)[0],-9)
        p=fixture();struct.pack_into('<Q',p,160,512);stamp(p);self.assertEqual(self.parse(p)[0],-10)
        p=fixture();struct.pack_into('<Q',p,160,0);stamp(p);rc,o=self.parse(p);self.assertEqual((rc,o.omap_present,o.omap_reference_ok),(0,0,0))
    def test_block_zero_checkpoint_cursors_are_ignored_and_volume_ids_are_not_addresses(self):
        p=fixture()
        for off in range(128,152,4):struct.pack_into('<I',p,off,0xffffffff)
        stamp(p);self.assertEqual(self.parse(p)[0],0)
        for off,val in [(192,1<<55),(184+8*8,999)]:
            p=fixture();struct.pack_into('<Q',p,off,val);stamp(p);self.assertEqual(self.parse(p)[0],-6)
    def test_explicit_apfs_argument_admission_never_touches_a_device(self):
        self.compile_run(r'''
#define main helper_main
#include "experimental/storage/n71-nand-private-probe.c"
#undef main
#include <assert.h>
int main(void){unsigned b;unsigned long long n;char *a[]={"probe","--apfs","4000","4999",0};
 assert(!select_apfs(4,a,&b,&n)&&b==4000&&n==1000);
 {const char *bad[]={"","-1","+6"," 6","5","15624999","18446744073709551616","6x"};unsigned i;
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++){a[2]=(char *)bad[i];assert(select_apfs(4,a,&b,&n)==-1);}}
 a[2]="15624998";a[3]="15624999";assert(!select_apfs(4,a,&b,&n)&&n==2);
 a[3]="15624998";assert(select_apfs(4,a,&b,&n)==-1);
 a[2]="6";a[3]="15625000";assert(select_apfs(4,a,&b,&n)==-1);return 0;}
''')
    def helper_source(self):
        p=fixture();arrays='static unsigned char fixture_header[4096]={'+','.join(str(x) for x in p)+'};\n'
        s=HELPER.replace('static ssize_t fake_pread(',arrays+'static ssize_t fake_pread(').replace('if(unsafe)return 0;errno=ENOENT;return -1;','if(unsafe){return 0;}\n errno=ENOENT;return -1;')
        s=s.replace('memset(out,(step&1U)?0x31:0x17,4096);','if(step&1U)memset(out,0x31,4096);else memcpy(out,fixture_header,4096);')
        return s[:s.index('int main(void) {')]
    def test_actual_helper_apfs_summary_private_references_and_cleanup(self):
        s=self.helper_source()+r'''
int main(void){char *a[]={"probe","--apfs","4000","4999",0};base=4000;
 assert(!helper_main(4,a));assert(reads==6&&opened==2&&created==1&&unlinked==1&&closed==1);
 fixture_header[72]^=1;opened=reads=created=unlinked=closed=0;
 assert(helper_main(4,a)==1);assert(reads==6&&unlinked==1&&closed==1);return 0;}
'''
        output=self.compile_run(s)
        self.assertEqual(output.count('APFS_SUPERBLOCK_PASS '),1)
        self.assertEqual(output.count('PRIVATE_APFS_REFS '),1)
        self.assertIn('latest_checkpoint_selected=0 filesystem_mounted=0',output)
        for private in [bytes(range(1,17)).hex(),str(1<<55),str(1<<56),str(1<<58),str(1<<59),'checksum_value=','fletcher64=']:
            self.assertNotIn(private,output)
    def test_actual_helper_each_failed_or_short_read_stops_without_retry(self):
        s=self.helper_source().replace('if(fail_at==step+1){errno=EIO;return -1;}','if(fail_at==step+1){errno=EIO;return -1;}if(fail_at==5&&step==1)return 2048;')+r'''
int main(void){char *a[]={"probe","--apfs","4000","4999",0};unsigned j;
 for(j=1;j<=5;j++){base=4000;opened=reads=created=unlinked=closed=0;fail_at=j;
 assert(helper_main(4,a)==1);assert(opened==2&&created==1&&unlinked==1&&closed==1);
 assert(reads==(j==5?4:2+j));}return 0;}
'''
        self.compile_run(s)
