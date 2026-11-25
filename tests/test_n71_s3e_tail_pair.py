# SPDX-License-Identifier: MIT
"""Tail pair runs the existing command/fault matrix against the real new core."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_n71_s3e_read_series import CORE, PORT
from test_n71_s3e_ro_block import MODEL

class TailPairTests(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'case.c';exe=Path(td)/'case';src.write_text(source)
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(PORT),str(src),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
    def test_tail_command_encoding_bit_corruption_and_all_failure_stops(self):
        macros = r"""
#define n71_read_series_command(b,s,l,n,z,f) n71_read_pair_command(b,s,l,n,z,f,15624998U)
#define n71_read_series_command_valid(b,s,l,n,z,f) n71_read_pair_command_valid(b,s,l,n,z,f,15624998U)
#define n71_read_series_core(o,c,l,n,z,f,r) n71_read_pair_core(o,c,l,n,z,f,r,15624998U)
"""
        s=CORE.replace('#include "n71_s3e_read_series_core.h"','#include "n71_s3e_read_series_core.h"'+macros)
        s=s.replace('==(step&1)&&','==(15624998U+(step&1))&&').replace('&&i!=40)', '&&!(i>=40&&i<48))')
        self.compile_run(s)
    def test_tail_bio_admission_exhaustion_and_atomic_rejection(self):
        macros = r"""
#define n71_ro_block_admissible(f,r) n71_ro_block_pair_admissible(f,r,15624998U)
#define n71_ro_block_admit(f,r) n71_ro_block_pair_admit(f,r,15624998U)
"""
        s=MODEL.replace('#include "n71_s3e_ro_block_core.h"','#include "n71_s3e_ro_block_core.h"'+macros)
        s=s.replace('8ULL*(step&1)','8ULL*(15624998U+(step&1))')
        self.compile_run(s)
    def test_only_two_pair_bases_and_reject_before_mutation(self):
        self.compile_run(r"""
#include <assert.h>
#include <string.h>
#include "n71_s3e_ro_block_core.h"
int main(void) {
 unsigned bases[]={1,2,15624997,15624999,15625000,~0U},i;
 struct n71_ro_block_flow f={.active=1},old=f;
 struct n71_ro_block_request r={0,1,4096,1,0,1,1};
 unsigned char b[64],oldb[64];
 const struct n71_s3e_ro_io_layout l={0x80010000ULL,0x80011000ULL,0x80012000ULL,0x80013000ULL,0x40800000ULL};
 memset(b,0x5a,64);memcpy(oldb,b,64);
 for(i=0;i<sizeof(bases)/sizeof(bases[0]);i++) {
  assert(!n71_read_pair_base_valid(bases[i]));
  assert(n71_ro_block_pair_admit(&f,&r,bases[i])==-1&&!memcmp(&f,&old,sizeof(f)));
  assert(n71_read_pair_command(b,0,&l,15625000,4096,32,bases[i])==-1&&!memcmp(b,oldb,64));
 }
 assert(n71_read_pair_lba(15624998U,3)==15624999U);
 return 0;
}
""")
    def test_tail_selection_requires_block_mode_before_hardware(self):
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        self.assertIn('static bool ans_ro_block_tail_once;',s)
        init=s[s.index('static int __init n71_port0_init'):]
        self.assertLess(init.index('if (ans_ro_block_tail_once && !ans_ro_block_once)'),init.index('n71_board_gate()'))
        for name in ['n71_s3e_read_series_runtime.h','n71_s3e_ro_block_runtime.h']:
            s=(PORT/name).read_text()
            self.assertIn('n71_series_base()',s)
            self.assertNotIn('n71_read_series_lba(',s)
