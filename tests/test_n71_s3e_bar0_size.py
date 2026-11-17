# SPDX-License-Identifier: MIT
"""BAR0 sizing must restore pairs and retain unsafe decode states."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_bar0_size.h"
struct model {
 unsigned lo,hi,old_lo,old_hi,mask_lo,mask_hi,command,writes,high_writes;
 int probe_lo,probe_hi,lose_ready,fail_restore,enable_decode;
};
static int ready(void *ctx) {
 struct model *m=ctx;return !(m->lose_ready && m->probe_lo);
}
static unsigned rd(void *ctx,unsigned off) {
 struct model *m=ctx;
 if(off==4)return m->command;
 if(off==0x10)return m->probe_lo?m->mask_lo:m->lo;
 assert(off==0x14);return m->probe_hi?m->mask_hi:m->hi;
}
static void wr(void *ctx,unsigned off,unsigned v) {
 struct model *m=ctx;assert(off==0x10 || off==0x14);m->writes++;
 if(off==0x10) {
  if(v==~0U) {m->probe_lo=1;if(m->enable_decode)m->command=2;}
  else {
   assert(!m->command);
   if(m->fail_restore)return;
   m->probe_lo=0;m->lo=v;
  }
 } else {
  m->high_writes++;
  if(v==~0U)m->probe_hi=1;
  else {assert(!m->command);m->probe_hi=0;m->hi=v;}
 }
}
static void init(struct model *m) {
 memset(m,0,sizeof(*m));m->lo=m->old_lo=4;
 m->mask_lo=0xffffc004U;m->mask_hi=0xffffffffU;
}
static void restored(struct model *m) {
 assert(!m->probe_lo && !m->probe_hi && m->lo==m->old_lo && m->hi==m->old_hi);
}
int main(void) {
 struct model m;struct n71_s3e_bar_result r;int rc;
 const struct n71_s3e_bar_ops o={.ready=ready,.read=rd,.write=wr};
 init(&m);rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(!rc && r.restored && r.is64 && r.size==0x4000);restored(&m);
 init(&m);m.lo=m.old_lo=0;m.hi=m.old_hi=0x87654321;m.mask_lo=0xffff0000;
 rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(!rc && r.restored && !r.is64 && r.size==0x10000 && !m.high_writes);restored(&m);
 init(&m);m.mask_lo=0xffff9004;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-2 && r.restored);restored(&m);
 init(&m);m.lose_ready=1;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-1 && r.restored);restored(&m);
 init(&m);m.command=4;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-1 && !m.writes);restored(&m);
 init(&m);m.lo=m.old_lo=1;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-2 && !m.writes);restored(&m);
 init(&m);m.fail_restore=1;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-3 && !r.restored && m.probe_lo);
 init(&m);m.enable_decode=1;rc=n71_s3e_bar0_size_trial(&o,&m,&r);
 assert(rc==-3 && !r.restored && m.command==2 && m.probe_lo && m.probe_hi);
 puts("BAR0_GEOMETRY_AND_SAFE_RESTORE_CASES_PASS");return 0;
}
"""
class S3EBar0Geometry(unittest.TestCase):
    def test_sizing_and_failure_paths(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"trial.c";p.write_text(C);binary=Path(d)/"trial"
            r=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
                "-I",str(ROOT/"experimental/port0"),str(p),"-o",str(binary)],
                capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("BAR0_GEOMETRY_AND_SAFE_RESTORE_CASES_PASS",r.stdout)
if __name__=="__main__":unittest.main()
