# SPDX-License-Identifier: MIT
"""NVMMU flush timeouts and unsafe observers must retain owned buffers."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_nvmmu_owned_tables.h"
struct model {unsigned regs[6],old[4],pending,flushes,writes;int ready,freeze,restore_bad,program_bad,observer_rc,lose_ready;};
static unsigned read_reg(void *c,unsigned off) {
 struct model *m=c;assert(off<=0x14&&!(off&3));
 if(off==4&&m->pending&&!m->freeze){if(!--m->pending)m->regs[1]=0;}
 return m->regs[off/4];
}
static void write_reg(void *c,unsigned off,unsigned v) {
 struct model *m=c;assert(off==4||off==8||off==12||off==16||off==20);m->writes++;
 if(off==4){assert(v==0x10000);m->flushes++;m->pending=2;}
 if(off==16&&m->program_bad&&v==0x20004000U){m->program_bad=0;return;}
 if(off==16&&m->restore_bad&&v==m->old[2])return;
 m->regs[off/4]=v;
}
static int ready(void *c){return ((struct model *)c)->ready;}
static void tick(void *c){(void)c;}
static int observe(void *c){struct model *m=c;if(m->lose_ready)m->ready=0;return m->observer_rc;}
static void init(struct model *m){memset(m,0,sizeof(*m));m->regs[0]=1;m->ready=1;m->regs[2]=0x10000000;m->regs[3]=8;m->regs[4]=0x10004000;m->regs[5]=8;memcpy(m->old,m->regs+2,sizeof(m->old));}
static void baseline(struct model *m){assert(!memcmp(m->old,m->regs+2,sizeof(m->old))&&!m->regs[1]);}
int main(void){
 struct model m;struct n71_nvmmu_result r;int rc;
 const struct n71_nvmmu_ops o={read_reg,write_reg,ready,tick,observe};
 const unsigned long long tcb=0x820000000ULL,aux=0x820004000ULL;
 init(&m);rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(!rc&&r.restored&&m.flushes==2&&r.owned_polls==2&&r.restore_polls==2);baseline(&m);
 init(&m);m.observer_rc=-9;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-9&&r.restored);baseline(&m);
 init(&m);m.observer_rc=-3;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-3&&!r.restored&&m.flushes==1&&m.regs[2]==0x20000000);
 init(&m);m.freeze=1;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-3&&!r.restored&&r.owned_polls==1000&&m.regs[4]==0x20004000);
 init(&m);m.restore_bad=1;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-3&&!r.restored);
 init(&m);m.program_bad=1;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-2&&r.restored&&m.flushes==1);baseline(&m);
 init(&m);m.lose_ready=1;rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb,aux,&r);assert(rc==-3&&!r.restored&&m.regs[2]==0x20000000);
 init(&m);rc=n71_nvmmu_owned_tables_trial(&o,&m,tcb+1,aux,&r);assert(rc==-1&&!m.writes);baseline(&m);
 init(&m);rc=n71_nvmmu_owned_tables_trial(&o,&m,~0ULL-16383,aux,&r);assert(rc==-1&&!m.writes);baseline(&m);
 puts("NVMMU_OWNERSHIP_TIMEOUT_AND_RESTORE_CASES_PASS");return 0;
}
"""
class NvmmuOwnedTables(unittest.TestCase):
    def test_transactions_and_quarantine(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"trial.c";src.write_text(C);exe=Path(d)/"trial"
            q=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"experimental/port0"),str(src),"-o",str(exe)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            self.assertIn("NVMMU_OWNERSHIP_TIMEOUT_AND_RESTORE_CASES_PASS",q.stdout)
if __name__=="__main__":unittest.main()
