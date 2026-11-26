# SPDX-License-Identifier: MIT
"""Broader bound pair still uses four retained commands; GPT prefix is private."""
from pathlib import Path
import ctypes as C
import struct
import subprocess
import tempfile
import unittest
import uuid
import zlib
from test_n71_s3e_read_series import CORE, PORT
from test_n71_s3e_ro_block import MODEL
from test_n71_s3e_ro_probe import HELPER
ROOT=Path(__file__).resolve().parents[1]
class PairTests(unittest.TestCase):
    def compile_run(self,s):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'test.c').write_text(s)
            q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(PORT),'-I',str(ROOT),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=5);self.assertEqual(q.returncode,0,q.stderr)
    def test_nonendpoint_pairs_run_actual_command_corruption_and_failure_matrix(self):
        macros=r"""
#define n71_read_series_command(b,s,l,n,z,f) n71_read_pair_command(b,s,l,n,z,f,TEST_BASE)
#define n71_read_series_command_valid(b,s,l,n,z,f) n71_read_pair_command_valid(b,s,l,n,z,f,TEST_BASE)
#define n71_read_series_core(o,c,l,n,z,f,r) n71_read_pair_core(o,c,l,n,z,f,r,TEST_BASE)
"""
        for base in [1,2,3,65535,15624997]:
            s=CORE.replace('#include "n71_s3e_read_series_core.h"','#include "n71_s3e_read_series_core.h"\n#define TEST_BASE '+str(base)+'U\n'+macros)
            s=s.replace('==(step&1)&&','==(TEST_BASE+(step&1))&&').replace('&&i!=40)','&&!(i>=40&&i<48))')
            self.compile_run(s)
    def test_nonendpoint_pair_runs_actual_bio_exhaustion_and_rejection_matrix(self):
        macros=r"""
#define n71_ro_block_admissible(f,r) n71_ro_block_pair_admissible(f,r,1U)
#define n71_ro_block_admit(f,r) n71_ro_block_pair_admit(f,r,1U)
"""
        s=MODEL.replace('#include "n71_s3e_ro_block_core.h"','#include "n71_s3e_ro_block_core.h"'+macros).replace('8ULL*(step&1)','8ULL*(1U+(step&1))')
        self.compile_run(s)
    def test_explicit_pair_mode_exhaustive_gate_and_pre_hardware_integration(self):
        self.compile_run(r"""
#include <assert.h>
#include "n71_s3e_ro_block_core.h"
int main(void){unsigned enabled,b,block,tail;unsigned bases[]={~0U,0,1,2,15624998,15624999};
 for(enabled=0;enabled<2;enabled++)for(b=0;b<6;b++)for(block=0;block<2;block++)for(tail=0;tail<2;tail++) {
 int want=enabled?(block&&!tail&&bases[b]<=15624998U):(bases[b]==~0U);
 assert(!!n71_ro_block_pair_mode_valid(enabled,bases[b],block,tail)==want);
 }return 0;}
""")
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text();init=s[s.index('static int __init n71_port0_init'):]
        self.assertIn('static bool ans_ro_block_pair_once;',s)
        self.assertIn('static unsigned int ans_ro_block_pair_base=~0U;',s)
        self.assertLess(init.index('n71_ro_block_pair_mode_valid('),init.index('n71_board_gate()'))
    def test_actual_helper_layout_mode_real_parser_and_private_summary(self):
        h,p=GPTPrefixTests().fixture(32)
        arrays='static unsigned char fixture_header[4096]={'+','.join(str(x) for x in h)+'};\nstatic unsigned char fixture_entries[4096]={'+','.join(str(x) for x in p)+'};\n'
        s=HELPER.replace('static ssize_t fake_pread(',arrays+'static ssize_t fake_pread(').replace('if(unsafe)return 0;errno=ENOENT;return -1;', 'if(unsafe){return 0;}\n errno=ENOENT;return -1;')
        s=s.replace('memset(out,(step&1U)?0x31:0x17,4096);','memcpy(out,(step&1U)?fixture_entries:fixture_header,4096);')
        a=s.index('int main(void) {');s=s[:a]+r"""
int main(void) {
 char *args[]={"probe","--layout",NULL};unsigned j;
 for(j=0;j<2;j++) {
  base=1;opened=reads=created=unlinked=closed=0;fail_at=corrupt=unsafe=regular=0;
  if(j)fixture_header[16]^=1;
  assert(helper_main(2,args)==(j?1:0));
  assert(reads==6&&opened==2&&created==1&&unlinked==1&&closed==1);
 }
 return 0;
}
"""
        self.compile_run(s)
    def test_actual_helper_argument_selection_without_device_access(self):
        self.compile_run(r"""
#define main helper_main
#include "experimental/storage/n71-nand-private-probe.c"
#undef main
#include <assert.h>
int main(void){unsigned b=0;int l=0;char *a[]={"probe","--pair","1",NULL};
 assert(!select_pair(3,a,&b,&l)&&b==1&&!l);
 a[2]="15624998";assert(!select_pair(3,a,&b,&l)&&b==15624998U);
 {const char *bad[]={"","-1","+1"," 1","15624999","4294967296","18446744073709551616","1x"};unsigned i;
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++){a[2]=(char *)bad[i];assert(select_pair(3,a,&b,&l)==-1);}}
 a[1]="--layout";assert(!select_pair(2,a,&b,&l)&&b==1&&l);
 a[1]="--initial";assert(!select_pair(2,a,&b,&l)&&b==0&&!l);
 return 0;}
""")
class Range(C.Structure):
    _fields_=[('slot',C.c_uint),('apfs_type',C.c_uint),('first',C.c_ulonglong),('last',C.c_ulonglong)]
