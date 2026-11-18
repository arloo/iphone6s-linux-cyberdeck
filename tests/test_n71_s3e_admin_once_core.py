# SPDX-License-Identifier: MIT
"""Refuse early DMA and retain memory when controller shutdown is uncertain."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "n71_s3e_admin_once_core.h"
struct model {unsigned master,cc,csts,master_calls,cc_calls,identify_calls,ms;int deny,enable_timeout,shutdown_timeout,shutdown_fatal,disable_timeout,fail_master_off,identify_fail;};
static int qualified(void *ctx) {struct model *m=ctx;return !m->deny&&!m->master&&!m->cc&&!m->csts;}
static int master(void *ctx,int on) {struct model *m=ctx;m->master_calls++;if(on)assert(qualified(ctx));if(!on&&m->fail_master_off)return -1;m->master=on;return 0;}
static void cc(void *ctx,unsigned v) {
 struct model *m=ctx;assert(m->master);m->cc=v;m->cc_calls++;
 if(v==0x460001)m->csts=m->enable_timeout?0:1;
 else if(v==0x464001)m->csts=m->shutdown_fatal?3:(m->shutdown_timeout?1:9);
 else {assert(!v);m->csts=m->disable_timeout?1:0;}
}
static unsigned csts(void *ctx) {return ((struct model *)ctx)->csts;}
static void delay(void *ctx,unsigned ms) {((struct model *)ctx)->ms+=ms;}
static int identify(void *ctx) {struct model *m=ctx;assert(m->master&&m->cc==0x460001&&m->csts==1);m->identify_calls++;return m->identify_fail?-2:0;}
int main(void) {
 struct model m={0};struct n71_admin_once_result r;
 const struct n71_admin_once_ops o={qualified,master,cc,csts,delay,identify};
 assert(!n71_admin_once_core(&o,&m,&r)&&r.stopped&&r.master_off&&m.identify_calls==1 &&
        r.shutdown_attempted==1&&r.shutdown_rc==0&&r.shutdown_csts==9&&
        r.disable_rc==0&&r.disable_csts==0&&r.inner_rc==0);
 memset(&m,0,sizeof(m));m.deny=1;assert(n71_admin_once_core(&o,&m,&r)==-1&&!m.master_calls&&!m.cc_calls);
 memset(&m,0,sizeof(m));m.enable_timeout=1;assert(n71_admin_once_core(&o,&m,&r)==-1&&r.stopped&&!m.identify_calls&&m.ms<=5100);
 memset(&m,0,sizeof(m));m.identify_fail=1;assert(n71_admin_once_core(&o,&m,&r)==-2&&r.stopped&&m.identify_calls==1);
 memset(&m,0,sizeof(m));m.shutdown_timeout=1;assert(n71_admin_once_core(&o,&m,&r)==-3&&!r.stopped&&r.master_off);
 memset(&m,0,sizeof(m));m.shutdown_fatal=1;assert(n71_admin_once_core(&o,&m,&r)==-3&&
      !r.stopped&&r.master_off&&r.inner_rc==0&&r.shutdown_attempted==1&&
      r.shutdown_rc==-2&&r.shutdown_csts==3&&r.disable_rc==0&&r.disable_csts==0);
 memset(&m,0,sizeof(m));m.disable_timeout=1;assert(n71_admin_once_core(&o,&m,&r)==-3&&!r.stopped&&r.master_off);
 memset(&m,0,sizeof(m));m.fail_master_off=1;assert(n71_admin_once_core(&o,&m,&r)==-3&&!r.stopped&&!r.master_off);
 puts("ADMIN_BME_ORDER_AND_UNSAFE_RETENTION_PASS");return 0;
}
"""
class AdminOnce(unittest.TestCase):
    def test_bme_gates_and_shutdown_failures(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"trial.c";src.write_text(C);binary=Path(d)/"trial"
            q=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"experimental/port0"),str(src),"-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            self.assertIn("ADMIN_BME_ORDER_AND_UNSAFE_RETENTION_PASS",q.stdout)
if __name__=="__main__":unittest.main()
