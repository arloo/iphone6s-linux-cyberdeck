# SPDX-License-Identifier: MIT
"""SART ownership must survive missing PERST or incomplete rollback."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_sart_hmb_owned.h"
struct model {unsigned reg[4],writes,pa;int perst,mode,restore_fail,callback_calls;};
static int ready(void *ctx) {struct model *m=ctx;return !m->perst;}
static unsigned rd(void *ctx,unsigned off) {struct model *m=ctx;assert(off>=0x20&&off<=0x2c&&!(off&3));return m->reg[(off-0x20)/4]|((off==0x24||off==0x28)?0x80000000U:0);}
static void wr(void *ctx,unsigned off,unsigned v) {
 struct model *m=ctx;assert(!m->perst&&off>=0x20&&off<=0x2c&&!(off&3));m->writes++;
 if(m->restore_fail&&m->callback_calls&&off==0x24)return;
 m->reg[(off-0x20)/4]=(off==0x24||off==0x28)?v&0x3fffffffU:v;
}
static int hold(void *ctx) {
 struct model *m=ctx;m->callback_calls++;
 assert(m->reg[0]==1&&m->reg[1]==0x3c000000&&m->reg[2]==0x3c700000&&m->reg[3]==m->pa);
 if(m->mode==1)return -2;
 if(m->mode==2)return -3;
 if(m->mode==3)m->perst=1;
 return 0;
}
static void init(struct model *m) {memset(m,0,sizeof(*m));m->pa=0x8200;m->reg[0]=1;m->reg[1]=0x1000000;m->reg[2]=0x1700000;m->reg[3]=0x8100;}
static void restored(struct model *m) {assert(m->reg[0]==1&&m->reg[1]==0x1000000&&m->reg[2]==0x1700000&&m->reg[3]==0x8100);}
int main(void) {
 struct model m;struct n71_sart_result r;
 const struct n71_sart_ops o={ready,rd,wr,hold};
 init(&m);assert(!n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)&&r.installed&&r.restored);restored(&m);
 init(&m);m.mode=1;assert(n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)==-2&&r.restored);restored(&m);
 init(&m);m.mode=2;assert(n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)==-3&&!r.restored&&m.reg[3]==m.pa);
 init(&m);m.mode=3;assert(n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)==-3&&!r.restored&&m.reg[3]==m.pa);
 init(&m);m.restore_fail=1;assert(n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)==-3&&!r.restored);
 init(&m);assert(n71_sart_hmb_owned_trial(&o,&m,0x820000001ULL,&r)==-1&&!m.writes);
 init(&m);m.perst=1;assert(n71_sart_hmb_owned_trial(&o,&m,0x820000000ULL,&r)==-1&&!m.writes);
 puts("SART_HMB_OWNERSHIP_AND_QUARANTINE_PASS");return 0;
}
"""
class SartHmb(unittest.TestCase):
    def test_safe_restore_and_unsafe_retention(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"trial.c";src.write_text(C);binary=Path(d)/"trial"
            q=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"experimental/port0"),str(src),"-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            self.assertIn("SART_HMB_OWNERSHIP_AND_QUARANTINE_PASS",q.stdout)
if __name__=="__main__":unittest.main()
