# SPDX-License-Identifier: MIT
"""Queue-only transport fault tests; no firmware, device or NAND access."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'experimental/port0'
C = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_io_queue_once_core.h"
static const struct n71_s3e_ro_io_layout good = {
 0x80010000ULL, 0x80011000ULL, 0x80012000ULL, 0x80013000ULL, 0x40800000ULL
};
struct model { unsigned calls, checks, deny_at, fail_cid, flags; };
static int qualified(void *ctx) {
 struct model *m=ctx; return ++m->checks != m->deny_at;
}
static int submit(void *ctx,const unsigned char *b,unsigned cid) {
 struct model *m=ctx; unsigned i;
 assert(cid==m->calls+2); m->calls++;
 /* Independent wire/domain assertions: both commands are admin QID0,
  * CQ opcode5 precedes SQ opcode1. No NVM READ/WRITE is submitted. */
 assert(b[0]==(cid==2?5:1) && b[1]==m->flags);
 assert(b[2]==cid && !b[3] && !b[4] && !b[5] && !b[6] && !b[7]);
 assert(n71_ro_get_le64(b+24)==(cid==2?0x80013000ULL:0x80012000ULL));
 assert(b[40]==1 && !b[41] && b[42]==15 && !b[43]);
 assert(b[44]==1 && !b[45] && b[46]==(cid==3?1:0) && !b[47]);
 for(i=0;i<64;i++)
  if(i!=0 && i!=1 && i!=2 && !(i>=24&&i<32) && !(i>=40&&i<48)) assert(!b[i]);
 return m->fail_cid==cid?-42:0;
}
int main(void) {
 const struct n71_io_queue_once_ops ops={qualified,submit};
 struct n71_io_queue_once_result r;
 struct model m;
 unsigned flags_i, enabled, identify, retire, late, i, bit, cid;
 const unsigned flags[]={~0U,0,32,1,64};
 for(enabled=0;enabled<2;enabled++) for(identify=0;identify<2;identify++)
 for(retire=0;retire<2;retire++) for(late=0;late<2;late++)
 for(flags_i=0;flags_i<5;flags_i++) {
  unsigned f=flags[flags_i];
  int expected=enabled?(identify&&!retire&&!late&&(f==0||f==32)):(f==~0U);
  assert(!!n71_io_queue_mode_valid(enabled,identify,f,retire,late)==expected);
 }
 for(flags_i=1;flags_i<=2;flags_i++) {
  memset(&m,0,sizeof(m));m.flags=flags[flags_i];
  assert(!n71_io_queue_once_core(&ops,&m,&good,m.flags,&r));
  assert(m.calls==2&&m.checks==2&&r.cq_validated&&r.sq_validated);
  for(i=1;i<=2;i++) {
   memset(&m,0,sizeof(m));m.flags=flags[flags_i];m.deny_at=i;
   assert(n71_io_queue_once_core(&ops,&m,&good,m.flags,&r)==-1);
   assert(m.calls==i-1 && !r.sq_attempted && !r.sq_validated);
  }
  for(cid=2;cid<=3;cid++) {
   memset(&m,0,sizeof(m));m.flags=flags[flags_i];m.fail_cid=cid;
   assert(n71_io_queue_once_core(&ops,&m,&good,m.flags,&r)==-42);
   assert(m.calls==cid-1 && !r.sq_validated);
   assert(r.cq_validated==(cid==3));
  }
 }
 for(i=0;i<32;i++) for(cid=0;cid<16;cid++) {
  assert(!!n71_io_queue_capability_valid(i,0x20U|cid,0x10001)==(i>=15&&cid==0));
  assert(!n71_io_queue_capability_valid(i,cid,0x10001));
  assert(!n71_io_queue_capability_valid(i,0x10020U|cid,0x10001));
  assert(!n71_io_queue_capability_valid(i,0x20U|cid,0x20000));
 }
 memset(&m,0,sizeof(m));
 assert(n71_io_queue_once_core(&ops,&m,&good,1,&r)==-1&&!m.calls&&!m.checks);
 {struct n71_s3e_ro_io_layout bad=good;bad.io_sq_iova=good.admin_sq_iova;
  assert(n71_io_queue_once_core(&ops,&m,&bad,0,&r)==-1&&!m.calls&&!m.checks);}
 assert(n71_io_queue_once_core(NULL,&m,&good,0,&r)==-1);
 assert(n71_io_queue_once_core(&ops,&m,&good,0,NULL)==-1);
 for(cid=2;cid<=3;cid++) {
  struct n71_s3e_admin_cqe_fields v={1,cid,0,cid};
  for(i=0;i<65536;i++) {v.status=i;assert(n71_io_queue_cqe_valid(i,&v,cid)==(i==1));}
  v.status=1;assert(n71_io_queue_cqe_valid(1,&v,cid));
  assert(!n71_io_queue_cqe_valid(0,&v,cid));
  v.command_id=cid+1;assert(!n71_io_queue_cqe_valid(1,&v,cid));v.command_id=cid;
  v.sq_id=1;assert(!n71_io_queue_cqe_valid(1,&v,cid));v.sq_id=0;
  v.sq_head=cid-1;assert(!n71_io_queue_cqe_valid(1,&v,cid));
  for(flags_i=1;flags_i<=2;flags_i++) {
   unsigned char b[64];unsigned f=flags[flags_i];
   assert(!(cid==2?n71_s3e_ro_encode_create_cq(b,&good):n71_s3e_ro_encode_create_sq(b,&good)));
   b[1]=f;assert(n71_io_queue_command_valid(b,&good,f,cid));
   for(bit=0;bit<512;bit++) {
    b[bit/8]^=1U<<(bit%8);
    assert(!n71_io_queue_command_valid(b,&good,f,cid));
    b[bit/8]^=1U<<(bit%8);
   }
   assert(!n71_io_queue_command_valid(b,&good,f,1));
   assert(!n71_io_queue_command_valid(b,&good,1,cid));
  }
 }
 assert(!n71_io_queue_cqe_valid(1,NULL,2));
 puts("QUEUE_ONLY_ORDER_FAULTS_131072_STATUS_CASES_2048_WIRE_MUTATIONS_PASS");
 return 0;
}
"""
class IOQueueOnceTests(unittest.TestCase):
    def test_queue_protocol_order_failure_and_command_identity(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'queue.c';source.write_text(C);binary=Path(td)/'queue'
            r=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                              '-I',str(PORT),str(source),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('2048_WIRE_MUTATIONS_PASS',r.stdout)

    def test_runtime_opt_in_checked_before_hardware(self):
        pilot=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        init=pilot[pilot.index('static int __init n71_port0_init'):]
        self.assertIn('static bool ans_io_queue_once;',pilot)
        self.assertIn('static unsigned int ans_io_queue_flags = ~0U;',pilot)
        self.assertLess(init.index('n71_io_queue_mode_valid('),init.index('n71_board_gate()'))
        self.assertLess(init.index('n71_io_queue_mode_valid('),init.index('syscon_node_to_regmap'))
        owner=(PORT/'n71_s3e_admin_identify_once.h').read_text()
        identify=owner[owner.index('static int n71_admin_identify_ns1'):owner.index('static int n71_admin_prepare')]
        self.assertLess(identify.index('namespace_validated=true'),identify.index('n71_io_queue_create_once(ctx)'))
        self.assertIn('if (ans_io_queue_once) return n71_io_queue_create_once(ctx);',identify)
        self.assertIn('if (ans_io_queue_once) {\n        rc=n71_io_queue_prepare(ctx);',owner)

    def test_shadow_ownership_and_publish_precede_dma_epoch(self):
        s=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        prepare=s[s.index('static int n71_io_queue_prepare'):s.index('static int n71_io_queue_qualified')]
        self.assertLess(prepare.index('n71_ro_io_dma_claim_valid('),prepare.index('memcpy(shadow[sid]'))
        self.assertLess(prepare.index('n71_s3e_ro_stage_io_queue_l2(shadow'),prepare.index('n71_io_queue_memory.mapped = true'))
        self.assertLess(prepare.index('n71_io_queue_memory.mapped = true'),prepare.index('memcpy(n71_admin_memory.page'))
        self.assertIn('!READ_ONCE(n71_admin_dma_epoch_latched)',s)
        self.assertIn('!n71_admin_reg(0x14)',s)
        self.assertIn('!n71_admin_reg(0x1c)',s)
        self.assertIn('n71_ro_io_dma_memory.quarantined = true;',prepare)
        self.assertNotIn('n71_s3e_ro_encode_one_sector(',s)
        self.assertNotIn('n71_s3e_ro_stage_flatdma_tag1(',s)
        self.assertNotIn('dma_unmap_single(',s)
        self.assertIn('free_page((unsigned long)shadow[sid])',s)
        self.assertNotIn('free_page((unsigned long)n71_ro_io_dma_memory',s)

    def test_ack_is_after_cqe_validation_and_all_dma_is_retained(self):
        s=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        submit=s[s.index('static int n71_io_queue_submit_admin'):s.index('static int n71_io_queue_create_once')]
        self.assertLess(submit.index('n71_io_queue_cqe_valid('),submit.index('n71_admin_write(0x1004, cid)'))
        self.assertIn('i < 5000',submit)
        self.assertIn('if (complete) return -EPROTO',submit)
        create=s[s.index('static int n71_io_queue_create_once'):]
        self.assertLess(create.index('n71_io_queue_memory.attempted = true'),create.index('n71_io_queue_once_core('))
        owner=(PORT/'n71_s3e_admin_identify_once.h').read_text()
        retention=owner[owner.index('if (ans_io_queue_once && n71_ro_io_dma_memory.ready)'):]
        self.assertLess(retention.index('n71_ro_io_dma_memory.quarantined=true'),retention.index('n71_admin_unprepare(ctx)'))
        self.assertLess(retention.index('return -3;'),retention.index('n71_admin_unprepare(ctx)'))
        self.assertIn('nvm_read_submitted=NO nvm_write_submitted=NO',s)
if __name__ == '__main__':
    unittest.main()
