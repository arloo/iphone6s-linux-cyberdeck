# SPDX-License-Identifier: MIT
"""Actual 17-Read core/runtime/helper against independent finite queue models."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_n71_s3e_read_series as prior
import test_n71_s3e_ro_probe as probe
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'experimental/port0'
CORE=r'''
#define N71_CQ_WRAP_PLAN 1
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_read_series_core.h"
static const unsigned slots[17]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,0};
static const unsigned nexts[17]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,0,1};
static const unsigned phases[17]={1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0};
static const struct n71_s3e_ro_io_layout layout={0x80010000ULL,0x80011000ULL,0x80012000ULL,0x80013000ULL,0x40800000ULL};
struct model {unsigned submitted,copied,fail_step,fail_stage,corrupt_repeat,late_change;unsigned char bytes[17][4096],copy[17][4096];};
static int qualified(void *p,unsigned i){struct model *m=p;assert(i==m->copied);return !(m->fail_stage==9&&m->fail_step==i);}
static int submit(void *p,unsigned i,const unsigned char *c){struct model *m=p;assert(i==m->submitted++);assert(c[0]==2&&c[1]==32&&c[2]==i+1&&c[4]==1);assert(n71_ro_get_le64(c+24)==0x40000000ULL+(i+1ULL)*8388608ULL);assert(n71_ro_get_le64(c+40)==4001ULL+(i%2));return m->fail_stage==1&&m->fail_step==i?-41:0;}
static int wait_cqe(void *p,unsigned i,unsigned *s,struct n71_s3e_admin_cqe_fields *v){struct model *m=p;*s=phases[i];*v=(struct n71_s3e_admin_cqe_fields){phases[i],i+1,1,nexts[i]};if(m->fail_stage==10&&m->fail_step==i)v->sq_head=16;return m->fail_stage==2&&m->fail_step==i?-42:0;}
static int ack(void *p,unsigned i){struct model *m=p;return m->fail_stage==3&&m->fail_step==i?-43:0;}
static int data(void *p,unsigned i){struct model *m=p;if(m->fail_stage==4&&m->fail_step==i)return -44;memset(m->bytes[i],i%2?0x31:0x17,4096);if(m->corrupt_repeat&&i==16)m->bytes[i][70]^=1;if(m->late_change&&i==16)m->bytes[0][70]^=1;return 0;}
static int snapshot(void *p,unsigned i){struct model *m=p;if(m->fail_stage==5&&m->fail_step==i)return -45;memcpy(m->copy[i],m->bytes[i],4096);m->copied++;return 0;}
static int stable(void *p,unsigned n){struct model *m=p;unsigned i;if(m->fail_stage==6&&m->fail_step==n-1)return -46;for(i=0;i<n;i++)if(memcmp(m->copy[i],m->bytes[i],4096))return -47;return 0;}
static int compare(void *p){struct model *m=p;unsigned i;for(i=2;i<17;i++)if(memcmp(m->copy[i%2],m->copy[i],4096))return -47;return 0;}
int main(void){struct n71_read_series_ops o={qualified,submit,wait_cqe,ack,data,snapshot,stable,compare};static struct model m;struct n71_read_series_result r;unsigned i,k,stage;
 assert(N71_READ_SERIES_COUNT==17&&N71_RO_Q_ENTRIES==16);
 assert(!n71_read_pair_core(&o,&m,&layout,15625000,4096,32,&r,4001));assert(r.submitted==17&&r.accepted==17&&r.snapshotted==17&&r.stability_checks==18&&r.pairs_valid);
 for(i=0;i<17;i++){struct n71_s3e_admin_cqe_fields v={phases[i],i+1,1,nexts[i]};assert(n71_read_queue_slot(i)==slots[i]&&n71_read_queue_next(i)==nexts[i]&&n71_read_cq_phase(i)==phases[i]);
  for(k=0;k<65536;k++){v.status=k;assert(n71_read_series_cqe_valid(k,&v,i)==(k==phases[i]));}
  v.status=phases[i];v.command_id=0;assert(!n71_read_series_cqe_valid(phases[i],&v,i));v.command_id=i+1;v.sq_head=16;assert(!n71_read_series_cqe_valid(phases[i],&v,i));}
 for(i=0;i<17;i++)for(stage=1;stage<=6;stage++){memset(&m,0,sizeof(m));m.fail_step=i;m.fail_stage=stage;assert(n71_read_pair_core(&o,&m,&layout,15625000,4096,32,&r,4001)==-(40+(int)stage));assert(m.submitted==i+1&&!r.pairs_valid);}
 for(i=0;i<17;i++)for(stage=9;stage<=10;stage++){memset(&m,0,sizeof(m));m.fail_step=i;m.fail_stage=stage;assert(n71_read_pair_core(&o,&m,&layout,15625000,4096,32,&r,4001)==(stage==9?-1:-2));assert(m.submitted==i+(stage==10));}
 memset(&m,0,sizeof(m));m.corrupt_repeat=1;assert(n71_read_pair_core(&o,&m,&layout,15625000,4096,32,&r,4001)==-47&&!r.pairs_valid);
 memset(&m,0,sizeof(m));m.late_change=1;assert(n71_read_pair_core(&o,&m,&layout,15625000,4096,32,&r,4001)==-47&&!r.pairs_valid);
 {unsigned char c[64];assert(n71_read_pair_command(c,17,&layout,15625000,4096,32,4001)==-1);assert(!n71_read_series_tag(17));}
 puts("CQ_WRAP_17_CORE_PHASE_HEAD_CID_FAILURE_AND_RETAINED_DATA_PASS");return 0;}
'''
RUNTIME_PREFIX=r'''
#define N71_CQ_WRAP_PLAN 1
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_read_series_core.h"
typedef unsigned char u8;typedef uint64_t dma_addr_t;
#define PAGE_SIZE 16384
#define DMA_BIDIRECTIONAL 0
#define READ_ONCE(x) (x)
#define le16_to_cpu(x) (x)
struct device {int unused;};
struct nvme_completion {uint64_t result;unsigned short sq_head,sq_id,command_id,status;};
static struct device device;
static struct {struct device *dev;} n71_nvmmu_memory={&device};
static unsigned char sq[PAGE_SIZE];static struct nvme_completion cq[PAGE_SIZE/16];
static struct {void *page[4];dma_addr_t dma[4];} n71_ro_io_dma_memory={{sq,cq,0,0},{1,2,0,0}};
static struct {unsigned long long nsze;unsigned lba_bytes;} n71_admin_memory={15625000,4096};
static const struct n71_s3e_ro_io_layout n71_io_layout={0x80010000ULL,0x80011000ULL,0x80012000ULL,0x80013000ULL,0x40800000ULL};
static struct {bool cq_created,sq_created,sq_delete_posted,cq_delete_posted;} n71_io_queue_memory={true,true,false,false};
static struct {bool prepared,quarantined;unsigned issued,completed;bool seen[17],valid[17],acked[17],data_arrived[17],guard_ok[17],snapshot_valid[17],cq_image_valid[17];unsigned status[17],cq_polls[17],sq_wraps,cq_wraps,reused_slot_checks;struct n71_s3e_admin_cqe_fields cqe[17];struct nvme_completion cq_image[17];} n71_read_series_memory;
static unsigned sq_writes,cq_writes,pending_step,publish_on_sleep,csts=1,last_sq,last_cq;
static bool n71_series_enabled(void){return true;}static unsigned n71_series_flags(void){return 32;}static unsigned n71_series_base(void){return 4001;}
static bool n71_io_queue_qualified(void *p){(void)p;return true;}
static void *memchr_inv(const void *p,int c,size_t n){const unsigned char *s=p;while(n--){if(*s!=(unsigned char)c)return (void *)s;s++;}return 0;}
static void dma_sync_single_for_cpu(struct device *d,dma_addr_t a,unsigned n,int dir){(void)d;(void)a;(void)n;(void)dir;}
static void dma_sync_single_for_device(struct device *d,dma_addr_t a,unsigned n,int dir){(void)d;(void)a;(void)n;(void)dir;}
static void dma_rmb(void){}static void dma_wmb(void){}
static unsigned n71_admin_csts(void *p){(void)p;return csts;}
static void publish(unsigned i){unsigned slot=i<16?i:0;unsigned phase=i<16?1:0;unsigned head=i==15?0:i==16?1:i+1;cq[slot]=(struct nvme_completion){0x1234ULL+i,head,1,i+1,phase};}
static void n71_admin_write(unsigned reg,unsigned value){if(reg==0x1008){sq_writes++;last_sq=value;pending_step=n71_read_series_memory.issued-1;assert(value==(pending_step==15?0:pending_step==16?1:pending_step+1));if(pending_step<16)publish(pending_step);}else{assert(reg==0x100c);cq_writes++;last_cq=value;}}
static void usleep_range(unsigned a,unsigned b){(void)a;(void)b;if(publish_on_sleep){publish(pending_step);publish_on_sleep=0;}}
'''
RUNTIME_MAIN=r'''
static void reset(void){memset(sq,0,sizeof(sq));memset(cq,0,sizeof(cq));memset(&n71_read_series_memory,0,sizeof(n71_read_series_memory));n71_read_series_memory.prepared=true;sq_writes=cq_writes=publish_on_sleep=0;csts=1;}
static void run_prefix(unsigned count){unsigned i;for(i=0;i<count;i++){unsigned char command[64];unsigned status;struct n71_s3e_admin_cqe_fields v;assert(!n71_read_pair_command(command,i,&n71_io_layout,15625000,4096,32,4001));assert(!n71_read_series_submit(0,i,command));if(i==16){assert(cq[0].command_id==1&&cq[0].status==1);publish_on_sleep=1;}assert(!n71_read_series_wait_cqe(0,i,&status,&v));assert(n71_read_series_cqe_valid(status,&v,i));assert(!n71_read_series_ack(0,i));n71_read_series_memory.data_arrived[i]=n71_read_series_memory.guard_ok[i]=n71_read_series_memory.snapshot_valid[i]=true;n71_read_series_memory.completed=i+1;}}
int main(void){unsigned f;reset();run_prefix(17);assert(sq_writes==17&&cq_writes==17&&last_sq==1&&last_cq==1);assert(n71_read_series_memory.sq_wraps==1&&n71_read_series_memory.cq_wraps==1&&n71_read_series_memory.reused_slot_checks==1);assert(cq[0].command_id==17&&cq[0].status==0&&n71_read_series_memory.valid[16]);
 for(f=0;f<4;f++){unsigned char command[64];unsigned before;reset();run_prefix(16);if(f==0)cq[0].result^=1;if(f==1)sq[23]^=1;if(f==2)n71_read_series_memory.snapshot_valid[0]=false;if(f==3)n71_read_series_memory.cqe[15].sq_head=16;assert(!n71_read_pair_command(command,16,&n71_io_layout,15625000,4096,32,4001));before=sq_writes;assert(n71_read_series_submit(0,16,command)==-EPROTO);assert(sq_writes==before);}
 {unsigned char command[64];unsigned status;struct n71_s3e_admin_cqe_fields v;reset();run_prefix(16);assert(!n71_read_pair_command(command,16,&n71_io_layout,15625000,4096,32,4001));assert(!n71_read_series_submit(0,16,command));cq[0].status=0;/* premature phase, stale CID */assert(!n71_read_series_wait_cqe(0,16,&status,&v));assert(!n71_read_series_cqe_valid(status,&v,16));assert(n71_read_series_ack(0,16)==-EPROTO&&cq_writes==16);}
 puts("ACTUAL_RUNTIME_MODULO_DOORBELLS_PHASE0_AND_OLD_IMAGE_GUARDS_PASS");return 0;}
'''
class CQWrapTests(unittest.TestCase):
    def compile_run(self,code):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'case.c').write_text(code)
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(PORT),'-I',str(ROOT),str(d/'case.c'),'-o',str(d/'case')],text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(d/'case')],text=True,capture_output=True,timeout=8);self.assertEqual(p.returncode,0,p.stderr);return p
    def test_actual_17_read_core_with_literal_phase_head_model_and_all_failure_positions(self):self.compile_run(CORE)
    def test_17_disjoint_tag_staging_and_every_dirty_slot_byte(self):
        s=prior.STAGE.replace('#include "n71_s3e_read_series_core.h"','#define N71_CQ_WRAP_PLAN 1\n#include "n71_s3e_read_series_core.h"',1).replace('[4][16384]','[17][16384]')
        start=s.index('static unsigned char *sgl[4]');end=s.index('static void reset',start)
        s=s[:start]+'static unsigned char *sgl[17];\nstatic struct n71_read_series_frames frames;\n'+s[end:]
        s=s.replace('for(i=640','for(i=2304').replace('tcb+640','tcb+2304').replace('old_tcb+640','old_tcb+2304').replace('16384-640','16384-2304').replace('i<4','i<17').replace('for(i=0;i<17;i++)sgl[i]=sgl_data[i];','for(i=0;i<17;i++){sgl[i]=sgl_data[i];frames.data[i]=0x820000000ULL+16384ULL*i;frames.sgl[i]=0x830000000ULL+16384ULL*i;}').replace('n71_read_series_frame(&frames,8)','n71_read_series_frame(&frames,34)')
        self.compile_run(s)
    def test_actual_kernel_runtime_queue_reuse_not_a_parallel_reimplementation(self):
        s=(PORT/'n71_s3e_read_series_runtime.h').read_text();start=s.index('static int n71_read_series_running');end=s.index('static int n71_read_series_wait_data',start);self.compile_run(RUNTIME_PREFIX+s[start:end]+RUNTIME_MAIN)
    def test_new_flag_is_default_off_pre_hardware_and_mixed_plans_fail_compilation(self):
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text();i=s[s.index('static int __init n71_port0_init'):];self.assertIn('static bool ans_ro_cq_wrap_once;',s);self.assertLess(i.index('n71_cq_wrap_mode_valid('),i.index('n71_board_gate()'))
        self.compile_run(r'''#define N71_CQ_WRAP_PLAN 1
#include "n71_s3e_read_series_core.h"
#include <assert.h>
int main(void){unsigned f,b,p,q,t,s,r;for(f=0;f<2;f++)for(b=0;b<2;b++)for(p=0;p<2;p++)for(q=0;q<2;q++)for(t=0;t<2;t++)for(s=0;s<2;s++)for(r=0;r<2;r++)assert(!!n71_cq_wrap_mode_valid(f,b,p,q,4001,t,s,r)==(f&&b&&p&&q&&!t&&!s&&!r));assert(!n71_cq_wrap_mode_valid(1,1,1,1,15624999,0,0,0));return 0;}''')
        with tempfile.TemporaryDirectory() as td:
            p=subprocess.run(['cc','-x','c','-E','-I',str(PORT),'-'],input='#define N71_GPT_FULL_PLAN 1\n#define N71_CQ_WRAP_PLAN 1\n#include "n71_s3e_read_series_core.h"\n',text=True,capture_output=True);self.assertNotEqual(p.returncode,0);self.assertIn('mixed CQ wrap',p.stderr)
    def helper_source(self):
        s=probe.HELPER.replace('step<4&&','step<17&&',1).replace('if(unsafe)return 0;errno=ENOENT;return -1;','if(unsafe){return 0;}\n errno=ENOENT;return -1;',1)
        return s[:s.index('int main(void) {')]
    def test_actual_helper_exact_17_copies_and_safe_summary(self):
        p=self.compile_run(self.helper_source()+r'''int main(void){char *a[]={"probe","--cq-wrap","4000","4999","1",0};base=4001;assert(!helper_main(5,a));assert(reads==19&&opened==2&&created==1&&unlinked==1&&closed==1);return 0;}''')
        self.assertIn('CQ_WRAP_PREAD_PASS completed=17',p.stdout);self.assertIn('descriptor_validation_performed=0 latest_checkpoint_selected=0 filesystem_mounted=0',p.stdout)
        for bad in ['PRIVATE_CHECKPOINT_REFS','0x17','0x31','UUID=','checksum=','hash=']:self.assertNotIn(bad,p.stdout)
    def test_actual_helper_every_failed_read_short_final_and_changed_last_repeat_stop(self):
        s=self.helper_source().replace('if(fail_at==step+1){errno=EIO;return -1;}','if(fail_at==step+1){errno=EIO;return -1;}if(fail_at==18&&step==16)return 2048;',1).replace('if(corrupt&&step==2)','if(corrupt&&step==16)',1)
        p=self.compile_run(s+r'''int main(void){char *a[]={"probe","--cq-wrap","4000","4999","1",0};unsigned j;for(j=1;j<=19;j++){base=4001;opened=reads=created=unlinked=closed=0;fail_at=j==19?0:j;corrupt=j==19;assert(helper_main(5,a)==1);assert(opened==2&&created==1&&unlinked==1&&closed==1);assert(reads==(j>=18?19:j+2));}return 0;}''');self.assertNotIn('CQ_WRAP_PREAD_PASS ',p.stdout)
    def test_no_DMA_release_or_data_export_added_and_last_user_reply_checks_every_repeat(self):
        s=(PORT/'n71_s3e_read_series_runtime.h').read_text();b=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        for bad in ['dma_unmap','free_page((unsigned long)n71_read_series_memory','print_hex_dump','copy_to_user','filp_open']:self.assertNotIn(bad,s)
        self.assertIn('memcmp(cq,&n71_read_series_memory.cq_image[step-N71_RO_Q_ENTRIES]',s);self.assertIn('memcmp(sq,prior,sizeof(prior))',s);self.assertIn('memcmp(n71_ro_block_memory.target[i&1U],n71_ro_block_memory.target[i],4096)',b)
        self.assertIn('N71_READ_SERIES_COUNT>=N71_RO_TCB_COUNT',s);self.assertIn('n71_read_series_memory.status[16]',s)
