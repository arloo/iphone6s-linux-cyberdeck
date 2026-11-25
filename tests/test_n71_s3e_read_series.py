# SPDX-License-Identifier: MIT
"""Bounded four-Read plan, disjoint frames, snapshots and failure stops."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'experimental/port0'
CORE=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_read_series_core.h"
static const struct n71_s3e_ro_io_layout layout={
 0x80010000ULL,0x80011000ULL,0x80012000ULL,0x80013000ULL,0x40800000ULL};
struct model {unsigned fail_step,fail_stage,corrupt_pair,late_change;
 unsigned submitted,accepted,snapshots,checks,compares;
 unsigned char data[4][4096],copy[4][4096];};
static int qualified(void *p,unsigned step) {
 struct model *m=p;assert(step==m->snapshots);
 return !(m->fail_stage==9&&m->fail_step==step);
}
static int submit(void *p,unsigned step,const unsigned char *b) {
 struct model *m=p;unsigned i;assert(step==m->submitted);m->submitted++;
 assert(b[0]==2&&b[1]==32&&b[2]==step+1&&b[4]==1);
 assert(n71_ro_get_le64(b+24)==(0x40000000ULL|((unsigned long long)(step+1)<<23)));
 assert(n71_ro_get_le64(b+40)==(step&1)&&!b[48]&&!b[49]);
 for(i=0;i<64;i++)if(i!=0&&i!=1&&i!=2&&i!=4&&!(i>=24&&i<32)&&i!=40)assert(!b[i]);
 return m->fail_step==step&&m->fail_stage==1?-41:0;
}
static int cqe(void *p,unsigned step,unsigned *observed,struct n71_s3e_admin_cqe_fields *v) {
 struct model *m=p;*observed=1;*v=(struct n71_s3e_admin_cqe_fields){1,step+1,1,step+1};
 if(m->fail_step==step&&m->fail_stage==10)v->sq_id=0;
 return m->fail_step==step&&m->fail_stage==2?-42:0;
}
static int ack(void *p,unsigned step) {
 struct model *m=p;return m->fail_step==step&&m->fail_stage==3?-43:0;
}
static int data(void *p,unsigned step) {
 struct model *m=p;
 if(m->fail_step==step&&m->fail_stage==4)return -44;
 memset(m->data[step],(step&1)?0x31:0x17,4096);
 if(m->corrupt_pair&&step==2)m->data[step][50]^=1;
 if(m->late_change&&step==1)m->data[0][5]^=1;
 m->accepted++;return 0;
}
static int snapshot(void *p,unsigned step) {
 struct model *m=p;if(m->fail_step==step&&m->fail_stage==5)return -45;
 memcpy(m->copy[step],m->data[step],4096);m->snapshots++;return 0;
}
static int stable(void *p,unsigned count) {
 struct model *m=p;unsigned i;m->checks++;
 if(m->fail_stage==6&&m->fail_step==count-1)return -46;
 if(m->fail_stage==8&&m->compares)return -48;
 for(i=0;i<count;i++)if(memcmp(m->copy[i],m->data[i],4096))return -47;
 return 0;
}
static int compare(void *p) {
 struct model *m=p;m->compares++;
 if(m->fail_stage==7)return -47;
 return memcmp(m->copy[0],m->copy[2],4096)||memcmp(m->copy[1],m->copy[3],4096)?-47:0;
}
int main(void) {
 const struct n71_read_series_ops ops={qualified,submit,cqe,ack,data,snapshot,stable,compare};
 static struct model m;
 struct n71_read_series_result r;
 unsigned step,stage,flags_i,enabled,id,q,d,single,qf,i,bit;
 const unsigned flags[]={~0U,0,32,1,64},queueflags[]={~0U,0,32};
 for(enabled=0;enabled<2;enabled++)for(id=0;id<2;id++)
 for(q=0;q<2;q++)for(d=0;d<2;d++)for(single=0;single<2;single++)
 for(flags_i=0;flags_i<5;flags_i++)for(qf=0;qf<3;qf++) {
  int expected=enabled?(flags[flags_i]==32&&id&&q&&d&&queueflags[qf]==0&&!single):(flags[flags_i]==~0U);
  assert(!!n71_read_series_mode_valid(enabled,flags[flags_i],id,q,d,queueflags[qf],single)==expected);
 }
 memset(&m,0,sizeof(m));assert(!n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r));
 assert(r.submitted==4&&r.accepted==4&&r.snapshotted==4&&r.stability_checks==5&&r.pairs_valid);
 assert(m.submitted==4&&m.accepted==4&&m.snapshots==4&&m.compares==1);
 for(step=0;step<4;step++)for(stage=1;stage<=6;stage++) {
  memset(&m,0,sizeof(m));m.fail_step=step;m.fail_stage=stage;
  assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-(40+(int)stage));
  assert(m.submitted==step+1&&!r.pairs_valid);
  assert(r.accepted==step+(stage>=5));
 }
 for(step=0;step<4;step++) {
  memset(&m,0,sizeof(m));m.fail_step=step;m.fail_stage=9;
  assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-1&&m.submitted==step);
  memset(&m,0,sizeof(m));m.fail_step=step;m.fail_stage=10;
  assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-2&&m.submitted==step+1&&r.accepted==step);
 }
 for(stage=7;stage<=8;stage++) {
  memset(&m,0,sizeof(m));m.fail_stage=stage;
  assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-(40+(int)stage));
  assert(r.accepted==4&&r.pairs_valid==(stage==8));
 }
 memset(&m,0,sizeof(m));m.corrupt_pair=1;
 assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-47&&!r.pairs_valid&&r.accepted==4);
 memset(&m,0,sizeof(m));m.late_change=1;
 assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,&r)==-47&&m.submitted==2);
 for(step=0;step<4;step++) {
  unsigned char b[64];struct n71_s3e_admin_cqe_fields v={1,step+1,1,step+1};
  assert(!n71_read_series_command(b,step,&layout,15625000,4096,32));
  assert(n71_read_series_command_valid(b,step,&layout,15625000,4096,32));
  for(bit=0;bit<512;bit++) {
   b[bit/8]^=1U<<(bit%8);
   assert(!n71_read_series_command_valid(b,step,&layout,15625000,4096,32));
   b[bit/8]^=1U<<(bit%8);
  }
  for(i=0;i<65536;i++){v.status=i;assert(n71_read_series_cqe_valid(i,&v,step)==(i==1));}
  v.status=1;assert(!n71_read_series_cqe_valid(0,&v,step));
  v.sq_head=0;assert(!n71_read_series_cqe_valid(1,&v,step));
 }
 {unsigned char b[64],old[64];memset(b,0xa5,64);memcpy(old,b,64);
  assert(n71_read_series_command(b,4,&layout,15625000,4096,32)==-1&&!memcmp(b,old,64));
  assert(n71_read_series_command(b,0,&layout,15625000,4096,0)==-1&&!memcmp(b,old,64));
  assert(n71_read_series_command(b,0,&layout,15625000,512,32)==-1&&!memcmp(b,old,64));}
 assert(!n71_read_series_tag(4));assert(!n71_read_series_cqe_valid(1,NULL,0));
 assert(n71_read_series_core(NULL,&m,&layout,15625000,4096,32,&r)==-1);
 assert(n71_read_series_core(&ops,&m,&layout,15625000,4096,32,NULL)==-1);
 puts("FOUR_READ_PLAN_CQE_WIRE_FAULTS_PRIVATE_EQUALITY_AND_LATE_CHANGE_PASS");return 0;
}
"""
STAGE=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_read_series_core.h"
static unsigned char tcb[16384],sgl_data[4][16384],old_tcb[16384],old_sgl[4][16384];
static unsigned char *sgl[4]={sgl_data[0],sgl_data[1],sgl_data[2],sgl_data[3]};
static const struct n71_read_series_frames frames={
 {0x820000000ULL,0x820004000ULL,0x820008000ULL,0x82000c000ULL},
 {0x830000000ULL,0x830004000ULL,0x830008000ULL,0x83000c000ULL}};
