# SPDX-License-Identifier: MIT
"""Real Read path contracts tested on host; no phone, firmware or NAND."""
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
#include "n71_s3e_lba0_read_once_core.h"
static const struct n71_s3e_ro_io_layout layout={
 0x80010000ULL,0x80011000ULL,0x80012000ULL,0x80013000ULL,0x40800000ULL};
struct model {unsigned fail,bad_cqe,n;char trace[16];};
static void event(struct model *m,char c){m->trace[m->n++]=c;m->trace[m->n]=0;}
static int qualified(void *p){struct model *m=p;event(m,'Q');return m->fail!=5;}
static int submit(void *p,const unsigned char *b) {
 struct model *m=p;unsigned i;event(m,'S');
 assert(b[0]==2&&b[1]==32&&b[2]==1&&b[4]==1);
 assert(n71_ro_get_le64(b+24)==0x40800000ULL);
 assert(n71_ro_get_le64(b+40)==0&&!b[48]&&!b[49]);
 for(i=0;i<64;i++) if(i!=0&&i!=1&&i!=2&&i!=4&&!(i>=24&&i<32)) assert(!b[i]);
 return m->fail==1?-41:0;
}
static int wait_cqe(void *p,unsigned *observed,struct n71_s3e_admin_cqe_fields *v){
 struct model *m=p;event(m,'W');*observed=1;
 *v=(struct n71_s3e_admin_cqe_fields){1,1,m->bad_cqe?0:1,1};
 return m->fail==2?-42:0;
}
static int ack(void *p){struct model *m=p;event(m,'A');return m->fail==3?-43:0;}
static int data(void *p){struct model *m=p;event(m,'D');return m->fail==4?-44:0;}
int main(void){
 const struct n71_lba0_read_ops ops={qualified,submit,wait_cqe,ack,data};
 struct n71_lba0_read_result result;
 struct model m;
 unsigned enabled,id,q,del,f,qf,i,bit,changed;
 const unsigned flags[]={~0U,0,32,1,64},qflags[]={~0U,0,32};
 unsigned char command[64],before[64],buffer[16384];
 struct n71_s3e_admin_cqe_fields cqe={1,1,1,1};
 for(enabled=0;enabled<2;enabled++)for(id=0;id<2;id++)
 for(q=0;q<2;q++)for(del=0;del<2;del++)
 for(f=0;f<5;f++)for(qf=0;qf<3;qf++) {
  int expected=enabled?(flags[f]==32&&id&&q&&del&&qflags[qf]==0):(flags[f]==~0U);
  assert(!!n71_lba0_mode_valid(enabled,flags[f],id,q,del,qflags[qf])==expected);
 }
 memset(&m,0,sizeof(m));
 assert(!n71_lba0_read_once_core(&ops,&m,&layout,15625000ULL,4096,32,&result));
 assert(!strcmp(m.trace,"QSWAD")&&result.submitted&&result.completion_seen&&
        result.completion_valid&&result.cq_acked&&result.data_arrived);
 for(i=1;i<=5;i++){
  memset(&m,0,sizeof(m));m.fail=i;
  int rc=n71_lba0_read_once_core(&ops,&m,&layout,15625000ULL,4096,32,&result);
  assert(rc==(i==5?-1:-(40+(int)i)));
  assert(!result.data_arrived);
  assert(!strcmp(m.trace,i==1?"QS":i==2?"QSW":i==3?"QSWA":i==4?"QSWAD":"Q"));
 }
 memset(&m,0,sizeof(m));m.bad_cqe=1;
 assert(n71_lba0_read_once_core(&ops,&m,&layout,15625000ULL,4096,32,&result)==-2);
 assert(!strcmp(m.trace,"QSW")&&!result.cq_acked&&!result.data_arrived);
 for(i=0;i<65536;i++){cqe.status=i;assert(n71_lba0_cqe_valid(i,&cqe)==(i==1));}
 cqe.status=1;assert(n71_lba0_cqe_valid(1,&cqe));
 assert(!n71_lba0_cqe_valid(0,&cqe));
 cqe.command_id=2;assert(!n71_lba0_cqe_valid(1,&cqe));cqe.command_id=1;
 cqe.sq_head=0;assert(!n71_lba0_cqe_valid(1,&cqe));cqe.sq_head=1;
 cqe.sq_id=0;assert(!n71_lba0_cqe_valid(1,&cqe));
 assert(!n71_lba0_cqe_valid(1,NULL));
 assert(!n71_lba0_command(command,&layout,15625000ULL,4096,32));
 assert(n71_lba0_command_valid(command,&layout,15625000ULL,4096,32));
 for(bit=0;bit<512;bit++){
  command[bit/8]^=1U<<(bit%8);
  assert(!n71_lba0_command_valid(command,&layout,15625000ULL,4096,32));
  command[bit/8]^=1U<<(bit%8);
 }
 memset(command,0xa5,64);memcpy(before,command,64);
 for(f=0;f<5;f++)if(flags[f]!=32){
  assert(n71_lba0_command(command,&layout,15625000ULL,4096,flags[f])==-1);
  assert(!memcmp(command,before,64));
 }
 assert(n71_lba0_command(command,&layout,15625001ULL,4096,32)==-1);
 assert(n71_lba0_command(command,&layout,15625000ULL,512,32)==-1);
 assert(n71_lba0_command(NULL,&layout,15625000ULL,4096,32)==-1);
 assert(!n71_lba0_command_valid(NULL,&layout,15625000ULL,4096,32));
 {struct n71_s3e_ro_io_layout bad=layout;bad.data_iova=0x40001000ULL;
  assert(n71_lba0_command(command,&bad,15625000ULL,4096,32)==-1);}
 memset(&m,0,sizeof(m));
 assert(n71_lba0_read_once_core(&ops,&m,&layout,15625000ULL,4096,0,&result)==-1&&!m.n);
 assert(n71_lba0_read_once_core(NULL,&m,&layout,15625000ULL,4096,32,&result)==-1);
 assert(n71_lba0_read_once_core(&ops,&m,&layout,15625000ULL,4096,32,NULL)==-1);
 for(i=0;i<0x20000;i++)assert(n71_lba0_invalidate_value_valid(i)==(i==0||i==0x10000));
 n71_lba0_mark(buffer,0x123456789abcdef0ULL);
 assert(n71_lba0_data_state(buffer,0x123456789abcdef0ULL,&changed)==0&&!changed);
 for(i=0;i<511;i++)buffer[i*8]^=1;
 assert(n71_lba0_data_state(buffer,0x123456789abcdef0ULL,&changed)==0&&changed==511);
 buffer[511*8]^=1;
 assert(n71_lba0_data_state(buffer,0x123456789abcdef0ULL,&changed)==1&&changed==512);
 buffer[4096]^=1;
 assert(n71_lba0_data_state(buffer,0x123456789abcdef0ULL,&changed)==-1);
 buffer[4096]^=1;
 assert(n71_lba0_data_state(buffer,0x123456789abcdef0ULL,&changed)==1);
 assert(n71_lba0_data_state(NULL,1,&changed)==-1);
 assert(n71_lba0_data_state(buffer,1,NULL)==-1);
 puts("READ_ONLY_LBA0_WIRE_COMPLETION_AND_GUARD_FAULTS_PASS");return 0;
}
"""
class LBA0ReadTests(unittest.TestCase):
    def test_protocol_mutations_fault_order_and_payload_witness(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'read.c';src.write_text(C);exe=Path(td)/'read'
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                              '-I',str(PORT),str(src),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('READ_ONLY_LBA0_WIRE_COMPLETION_AND_GUARD_FAULTS_PASS',p.stdout)

    def test_read_opt_in_before_hardware_and_completed_read_before_delete(self):
        pilot=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        init=pilot[pilot.index('static int __init n71_port0_init'):]
        self.assertLess(init.index('n71_lba0_mode_valid('),init.index('n71_board_gate()'))
        self.assertLess(init.index('n71_lba0_mode_valid('),init.index('syscon_node_to_regmap'))
        self.assertIn('static bool ans_lba0_read_once;',pilot)
        self.assertIn('static unsigned int ans_lba0_read_flags = ~0U;',pilot)
        runtime=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        self.assertIn('if (!rc && ans_lba0_read_once) rc=n71_lba0_read_prepare(ctx);',runtime)
        create=runtime[runtime.index('static int n71_io_queue_create_once'):]
        self.assertLess(create.index('n71_lba0_read_once(ctx)'),create.index('n71_io_queue_delete_once(ctx)'))
        self.assertIn('(!ans_lba0_read_once || n71_lba0_completed_safely())',runtime)

    def test_pre_epoch_owner_preimages_and_count_last_publication(self):
        s=(PORT/'n71_s3e_lba0_read_runtime.h').read_text()
        owner=s[s.index('static int n71_lba0_invalidate_owned'):
                s.index('static int n71_lba0_invalidate_pre_bme')]
        self.assertIn('READ_ONCE(n71_admin_dma_epoch_latched)',owner)
        self.assertIn('n71_lba0_invalidate_value_valid(',owner)
        self.assertNotIn('n71_admin_qualified(',owner)
        self.assertNotIn('n71_storage_ans_hmb_read(',owner)
        self.assertIn('!n71_admin_reg(0x14) && !n71_admin_reg(0x1c)',owner)
        invalidate=s[s.index('static int n71_lba0_invalidate_pre_bme'):
                     s.index('static int n71_lba0_read_prepare')]
        self.assertIn('writel(0x10000U,(u8 __iomem *)m->nvmmu+4)',invalidate)
        self.assertIn('i<1000',invalidate)
        self.assertIn('if (!value) return n71_io_pre_bme(ctx)',invalidate)
        prep=s[s.index('static int n71_lba0_read_prepare'):
               s.index('static int n71_lba0_read_qualified')]
        self.assertLess(prep.index('n71_ro_io_dma_claim_valid(virt_to_phys(shadow_tcb)'),
                        prep.index('memcpy(shadow_tcb,live_tcb,PAGE_SIZE)'))
        self.assertLess(prep.index('n71_s3e_ro_stage_flatdma_tag1('),
                        prep.index('n71_lba0_memory.staged=true'))
        self.assertLess(prep.index('memcmp(live_tcb,shadow_tcb'),
                        prep.index('n71_lba0_memory.staged=true'))
        self.assertLess(prep.index('memcpy(slot+8,'),prep.index('WRITE_ONCE(*(__le32 *)(slot+4)'))
        self.assertIn('if (shadow_sgl) free_page((unsigned long)shadow_sgl);',prep)
        self.assertIn('if (shadow_tcb) free_page((unsigned long)shadow_tcb);',prep)
        self.assertNotIn('dma_unmap',s)

    def test_only_one_io_doorbell_and_private_data_with_independent_witness(self):
        s=(PORT/'n71_s3e_lba0_read_runtime.h').read_text()
        submit=s[s.index('static int n71_lba0_submit'):s.index('static int n71_lba0_wait_cqe')]
        self.assertLess(submit.index('n71_lba0_command_valid('),submit.index('memcpy(sq,command'))
        self.assertLess(submit.index('n71_lba0_memory.submitted=true'),submit.index('n71_admin_write(0x1008,1)'))
        self.assertEqual(s.count('n71_admin_write(0x1008,1)'),1)
        ack=s[s.index('static int n71_lba0_ack_cq'):s.index('static int n71_lba0_wait_data')]
        self.assertLess(ack.index('n71_lba0_cqe_valid('),ack.index('n71_admin_write(0x100c,1)'))
        data=s[s.index('static int n71_lba0_wait_data'):s.index('static int n71_lba0_completed_safely')]
        self.assertIn('i<1000',data)
        self.assertIn('if (state<0) return -EOVERFLOW;',data)
        self.assertIn('dma_sync_single_for_cpu',data)
        once=s[s.index('static int n71_lba0_read_once'):]
        self.assertLess(once.index('n71_lba0_memory.attempted=true'),
                        once.index('n71_lba0_read_once_core('))
        log=once[once.index('pr_info('):]
        self.assertNotIn('witness_seed',log)
        self.assertNotIn('page[2]',log)
        for forbidden in ['print_hex_dump','copy_to_user','debugfs_create','proc_create','filp_open']:
            self.assertNotIn(forbidden,s)
        self.assertIn('payload_redacted=YES dma_release_authorized=NO',log)
        self.assertIn('n71_lba0_memory.cqe_seen,r.completion_valid,r.cq_acked',log)

if __name__=='__main__':unittest.main()
