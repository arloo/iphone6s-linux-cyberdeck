# SPDX-License-Identifier: MIT
"""Read-only HMB probe refuses stale descriptors and lost guard ownership."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_ans_hmb_ro.h"
struct model {unsigned calls,req,change,lost,allones;};
static int ready(void *ctx) {struct model *m=ctx;return !m->lost||m->calls<m->lost;}
static unsigned rd(void *ctx,unsigned off) {
 struct model *m=ctx;m->calls++;
 if(m->allones)return ~0U;
 switch(off) {
 case 0x1808:return m->change&&m->calls==5 ? m->req+4096 : m->req;
 case 0x1810:case 0x1814:case 0x1818:return 0;
 default:assert(0);return ~0U;
 }
}
int main(void) {
 struct model m={0};struct n71_ans_hmb_result r;
 const struct n71_ans_hmb_ops o={ready,rd};
 assert(!n71_ans_hmb_ro(&o,&m,&r)&&r.reads==5&&r.stable&&!r.nonzero);
 memset(&m,0,sizeof(m));m.req=0x200000;
 assert(!n71_ans_hmb_ro(&o,&m,&r)&&r.nonzero&&r.aligned&&r.request==m.req);
 memset(&m,0,sizeof(m));m.req=0x200000;m.change=1;
 assert(n71_ans_hmb_ro(&o,&m,&r)==-2&&!r.stable);
 memset(&m,0,sizeof(m));m.lost=3;
 assert(n71_ans_hmb_ro(&o,&m,&r)==-1&&m.calls==3&&r.reads==3);
 memset(&m,0,sizeof(m));m.allones=1;
 assert(n71_ans_hmb_ro(&o,&m,&r)==-2);
 puts("HMB_READONLY_GUARD_FAILURES_PASS");return 0;
}
"""
class AnsHmbRo(unittest.TestCase):
    def test_guard_and_descriptor_failures(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"trial.c";src.write_text(C);binary=Path(d)/"trial"
            p=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"experimental/port0"),str(src),"-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn("HMB_READONLY_GUARD_FAILURES_PASS",p.stdout)
if __name__=="__main__":unittest.main()
