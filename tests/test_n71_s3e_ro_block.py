# SPDX-License-Identifier: MIT
"""Real bridge admission, terminal errors, CPU-only targets and lifetime gates."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'experimental/port0'
MODEL=r"""
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "n71_s3e_ro_block_core.h"
static struct n71_ro_block_request request(unsigned step) {
 return (struct n71_ro_block_request){8ULL*(step&1),1,4096,1,0,1,1};
}
int main(void) {
 struct n71_ro_block_flow f,old;
 struct n71_ro_block_request r,bad;
 unsigned step,k,v,enabled,id,q,d,single,series,fi,qi;
 const unsigned flags[]={~0U,0,1,32,64},qflags[]={~0U,0,32};
 for(enabled=0;enabled<2;enabled++)for(id=0;id<2;id++)
 for(q=0;q<2;q++)for(d=0;d<2;d++)for(single=0;single<2;single++)
 for(series=0;series<2;series++)for(fi=0;fi<5;fi++)for(qi=0;qi<3;qi++) {
  int expected=enabled?(flags[fi]==32&&id&&q&&d&&qflags[qi]==0&&!single&&!series):(flags[fi]==~0U);
  assert(!!n71_ro_block_mode_valid(enabled,flags[fi],id,q,d,qflags[qi],single,series)==expected);
 }
 f=(struct n71_ro_block_flow){.active=1};
 for(step=0;step<4;step++) {
  r=request(step);assert(n71_ro_block_admissible(&f,&r));
  for(k=0;k<7;k++)for(v=0;v<64;v++) {
   bad=r;
   switch(k) {
    case 0:bad.is_read=v;break;case 1:bad.bytes=v;break;
    case 2:bad.segments=v;break;case 3:bad.offset=v;break;
    case 4:bad.trusted_bio=v;break;case 5:bad.trusted_page=v;break;
    default:bad.sector=v;break;
   }
   if(!memcmp(&bad,&r,sizeof(r)))continue;
   old=f;assert(n71_ro_block_admit(&f,&bad)==-1&&!memcmp(&f,&old,sizeof(f)));
  }
  {const unsigned long long sectors[]={~0ULL,1ULL<<63,1ULL<<32,125000000ULL,124999999ULL};
   for(k=0;k<sizeof(sectors)/sizeof(sectors[0]);k++) {
    bad=r;bad.sector=sectors[k];old=f;
    assert(n71_ro_block_admit(&f,&bad)==-1&&!memcmp(&f,&old,sizeof(f)));
   }}
  assert(!n71_ro_block_admit(&f,&r));assert(f.pending&&f.admitted==step+1&&f.delivered==step);
  old=f;assert(n71_ro_block_admit(&f,&r)==-1&&!memcmp(&f,&old,sizeof(f)));
  old=f;assert(n71_ro_block_deliver(&f,step+1)==-1&&!memcmp(&f,&old,sizeof(f)));
  assert(!n71_ro_block_deliver(&f,step));assert(!f.pending&&f.delivered==step+1);
  old=f;assert(n71_ro_block_deliver(&f,step)==-1&&!memcmp(&f,&old,sizeof(f)));
 }
 old=f;r=request(4);assert(n71_ro_block_admit(&f,&r)==-1&&!memcmp(&f,&old,sizeof(f)));
 assert(!n71_ro_block_flow_complete(&f));n71_ro_block_close(&f,0);
 assert(n71_ro_block_flow_complete(&f));old=f;
 assert(n71_ro_block_admit(&f,&r)==-1&&!memcmp(&f,&old,sizeof(f)));
 for(step=0;step<4;step++) {
  f=(struct n71_ro_block_flow){.active=1};
  for(k=0;k<step;k++){r=request(k);assert(!n71_ro_block_admit(&f,&r));assert(!n71_ro_block_deliver(&f,k));}
  r=request(step);assert(!n71_ro_block_admit(&f,&r));n71_ro_block_close(&f,1);
  assert(!n71_ro_block_flow_complete(&f)&&f.failed&&f.closed&&!f.pending);
  old=f;assert(n71_ro_block_deliver(&f,step)==-1&&!memcmp(&f,&old,sizeof(f)));
  assert(n71_ro_block_admit(&f,&r)==-1&&!memcmp(&f,&old,sizeof(f)));
 }
 for(k=0;k<6;k++)for(v=0;v<6;v++) {
  f=(struct n71_ro_block_flow){.active=1};r=request(0);
  switch(k){case 0:f.active=v;break;case 1:f.closed=v;break;case 2:f.failed=v;break;
   case 3:f.pending=v;break;case 4:f.admitted=v;break;default:f.delivered=v;break;}
  if(f.active==1&&!f.closed&&!f.failed&&!f.pending&&!f.admitted&&!f.delivered)continue;
  old=f;assert(n71_ro_block_admit(&f,&r)==-1&&!memcmp(&f,&old,sizeof(f)));
 }
 assert(!n71_ro_block_admissible(NULL,&r));assert(!n71_ro_block_admissible(&f,NULL));
 assert(!n71_ro_block_flow_complete(NULL));n71_ro_block_close(NULL,1);
 puts("BLOCK_MODE_ADMISSION_EXHAUSTION_ATOMIC_REJECTION_AND_FAILURE_STOP_PASS");return 0;
}
"""
class ROBlockTests(unittest.TestCase):
    def test_portable_actual_admission_and_terminal_states(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'case.c';src.write_text(MODEL);exe=Path(td)/'case'
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(PORT),str(src),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('BLOCK_MODE_ADMISSION_EXHAUSTION_ATOMIC_REJECTION_AND_FAILURE_STOP_PASS',p.stdout)

    def test_default_off_mutually_exclusive_and_pre_hardware(self):
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        self.assertIn('static bool ans_ro_block_once;',s)
        self.assertIn('static unsigned int ans_ro_block_flags = ~0U;',s)
        init=s[s.index('static int __init n71_port0_init'):]
        self.assertLess(init.index('n71_ro_block_mode_valid('),init.index('n71_board_gate()'))
        q=(PORT/'n71_s3e_io_queue_runtime.h').read_text()
        self.assertIn('(!ans_ro_block_once || n71_ro_block_completed_safely())',q)
        create=q[q.index('static int n71_io_queue_create_once'):]
        self.assertLess(create.index('n71_ro_block_once(ctx)'),create.index('n71_io_queue_delete_once(ctx)'))

    def test_no_write_no_scan_no_userspace_and_no_mmio_in_bio_callback(self):
        s=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        callback=s[s.index('static void n71_ro_block_submit_bio'):s.index('static int n71_ro_block_open')]
        self.assertIn('bio_op(bio)==REQ_OP_READ',callback)
        self.assertIn('bio==n71_ro_block_memory.bio[step]',callback)
        self.assertIn('n71_ro_block_pair_admit(',callback)
        for forbidden in ['n71_admin_write','writel(','n71_read_series_submit','usleep','wait_for_completion','mutex_lock']:
            self.assertNotIn(forbidden,callback)
        opened=s[s.index('static int n71_ro_block_open'):s.index('static const struct block_device_operations')]
        self.assertIn('return -EACCES;',opened)
        self.assertIn('GENHD_FL_NO_PART',s)
        self.assertIn('set_disk_ro(n71_ro_block_memory.disk,true)',s)
        for forbidden in ['REQ_OP_WRITE','REQ_OP_DISCARD','copy_to_user','print_hex_dump','debugfs_create','proc_create','dma_unmap','dma_map_single']:
            self.assertNotIn(forbidden,s)

    def test_cpu_targets_pre_epoch_owned_and_completion_after_data_stability(self):
        s=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        prep=s[s.index('static int n71_ro_block_prepare'):s.index('static int n71_ro_block_client')]
        self.assertIn('!n71_io_pre_bme(ctx)',prep)
        self.assertLess(prep.index('n71_read_series_claim('),prep.index('memset(n71_ro_block_memory.target[i],0,PAGE_SIZE)'))
        self.assertIn('bio_add_page(bio,virt_to_page(n71_ro_block_memory.target[i])',prep)
        delivery=s[s.index('static int n71_ro_block_stable'):s.index('static int n71_ro_block_completed_safely')]
        self.assertLess(delivery.index('n71_read_series_stable('),delivery.index('memcpy(n71_ro_block_memory.target[step]'))
        self.assertLess(delivery.index('n71_ro_block_deliver('),delivery.index('bio_endio(bio)'))
        self.assertNotRegex(s,r'\bfree_page\s*\(')
        self.assertIn('msecs_to_jiffies(8000)',s)

    def test_error_closes_admission_completes_bio_joins_then_releases_software(self):
        s=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        run=s[s.index('static int n71_ro_block_once'):]
        self.assertLess(run.index('n71_ro_block_close('),run.index('if (pending) bio_io_error(pending)'))
        self.assertLess(run.index('if (pending) bio_io_error(pending)'),run.index('kthread_stop('))
        self.assertLess(run.index('kthread_stop('),run.rindex('n71_ro_block_release_software()'))
        self.assertIn('while (!kthread_should_stop()) schedule_timeout_interruptible(HZ)',s)
        self.assertIn('if (rc) n71_read_series_memory.series_ok=false;',s)
        self.assertIn('n71_read_series_completed_safely()',s)
        release=s[s.index('static void n71_ro_block_release_software'):s.index('static int n71_ro_block_prepare')]
        self.assertIn('bio_put(',release);self.assertIn('del_gendisk(',release)
        self.assertNotIn('free_page(',release)

if __name__=='__main__':unittest.main()