static void reset(void) {
 unsigned i;memset(tcb,0,sizeof(tcb));memset(sgl_data,0,sizeof(sgl_data));
 n71_ro_le32(tcb,0x200);n71_ro_le32(tcb+4,1);n71_ro_le32(tcb+8,0x812340);
 n71_ro_le64(tcb+16,0x812340000ULL);
 for(i=640;i<16384;i++)tcb[i]=(unsigned char)(i*17+1);
 for(i=0;i<4;i++)sgl[i]=sgl_data[i];
}
static void preserve(void){memcpy(old_tcb,tcb,16384);memcpy(old_sgl,sgl_data,sizeof(sgl_data));}
static void unchanged(void){assert(!memcmp(old_tcb,tcb,16384)&&!memcmp(old_sgl,sgl_data,sizeof(sgl_data)));}
int main(void) {
 unsigned i,j;struct n71_read_series_frames bad;struct n71_s3e_ro_foreign_range foreign;
 reset();preserve();assert(!n71_read_series_stage(tcb,sgl,&frames,NULL,0));
 assert(!memcmp(tcb,old_tcb,128)&&!memcmp(tcb+640,old_tcb+640,16384-640));
 for(i=0;i<4;i++) {
  unsigned char *slot=tcb+128*(i+1);
  assert(n71_ro_get_le32(slot)==0x200&&n71_ro_get_le32(slot+4)==1);
  assert(n71_ro_get_le32(slot+8)==frames.data[i]>>12);
  assert(n71_ro_get_le64(slot+16)==frames.sgl[i]);
  assert(n71_ro_get_le32(sgl[i])==frames.data[i]>>12);
  for(j=4;j<16384;j++)assert(!sgl[i][j]);
 }
 preserve();assert(n71_read_series_stage(tcb,sgl,&frames,NULL,0)==-1);unchanged();
 for(i=0;i<4;i++)for(j=0;j<128;j++) {
  reset();tcb[128*(i+1)+j]=1;preserve();
  assert(n71_read_series_stage(tcb,sgl,&frames,NULL,0)==-1);unchanged();
 }
 for(i=0;i<4;i++) {
  reset();sgl[i][16383]=1;preserve();
  assert(n71_read_series_stage(tcb,sgl,&frames,NULL,0)==-1);unchanged();
 }
 reset();sgl[1]=sgl[0];preserve();
 assert(n71_read_series_stage(tcb,sgl,&frames,NULL,0)==-1);unchanged();
 reset();sgl[0]=tcb;preserve();
 assert(n71_read_series_stage(tcb,sgl,&frames,NULL,0)==-1);unchanged();
 reset();bad=frames;bad.data[1]=bad.sgl[3];preserve();
 assert(n71_read_series_stage(tcb,sgl,&bad,NULL,0)==-1);unchanged();
 bad=frames;bad.data[0]++;assert(!n71_read_series_frames_valid(&bad,NULL,0));
 bad=frames;bad.sgl[0]=1ULL<<36;assert(!n71_read_series_frames_valid(&bad,NULL,0));
 foreign=(struct n71_s3e_ro_foreign_range){frames.data[2],16384};
 assert(!n71_read_series_frames_valid(&frames,&foreign,1));
 foreign=(struct n71_s3e_ro_foreign_range){0x840000000ULL,0};
 assert(!n71_read_series_frames_valid(&frames,&foreign,1));
 assert(!n71_read_series_frames_valid(&frames,NULL,1));
 assert(!n71_read_series_frames_valid(NULL,NULL,0));
 assert(!n71_read_series_frames_valid(&frames,&foreign,129));
 assert(!n71_read_series_frame(&frames,8));
 puts("FOUR_TAG_SHADOW_ATOMICITY_AND_PHYSICAL_OWNER_EXCLUSIONS_PASS");return 0;
}
"""
class ReadSeriesTests(unittest.TestCase):
    def compile_run(self,code,marker):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'test.c';src.write_text(code);exe=Path(td)/'test'
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                              '-I',str(PORT),str(src),'-o',str(exe)],
                             text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(exe)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn(marker,p.stdout)

    def test_fixed_plan_commands_and_fault_order(self):
        self.compile_run(CORE,'FOUR_READ_PLAN_CQE_WIRE_FAULTS_PRIVATE_EQUALITY_AND_LATE_CHANGE_PASS')

    def test_atomic_four_tag_stage_and_ownership(self):
        self.compile_run(STAGE,'FOUR_TAG_SHADOW_ATOMICITY_AND_PHYSICAL_OWNER_EXCLUSIONS_PASS')

    def test_default_off_exclusive_mode_and_early_hardware_gate(self):
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        init=s[s.index('static int __init n71_port0_init'):]
        self.assertIn('static bool ans_read_series_once;',s)
        self.assertIn('static unsigned int ans_read_series_flags = ~0U;',s)
        self.assertLess(init.index('n71_read_series_mode_valid('),init.index('n71_board_gate()'))
        q=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        self.assertIn('if (!rc && ans_read_series_once) rc=n71_read_series_prepare(ctx);',q)
        create=q[q.index('static int n71_io_queue_create_once'):]
        self.assertLess(create.index('n71_read_series_once(ctx)'),create.index('n71_io_queue_delete_once(ctx)'))
        self.assertIn('(!ans_read_series_once || n71_read_series_completed_safely())',q)

    def test_disjoint_pre_epoch_buffers_and_no_payload_export(self):
        s=(PORT/'n71_s3e_read_series_runtime.h').read_text()
        prep=s[s.index('static int n71_read_series_prepare'):s.index('static int n71_read_series_running')]
        self.assertLess(prep.index('n71_read_series_claim(pa,foreign,count,i)'),
                        prep.index('memset(n71_read_series_memory.page[i],0,PAGE_SIZE)'))
        self.assertIn('if (i<N71_READ_SERIES_DMA_PAGES)',prep)
        self.assertLess(prep.index('n71_read_series_stage('),prep.index('n71_read_series_memory.staged=true'))
        self.assertLess(prep.index('memcmp(live,shadow[0],N71_RO_TCB_BYTES)'),prep.index('n71_read_series_memory.staged=true'))
        self.assertLess(prep.index('memcpy(slot+8'),prep.index('WRITE_ONCE('))
        self.assertIn('free_page((unsigned long)shadow[i])',prep)
        self.assertNotIn('dma_unmap',s)
        self.assertNotIn('free_page((unsigned long)n71_read_series_memory',s)
        for forbidden in ['copy_to_user','filp_open','print_hex_dump','debugfs_create','proc_create']:
            self.assertNotIn(forbidden,s)
        self.assertIn('payload_and_hashes_redacted=YES',s)

    def test_validation_before_ack_and_readonly_retained_observation(self):
        s=(PORT/'n71_s3e_read_series_runtime.h').read_text()
        ack=s[s.index('static int n71_read_series_ack'):s.index('static int n71_read_series_wait_data')]
        self.assertLess(ack.index('n71_read_series_cqe_valid('),ack.index('n71_admin_write(0x100c,step+1U)'))
        submit=s[s.index('static int n71_read_series_submit'):s.index('static int n71_read_series_wait_cqe')]
        self.assertLess(submit.index('n71_read_pair_command_valid('),submit.index('memcpy(sq,command,64)'))
        self.assertLess(submit.index('n71_read_series_memory.issued++'),submit.index('n71_admin_write(0x1008,step+1U)'))
        compare=s[s.index('static int n71_read_series_compare'):s.index('static int n71_read_series_completed_safely')]
        self.assertIn('page[8]',compare);self.assertIn('page[10]',compare)
        self.assertIn('page[9]',compare);self.assertIn('page[11]',compare)
        observer=s[s.index('static void n71_read_series_observe_retained_ro'):]
        for forbidden in ['n71_admin_write(','writel(','dma_unmap','free_page(']:
            self.assertNotIn(forbidden,observer)
        self.assertIn('i<5',observer)
        self.assertIn('dma_quiescence_proven=NO dma_release_authorized=NO',observer)
        owner=(PORT/'n71_s3e_admin_identify_once.h').read_text()
        block=owner[owner.index('static int n71_storage_admin_identify_once'):]
        self.assertLess(block.index('n71_admin_once_core(&o,ctx,&r)'),block.index('n71_read_series_observe_retained_ro(ctx)'))
        self.assertLess(block.index('n71_read_series_observe_retained_ro(ctx)'),block.index('n71_admin_unprepare(ctx)'))

if __name__=='__main__':unittest.main()
