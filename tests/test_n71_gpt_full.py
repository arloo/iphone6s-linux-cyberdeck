# SPDX-License-Identifier: MIT
"""Fixed five-slot wire/ownership fault matrix and independently checksummed GPT."""
from pathlib import Path
import ctypes as C
import struct
import subprocess
import tempfile
import unittest
import zlib
from test_n71_s3e_read_series import CORE, STAGE, PORT
from test_n71_s3e_ro_block import MODEL
from test_n71_s3e_ro_probe import HANDLER, HELPER
import test_n71_bounded_pair_gpt as pairmod
Range=pairmod.Range
ROOT=Path(__file__).resolve().parents[1]

class FullTransportTests(unittest.TestCase):
    compile_run=pairmod.PairTests.compile_run
    def test_five_commands_actual_wire_CQE_fault_matrix_and_no_sixth_request(self):
        s='#define N71_GPT_FULL_PLAN 1\n'+CORE
        s=s.replace('[4][4096]','[5][4096]').replace('==(step&1)&&','==(step+1)&&')
        s=s.replace('memset(m->data[step],(step&1)?0x31:0x17,4096);','memset(m->data[step],step+1,4096);')
        s=s.replace('return memcmp(m->copy[0],m->copy[2],4096)||memcmp(m->copy[1],m->copy[3],4096)?-47:0;', 'for(unsigned i=0;i<5;i++){for(unsigned j=0;j<4096;j++){if(m->copy[i][j]!=i+1)return -47;}}return 0;')
        s=s.replace('step<4','step<5').replace('stability_checks==5','stability_checks==6')
        for token in ['r.submitted','r.accepted','r.snapshotted','m.submitted','m.accepted','m.snapshots']:
            s=s.replace(token+'==4',token+'==5')
        s=s.replace('command(b,4,','command(b,5,').replace('series_tag(4)','series_tag(5)')
        self.compile_run(s)
    def test_five_distinct_tags_all_or_nothing_shadow_and_foreign_frame_exclusion(self):
        s='#define N71_GPT_FULL_PLAN 1\n'+STAGE
        s=s.replace('[4]','[5]').replace('sgl_data[3]};','sgl_data[3],sgl_data[4]};')
        s=s.replace('0x82000c000ULL}','0x82000c000ULL,0x820010000ULL}').replace('0x83000c000ULL}','0x83000c000ULL,0x830010000ULL}')
        s=s.replace('i<4','i<5').replace('640','768').replace('frame(&frames,8)','frame(&frames,10)')
        self.compile_run(s)
    def test_five_bios_reject_wrong_LBA_write_untrusted_and_sixth_request(self):
        s='#define N71_GPT_FULL_PLAN 1\n'+MODEL
        s=s.replace('8ULL*(step&1)','8ULL*(1U+step)').replace('step<4','step<5').replace('request(4)','request(5)')
        self.compile_run(s)
    def test_actual_kernel_char_handler_five_reads_copy_fault_close_and_terminal_state(self):
        s='#define N71_GPT_FULL_PLAN 1\n'+HANDLER
        s=s.replace('n71_series_base(void){return 0;}','n71_series_base(void){return 1;}').replace('[4]','[5]').replace('i<4','i<5')
        s=s.replace('off=4096;assert','off=8192;assert').replace('off=0;','off=4096;').replace('off=4096*(i&1);','off=4096*(1+i);')
        s=s.replace('copied==4','copied==5').replace('request_events==4','request_events==5')
        self.compile_run(s)
    def test_explicit_full_plan_gate_all_booleans_and_pre_board_integration(self):
        self.compile_run(r"""
#define N71_GPT_FULL_PLAN 1
#include <assert.h>
#include "n71_s3e_ro_block_core.h"
int main(void){unsigned bits;for(bits=0;bits<256;bits++) {
 unsigned selected=bits&1,block=(bits>>1)&1,probe=(bits>>2)&1,pair=(bits>>3)&1;
 unsigned base=(bits&16)?1U:~0U,tail=(bits>>5)&1,series=(bits>>6)&1,single=(bits>>7)&1;
 int want=selected&&block&&probe&&!pair&&base==~0U&&!tail&&!series&&!single;
 assert(!!n71_gpt_full_mode_valid(selected,block,probe,pair,base,tail,series,single)==want);
 }assert(N71_READ_SERIES_COUNT==5&&N71_READ_SERIES_DMA_PAGES==10&&N71_READ_SERIES_PAGES==15);
 assert(n71_read_pair_base_valid(1));assert(!n71_read_pair_base_valid(0));assert(!n71_read_pair_base_valid(2));return 0;}
""")
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text();s=s[s.index('static int __init n71_port0_init'):]
        self.assertLess(s.index('n71_gpt_full_mode_valid('),s.index('n71_board_gate()'))

class Full(C.Structure):
    _fields_=[(n,C.c_uint) for n in ['declared','checked','used','apfs_type_count','array_complete','array_crc_checked','array_crc_ok']]+[('ranges',Range*128)]

