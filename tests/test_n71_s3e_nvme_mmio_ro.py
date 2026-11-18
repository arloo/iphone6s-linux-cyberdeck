# SPDX-License-Identifier: MIT
"""Regressions for command-width, BAR rollback and unsafe-state retention."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_nvme_mmio_ro.h"
struct model {
 unsigned rootcmd,epcmd,lo,hi,window,pf,pfbhi,pflhi,vs;
 unsigned writes,reads,ever_enabled;
 int fail_clear,fail_restore,lose_ready,fail_enable;
};
static int ready(void *c) {struct model *m=c;return !(m->lose_ready&&m->ever_enabled);}
static unsigned root(void *c,unsigned off) {
 struct model *m=c;
 switch(off) {
 case 4:return 0x00100000U|m->rootcmd;
 case 0x20:return m->window;
 case 0x24:return m->pf;
 case 0x28:return m->pfbhi;
 case 0x2c:return m->pflhi;
 default:assert(0);return ~0U;
 }
}
static unsigned ep(void *c,unsigned off) {
 struct model *m=c;
 switch(off) {case 4:return 0x00100000U|m->epcmd;case 0x10:return m->lo;case 0x14:return m->hi;default:assert(0);return ~0U;}
}
static void bar(void *c,unsigned off,unsigned v) {
 struct model *m=c;assert(!m->rootcmd&&!m->epcmd);m->writes++;
 if(off==0x10){if(m->fail_restore&&v==4)return;m->lo=v;}
 else {assert(off==0x14);m->hi=v;}
}
static void window(void *c,unsigned v) {struct model *m=c;assert(!m->rootcmd&&!m->epcmd);m->writes++;m->window=v;}
static void rc(void *c,unsigned v) {struct model *m=c;assert(v==0||v==2);m->writes++;if(v==2&&m->fail_enable)return;m->rootcmd=v;}
static void ec(void *c,unsigned v) {struct model *m=c;assert(v==0||v==2);m->writes++;if(!v&&m->fail_clear)return;m->epcmd=v;if(v)m->ever_enabled=1;}
static unsigned nvme(void *c,unsigned off) {
 struct model *m=c;assert(m->rootcmd==2&&m->epcmd==2&&m->lo==0xc1000004U&&m->window==0xc100c100U);m->reads++;
 switch(off){case 0:return 0x001003ff;case 4:return 0x20;case 8:return m->vs;case 0x14:return 0;case 0x1c:return 0;default:assert(0);return ~0U;}
}
static int observe_ok(void *c) {struct model *m=c;assert(m->rootcmd==2&&m->epcmd==2&&m->reads==5);return 0;}
static int observe_fail(void *c) {assert(!observe_ok(c));return -2;}
static int observe_unsafe(void *c) {assert(!observe_ok(c));return -3;}
static void init(struct model *m) {memset(m,0,sizeof(*m));m->lo=4;m->window=m->pf=0x0000fff0U;m->vs=0x00010100;}
static void baseline(struct model *m) {assert(!m->rootcmd&&!m->epcmd&&m->lo==4&&!m->hi&&m->window==0x0000fff0U);}
int main(void) {
 struct model m;struct n71_s3e_mmio_result r;int result;
 struct n71_s3e_mmio_ops o={ready,root,ep,window,bar,rc,ec,nvme,0};
 init(&m);result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);
 assert(!result&&r.restored&&r.reads==5&&m.reads==5&&r.vs==0x00010100);baseline(&m);
 init(&m);m.vs=~0U;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-2&&r.restored);baseline(&m);
 init(&m);m.epcmd=4;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-1&&!m.writes&&!m.reads);
 init(&m);m.pf=0;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(!result&&r.restored&&m.reads==5);baseline(&m);
 init(&m);m.pf=0xc070c000U;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-2&&!m.writes&&!m.reads);baseline(&m);
 init(&m);m.pf=0xc100c100U;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-2&&!m.writes&&!m.reads);baseline(&m);
 init(&m);m.pf=0x00010001;m.pflhi=1;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-2&&!m.writes);baseline(&m);
 init(&m);m.fail_enable=1;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-1&&r.restored&&!m.reads);baseline(&m);
 init(&m);m.lose_ready=1;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-1&&r.restored&&!m.reads);baseline(&m);
 init(&m);m.fail_restore=1;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-3&&!r.restored&&m.lo==0xc1000004U&&!m.rootcmd&&!m.epcmd);
 init(&m);m.fail_clear=1;result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-3&&!r.restored&&m.epcmd==2&&m.lo==0xc1000004U&&m.window==0xc100c100U);
 o.active_readonly=observe_ok;init(&m);result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(!result&&r.restored);baseline(&m);
 o.active_readonly=observe_fail;init(&m);result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-2&&r.restored);baseline(&m);
 o.active_readonly=observe_unsafe;init(&m);result=n71_s3e_nvme_mmio_ro_trial(&o,&m,&r);assert(result==-3&&!r.restored&&m.epcmd==2&&m.rootcmd==2&&m.lo==0xc1000004U&&m.window==0xc100c100U);
 puts("S3E_NVME_RO_AND_UNSAFE_ROLLBACK_CASES_PASS");return 0;
}
"""
class S3ENvmeMmio(unittest.TestCase):
    def test_transaction_and_unsafe_failures(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"trial.c";src.write_text(C);binary=Path(d)/"trial"
            q=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"experimental/port0"),str(src),"-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            self.assertIn("S3E_NVME_RO_AND_UNSAFE_ROLLBACK_CASES_PASS",q.stdout)
if __name__=="__main__":unittest.main()
