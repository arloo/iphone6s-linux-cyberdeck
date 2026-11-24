# SPDX-License-Identifier: MIT
"""Bounded admin deletion of empty I/O queues; no device/NAND access."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'experimental/port0'
C=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_io_queue_delete_once_core.h"
struct model { unsigned calls,checks,deny_at,fail_cid,flags; };
static int qualify(void *p) {
 struct model *m=p;return ++m->checks!=m->deny_at;
}
static int submit(void *p,const unsigned char *b,unsigned cid) {
 struct model *m=p;unsigned i;
 assert(cid==4U+m->calls);m->calls++;
 assert(b[0]==(cid==4?0:4) && b[1]==m->flags && b[2]==cid && b[40]==1);
 /* Independent canonical wire checks: ADMIN NSID/PRP/reserved fields zero. */
 for(i=0;i<64;i++) if(i!=0&&i!=1&&i!=2&&i!=40) assert(!b[i]);
 return m->fail_cid==cid?-42:0;
}
int main(void) {
 const struct n71_io_queue_once_ops ops={qualify,submit};
 struct n71_io_queue_delete_result r;
 struct model m;
 unsigned flags_i,i,cid,bit;
 const unsigned flags[]={0,32};
 for(flags_i=0;flags_i<2;flags_i++) {
  memset(&m,0,sizeof(m));m.flags=flags[flags_i];
  assert(!n71_io_queue_delete_once_core(&ops,&m,m.flags,1,&r));
  assert(m.calls==2&&m.checks==2&&r.sq_validated&&r.cq_validated);
  for(i=1;i<=2;i++) {
   memset(&m,0,sizeof(m));m.flags=flags[flags_i];m.deny_at=i;
   assert(n71_io_queue_delete_once_core(&ops,&m,m.flags,1,&r)==-1);
   assert(m.calls==i-1&&!r.cq_attempted&&!r.cq_validated);
  }
  for(cid=4;cid<=5;cid++) {
   memset(&m,0,sizeof(m));m.flags=flags[flags_i];m.fail_cid=cid;
   assert(n71_io_queue_delete_once_core(&ops,&m,m.flags,1,&r)==-42);
   assert(m.calls==cid-3&&!r.cq_validated&&r.sq_validated==(cid==5));
  }
 }
 memset(&m,0,sizeof(m));
 assert(n71_io_queue_delete_once_core(&ops,&m,0,0,&r)==-1&&!m.calls&&!m.checks);
 assert(n71_io_queue_delete_once_core(&ops,&m,1,1,&r)==-1&&!m.calls&&!m.checks);
 assert(n71_io_queue_delete_once_core(NULL,&m,0,1,&r)==-1);
 assert(n71_io_queue_delete_once_core(&ops,&m,0,1,NULL)==-1);
 for(cid=4;cid<=5;cid++) {
  struct n71_s3e_admin_cqe_fields v={1,cid,0,cid};
  for(i=0;i<65536;i++) {v.status=i;assert(n71_io_queue_delete_cqe_valid(i,&v,cid)==(i==1));}
  v.status=1;
  assert(!n71_io_queue_delete_cqe_valid(0,&v,cid));
  v.command_id=cid+1;assert(!n71_io_queue_delete_cqe_valid(1,&v,cid));v.command_id=cid;
  v.sq_id=1;assert(!n71_io_queue_delete_cqe_valid(1,&v,cid));v.sq_id=0;
  v.sq_head=cid-1;assert(!n71_io_queue_delete_cqe_valid(1,&v,cid));
  for(flags_i=0;flags_i<2;flags_i++) {
   unsigned char b[64];
   assert(!n71_io_queue_delete_encode(b,flags[flags_i],cid));
   assert(n71_io_queue_delete_command_valid(b,flags[flags_i],cid));
   for(bit=0;bit<512;bit++) {
    b[bit/8]^=1U<<(bit%8);
    assert(!n71_io_queue_delete_command_valid(b,flags[flags_i],cid));
    b[bit/8]^=1U<<(bit%8);
   }
  }
 }
 {
  unsigned char b[64],before[64];memset(b,0xa5,sizeof(b));memcpy(before,b,sizeof(b));
  for(cid=0;cid<8;cid++) if(cid!=4&&cid!=5) {
   assert(n71_io_queue_delete_encode(b,0,cid)==-1&&!memcmp(b,before,64));
   assert(!n71_io_queue_delete_command_valid(b,0,cid));
  }
  assert(n71_io_queue_delete_encode(b,1,4)==-1&&!memcmp(b,before,64));
  assert(n71_io_queue_delete_encode(NULL,0,4)==-1);
  assert(!n71_io_queue_delete_command_valid(NULL,0,4));
  assert(!n71_io_queue_delete_cqe_valid(1,NULL,4));
 }
 puts("ADMIN_DELETE_SQ_CQ_ORDER_AND_ERROR_STOP_PASS");return 0;
}
"""
class DeleteQueueOnceTests(unittest.TestCase):
    def test_wire_order_faults_and_completion_identity(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'delete.c';source.write_text(C);binary=Path(td)/'delete'
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                              '-I',str(PORT),str(source),'-o',str(binary)],
                             text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(binary)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('ADMIN_DELETE_SQ_CQ_ORDER_AND_ERROR_STOP_PASS',p.stdout)

    def test_opt_in_single_attempt_and_no_backing_release(self):
        pilot=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        init=pilot[pilot.index('static int __init n71_port0_init'):]
        gate='if (ans_io_queue_delete_once && !ans_io_queue_once) return -EPERM;'
        self.assertLess(init.index(gate),init.index('n71_board_gate()'))
        self.assertIn('static bool ans_io_queue_delete_once;',pilot)
        runtime=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        allowed=runtime[runtime.index('static int n71_io_queue_command_allowed'):
                        runtime.index('static int n71_io_queue_submit_admin')]
        delete_sq=allowed[allowed.index('case 4:'):allowed.index('case 5:')]
        delete_cq=allowed[allowed.index('case 5:'):allowed.index('default:')]
        self.assertIn('ans_io_queue_delete_once',delete_sq)
        self.assertIn('n71_io_queue_memory.cq_created',delete_sq)
        self.assertIn('n71_io_queue_memory.sq_created',delete_sq)
        self.assertIn('!n71_io_queue_memory.sq_delete_posted',delete_sq)
        self.assertIn('n71_io_queue_memory.sq_deleted',delete_cq)
        self.assertIn('!n71_io_queue_memory.cq_delete_posted',delete_cq)
        deletion=runtime[runtime.index('static int n71_io_queue_delete_once'):
                         runtime.index('static int n71_io_queue_create_once')]
        self.assertLess(deletion.index('delete_attempted=true'),
                        deletion.index('n71_io_queue_delete_once_core('))
        self.assertIn('if (!rc && ans_io_queue_delete_once) rc=n71_io_queue_delete_once(ctx);',runtime)
        self.assertIn('all_backing_retained=YES dma_release_authorized=NO',deletion)
        for forbidden in ['dma_unmap','free_page','n71_admin_unprepare','n71_s3e_ro_encode_one_sector']:
            self.assertNotIn(forbidden,deletion)
        submit=runtime[runtime.index('static int n71_io_queue_submit_admin'):
                       runtime.index('static int n71_io_queue_delete_once')]
        self.assertLess(submit.index('n71_io_queue_delete_cqe_valid('),
                        submit.index('n71_admin_write(0x1004, cid)'))
        self.assertNotIn('n71_admin_write(0x1008',runtime)
        self.assertNotIn('n71_admin_write(0x100c',runtime)

if __name__=='__main__':unittest.main()
