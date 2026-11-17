# SPDX-License-Identifier: MIT
"""Check bounded S3E bus2 routing, reads and mandatory rollback."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_endpoint_cfg_ro.h"
struct model {
 unsigned id,root_command,buses,endpoint[3],writes,reads;
 int fail_target,fail_restore,lose_ready;
};
static int ready(void *ctx) {
 struct model *m=ctx;
 return !(m->lose_ready && m->reads);
}
static unsigned root_read(void *ctx,unsigned off) {
 struct model *m=ctx;
 switch(off) {
 case 0:return m->id;
 case 4:return m->root_command;
 case 8:return 0x06040001;
 case 0x18:return m->buses;
 default:assert(0);return 0;
 }
}
static void bus_write(void *ctx,unsigned value) {
 struct model *m=ctx;m->writes++;
 assert(value==0x9a020200U || value==0x9a000000U);
 if(m->fail_target && value==0x9a020200U)return;
 if(m->fail_restore && value==0x9a000000U)return;
 m->buses=value;
}
static unsigned endpoint_read(void *ctx,unsigned off) {
 struct model *m=ctx;
 assert(m->buses==0x9a020200U && off<=8 && !(off&3));
 m->reads++;
 return m->endpoint[off/4];
}
static void init(struct model *m) {
 memset(m,0,sizeof(*m));m->id=0x1003106b;m->buses=0x9a000000;
 m->endpoint[0]=0x2002106b;m->endpoint[2]=0x01800201;
}
int main(void) {
 struct model m;struct n71_s3e_cfg_result r;int rc;
 const struct n71_s3e_cfg_ops o={
  .ready=ready,.root_read=root_read,.root_bus_write=bus_write,
  .endpoint_read=endpoint_read
 };
 init(&m);rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(!rc && r.restored && r.reads==3 && m.writes==2 && m.buses==0x9a000000U);
 init(&m);m.endpoint[0]=0xffffffffU;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-2 && r.restored && r.reads==1 && m.buses==0x9a000000U);
 init(&m);m.endpoint[1]=4;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-4 && r.restored && r.reads==2 && m.buses==0x9a000000U);
 init(&m);m.id=0x1004106b;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-1 && !m.writes && !m.reads);
 init(&m);m.buses=0x9a010100;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-1 && !m.writes && !m.reads);
 init(&m);m.fail_target=1;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-1 && r.restored && !m.reads);
 init(&m);m.fail_restore=1;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-3 && !r.restored && m.buses==0x9a020200U);
 init(&m);m.lose_ready=1;rc=n71_s3e_endpoint_cfg_trial(&o,&m,&r);
 assert(rc==-1 && r.restored && m.reads==1 && m.buses==0x9a000000U);
 puts("S3E_CONFIG_READ_AND_ROUTE_ROLLBACK_CASES_PASS");
 return 0;
}
"""
class S3ERoutingRollback(unittest.TestCase):
    def test_identity_read_errors_and_route_retention(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"trial.c";source.write_text(C)
            binary=Path(d)/"trial"
            r=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
                "-I",str(ROOT/"experimental/port0"),str(source),"-o",str(binary)],
                capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("S3E_CONFIG_READ_AND_ROUTE_ROLLBACK_CASES_PASS",r.stdout)
if __name__=="__main__":
    unittest.main()