class Prefix(C.Structure):
    _fields_=[(n,C.c_uint) for n in ['declared','checked','used','apfs_type_count','array_complete','array_crc_checked','array_crc_ok']]+[('ranges',Range*32)]
class GPTPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name)
        (p/'test.c').write_text('#include "n71-gpt-prefix-core.h"\nint run(const unsigned char *h,const unsigned char *p,unsigned n,struct n71_gpt_prefix_result *o){return n71_gpt_prefix_parse(h,p,n,o);}\n')
        q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(p/'test.c'),'-o',str(p/'test.so')],text=True,capture_output=True)
        if q.returncode:raise AssertionError(q.stderr)
        cls.lib=C.CDLL(str(p/'test.so'));cls.lib.run.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.POINTER(Prefix)];cls.lib.run.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def fixture(self,count=32):
        h=bytearray(4096);full=bytearray(count*128);h[:8]=b'EFI PART';struct.pack_into('<II',h,8,0x10000,92)
        first=2+(len(full)+4095)//4096;struct.pack_into('<QQQQ',h,24,1,15624999,first,15624990);struct.pack_into('<QII',h,72,2,count,128)
        full[:16]=uuid.UUID('7C3457EF-0000-11AA-AA11-00306543ECAC').bytes_le;struct.pack_into('<QQ',full,32,10,19)
        full[128]=1;struct.pack_into('<QQ',full,160,20,100)
        struct.pack_into('<I',h,88,zlib.crc32(full));self.header_crc(h)
        return h,bytearray(full[:4096]).ljust(4096,b'\0')
    @staticmethod
    def header_crc(h):struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
    def parse(self,h,p):
        hh=C.create_string_buffer(bytes(h));pp=C.create_string_buffer(bytes(p));old=(hh.raw,pp.raw);o=Prefix();C.memset(C.byref(o),0x5a,C.sizeof(o));before=bytes(o)
        rc=self.lib.run(hh,pp,4096,C.byref(o));self.assertEqual((hh.raw,pp.raw),old)
        if rc:self.assertEqual(bytes(o),before)
        return rc,o
    def test_complete_array_independent_crc_and_APFS_type_not_unique_GUID(self):
        h,p=self.fixture();rc,o=self.parse(h,p);self.assertEqual(rc,0);self.assertEqual((o.declared,o.checked,o.used,o.apfs_type_count),(32,32,2,1));self.assertEqual((o.array_complete,o.array_crc_checked,o.array_crc_ok),(1,1,1));self.assertEqual((o.ranges[0].first,o.ranges[0].last),(10,19))
    def test_partial_array_never_claims_crc_or_completeness(self):
        h,p=self.fixture(128);rc,o=self.parse(h,p);self.assertEqual(rc,0);self.assertEqual((o.declared,o.checked,o.used),(128,32,2));self.assertEqual((o.array_complete,o.array_crc_checked,o.array_crc_ok),(0,0,0))
    def test_crc_range_overlap_and_header_failures_are_atomic(self):
        h,p=self.fixture();bad=bytearray(p);bad[70]^=1;self.assertEqual(self.parse(h,bad)[0],-2)
        for start,last,rc in [(2,19,-3),(20,19,-3),(10,15624999,-3),(18,100,-4)]:
            bad=bytearray(p);struct.pack_into('<QQ',bad,160,start,last);hh=bytearray(h);struct.pack_into('<I',hh,88,zlib.crc32(bad));self.header_crc(hh);self.assertEqual(self.parse(hh,bad)[0],rc)
        hh=bytearray(h);struct.pack_into('<Q',hh,72,3);self.header_crc(hh);self.assertEqual(self.parse(hh,p)[0],-1)
    def test_bad_size_and_null_are_rejected_without_output_mutation(self):
        h,p=self.fixture();hh=C.create_string_buffer(bytes(h));pp=C.create_string_buffer(bytes(p));o=Prefix();C.memset(C.byref(o),0x5a,C.sizeof(o));old=bytes(o)
        for n in [0,512,4095,4097]:self.assertEqual(self.lib.run(hh,pp,n,C.byref(o)),-1);self.assertEqual(bytes(o),old)
        self.assertEqual(self.lib.run(None,pp,4096,C.byref(o)),-1)