def fixture():
    h,_=pairmod.GPTPrefixTests().fixture(128);a=bytearray(16384)
    # Populate every page, including entry128, with independent non-overlapping ranges.
    for slot,start in [(0,10),(32,100),(64,200),(127,300)]:
        a[slot*128]=1;struct.pack_into('<QQ',a,slot*128+32,start,start+9)
    a[:16]=bytes.fromhex('ef57347c0000aa11aa1100306543ecac')
    struct.pack_into('<I',h,88,zlib.crc32(a));pairmod.GPTPrefixTests.header_crc(h)
    return h,a

class FullParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name)
        (p/'case.c').write_text('#include "n71-gpt-full-core.h"\nint run(const unsigned char *h,const unsigned char *a,struct n71_gpt_full_result *o){const unsigned char *p[4]={a,a+4096,a+8192,a+12288};return n71_gpt_full_parse(h,p,o);}\n')
        q=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'experimental/storage'),str(p/'case.c'),'-o',str(p/'case.so')],capture_output=True,text=True)
        if q.returncode:raise AssertionError(q.stderr)
        cls.lib=C.CDLL(str(p/'case.so'));cls.lib.run.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(Full)];cls.lib.run.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def parse(self,h,a):
        hh=C.create_string_buffer(bytes(h));aa=C.create_string_buffer(bytes(a));before=(hh.raw,aa.raw);out=Full();C.memset(C.byref(out),0xa5,C.sizeof(out))
        rc=self.lib.run(hh,aa,C.byref(out));self.assertEqual((hh.raw,aa.raw),before)
        if rc:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return rc,out
    def test_all_128_entries_last_slot_and_independent_header_and_array_CRC(self):
        h,a=fixture();rc,o=self.parse(h,a);self.assertEqual(rc,0)
        self.assertEqual((o.declared,o.checked,o.used,o.apfs_type_count,o.array_complete,o.array_crc_checked,o.array_crc_ok),(128,128,4,1,1,1,1))
        self.assertEqual([o.ranges[i].slot for i in range(o.used)],[1,33,65,128])
    def test_every_array_page_corruption_fails_including_unused_bytes(self):
        h,a=fixture()
        for index in [0,4095,4096,8191,8192,12287,12288,16383]:
            bad=bytearray(a);bad[index]^=1;self.assertEqual(self.parse(h,bad)[0],-1)
    def test_cross_page_overlap_and_bad_final_entry_range_fail_without_partial_coordinates(self):
        h,a=fixture()
        for first,last,want in [(15,25,-4),(1,10,-3),(400,300,-3),(300,15624999,-3)]:
            bad=bytearray(a);struct.pack_into('<QQ',bad,127*128+32,first,last);hh=bytearray(h)
            struct.pack_into('<I',hh,88,zlib.crc32(bad));pairmod.GPTPrefixTests.header_crc(hh)
            self.assertEqual(self.parse(hh,bad)[0],want)
    def test_fixed_geometry_header_CRC_and_null_header_are_fail_closed(self):
        h,a=fixture()
        for off,value,fmt in [(16,0,'I'),(72,3,'Q'),(80,32,'I'),(84,256,'I')]:
            bad=bytearray(h);struct.pack_into('<'+fmt,bad,off,value)
            if off!=16:pairmod.GPTPrefixTests.header_crc(bad)
            self.assertEqual(self.parse(bad,a)[0],-1)
        aa=C.create_string_buffer(bytes(a));out=Full();self.assertEqual(self.lib.run(None,aa,C.byref(out)),-1)
    def test_actual_helper_five_private_preads_and_each_no_retry_failure(self):
        h,a=fixture();arrays='static unsigned char fixture_data[20480]={'+','.join(str(x) for x in h+a)+'};\n'
        s=HELPER.replace('static ssize_t fake_pread(',arrays+'static ssize_t fake_pread(').replace('if(unsafe)return 0;errno=ENOENT;return -1;', 'if(unsafe){return 0;}\n errno=ENOENT;return -1;')
        s=s.replace('step<4','step<5').replace('(base+(step&1U))','(base+step)').replace('memset(out,(step&1U)?0x31:0x17,4096);','memcpy(out,fixture_data+step*4096,4096);')
        start=s.index('int main(void) {');s=s[:start]+r"""
int main(void){char *args[]={"probe","--gpt-full",NULL};unsigned j;
 for(j=0;j<7;j++) {
 base=1;opened=reads=created=unlinked=closed=0;fail_at=corrupt=unsafe=regular=0;
 if(j>=1&&j<=5){fail_at=j;}if(j==6){fixture_data[20479]^=1;}
 assert(helper_main(2,args)==(j?1:0));assert(opened==2&&created==1&&unlinked==1&&closed==1);
 assert(reads==(fail_at?2+fail_at:7));
 }return 0;}
"""
        pairmod.PairTests.compile_run(self,s)
