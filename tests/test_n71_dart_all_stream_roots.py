# SPDX-License-Identifier: MIT
"""Exercise all-stream rollback failures; physical qualification is separate."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-dart-all-stream-owned-roots-trial.h"
struct model {
 unsigned r[32], old[16], roots[16], writes, pending;
 int low, timeout, bad_root, bad_disable, fault, unsafe;
};
static unsigned rd(void *ctx,unsigned off) {
 struct model *m=ctx;
 if(off==0 && m->pending && !m->timeout) {
  if(!--m->pending)m->r[0]=0xf02;
 }
 return m->r[off/4];
}
static void wr(void *ctx,unsigned off,unsigned v) {
 struct model *m=ctx;unsigned i;
 m->writes++;
 if(off>=0x40) {
  assert(off<=0x7c && !(off&3));
  if(m->r[3] && v==m->old[(off-0x40)/4])m->unsafe=1;
  if(m->bad_root && off==0x74 && v==m->roots[13])v^=1;
 }
 if(off==0xc && v==0x80808080) {
  for(i=0;i<16;i++)if(m->r[16+i]!=m->roots[i])m->unsafe=1;
 }
 if(off==0xc && v==0 && m->r[3] && m->bad_disable)return;
 m->r[off/4]=v;
 if(off==0) {
  assert(v==0xf02);m->r[0]|=8;m->pending=2;
  if(m->fault)m->r[4]^=0x80000000U;
 }
}
static int low(void *ctx){return ((struct model*)ctx)->low;}
static void tick(void *ctx){(void)ctx;}
static void init(struct model *m) {
 unsigned i;memset(m,0,sizeof(*m));m->low=1;m->r[0]=0xf02;m->r[4]=0x100;
 for(i=0;i<16;i++) {
  m->r[16+i]=m->old[i]=0x800ff000U+i;
  m->roots[i]=0x80091000U+4*i;
 }
}
static void restored(struct model *m) {
 unsigned i;assert(!m->r[3] && !m->unsafe);
 for(i=0;i<16;i++)assert(m->r[16+i]==m->old[i]);
}
int main(void) {
 struct model m;unsigned last,polls,i;int rc;
 const struct n71_dart_trial_ops o={
  .read=rd,.write=wr,.perst_low=low,.tick=tick
 };
 (void)n71_dart_owned_ttbr;
 (void)n71_dart_owned_roots_trial;
 (void)n71_dart_disabled_ttbr_trial;
 init(&m);rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==0 && polls==2 && last==0xf02);restored(&m);
 init(&m);m.timeout=1;rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-2 && polls==100 && (last&8));restored(&m);
 init(&m);m.bad_disable=1;rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-3 && m.r[3]==0x80808080U && !m.unsafe);
 for(i=0;i<16;i++)assert(m.r[16+i]==m.roots[i]);
 init(&m);m.bad_root=1;rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-2);restored(&m);
 init(&m);m.fault=1;rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-1);restored(&m);
 init(&m);m.low=0;rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-1 && !m.writes);restored(&m);
 init(&m);m.roots[15]=m.roots[0];rc=n71_dart_all_stream_owned_roots_trial(&o,&m,m.roots,&last,&polls);
 assert(rc==-1 && !m.writes);restored(&m);
 puts("ALL_STREAM_ROLLBACK_AND_RETAIN_CASES_PASS");
 return 0;
}
"""
class AllStreamDartRollback(unittest.TestCase):
    def test_success_deadline_failure_and_page_retention(self):
        self.assertIsNotNone(shutil.which("cc"))
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"trial.c"
            binary=Path(d)/"trial"
            source.write_text(C)
            subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
                            "-I",str(ROOT/"experimental/port1"),
                            str(source),"-o",str(binary)],check=True,
                           capture_output=True,text=True)
            r=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
            self.assertIn("ALL_STREAM_ROLLBACK_AND_RETAIN_CASES_PASS",r.stdout)

if __name__=="__main__":
    unittest.main()
