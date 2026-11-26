# SPDX-License-Identifier: MIT
"""Actual portable admission plus actual userspace helper with mocked syscalls."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'experimental/port0'
CORE=r"""
#include <assert.h>
#include "n71_s3e_ro_block_core.h"
int main(void) {
 unsigned b,step,active,failed,k;
 unsigned bases[]={0,15624998,1,15624999,~0U};
 unsigned long long badbytes[]={0,1,512,4095,4097,16384,~0ULL};
 assert(n71_ro_probe_mode_valid(0,0));
 assert(!n71_ro_probe_mode_valid(1,0));assert(n71_ro_probe_mode_valid(1,1));
 for(b=0;b<5;b++)for(step=0;step<6;step++)
 for(active=0;active<3;active++)for(failed=0;failed<2;failed++) {
  unsigned long long off=4096ULL*(bases[b]+(step&1U));
  int ok=b<3&&step<4&&active==1&&!failed;
  assert(!!n71_ro_probe_request_valid(active,failed,step,bases[b],off,4096)==ok);
  for(k=0;k<sizeof(badbytes)/sizeof(badbytes[0]);k++)
   assert(!n71_ro_probe_request_valid(active,failed,step,bases[b],off,badbytes[k]));
  assert(!n71_ro_probe_request_valid(active,failed,step,bases[b],off+1,4096));
  assert(!n71_ro_probe_request_valid(active,failed,step,bases[b],~0ULL,4096));
  assert(!n71_ro_probe_request_valid(active,failed,step,bases[b],1ULL<<63,4096));
 }
 return 0;
}
"""
HELPER=r"""
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>
static unsigned base,opened,reads,created,unlinked,closed,fail_at,corrupt,unsafe,regular;
static FILE *fake_fopen(const char *p,const char *mode) {
 FILE *f;assert(!strcmp(p,"/proc/devices")&&!strcmp(mode,"r"));
 f=tmpfile();assert(f);fputs("Character devices:\n240 n71nand_probe\n",f);rewind(f);return f;
}
static int fake_lstat(const char *p,struct stat *s) {
 (void)s;assert(!strcmp(p,"/dev/n71nand-probe"));
 if(unsafe)return 0;errno=ENOENT;return -1;
}
static int fake_mknod(const char *p,mode_t mode,dev_t dev) {
 assert(!strcmp(p,"/dev/n71nand-probe")&&mode==(S_IFCHR|0600)&&major(dev)==240&&minor(dev)==0);
 created++;return 0;
}
static int fake_open(const char *p,int flags,...) {
 assert(!strcmp(p,"/dev/n71nand-probe"));opened++;
 if((flags&O_ACCMODE)==O_RDWR){errno=EACCES;return -1;}
 assert((flags&O_NOFOLLOW)&&(flags&O_CLOEXEC));return 42;
}
static int fake_fstat(int fd,struct stat *s) {
 assert(fd==42);memset(s,0,sizeof(*s));s->st_mode=(regular?S_IFREG:S_IFCHR)|0600;s->st_rdev=makedev(240,0);return 0;
}
static ssize_t fake_pread(int fd,void *out,size_t n,off_t off) {
 unsigned step;assert(fd==42);reads++;
 if(reads==1){assert(n==1&&off==(off_t)base*4096);errno=EINVAL;return -1;}
 if(reads==2){assert(n==4096&&off==(off_t)(base+1U)*4096);errno=EINVAL;return -1;}
 step=reads-3;assert(step<4&&n==4096&&off==(off_t)(base+(step&1U))*4096);
 if(fail_at==step+1){errno=EIO;return -1;}
 memset(out,(step&1U)?0x31:0x17,4096);
 if(corrupt&&step==2)((unsigned char *)out)[70]^=1;
 return 4096;
}
static int fake_unlink(const char *p){assert(!strcmp(p,"/dev/n71nand-probe"));unlinked++;return 0;}
static int fake_close(int fd){assert(fd==42);closed++;return 0;}
static uid_t fake_geteuid(void){return 0;}
#define fopen fake_fopen
#define lstat fake_lstat
#define mknod fake_mknod
#define open fake_open
#define fstat fake_fstat
#define pread fake_pread
#define unlink fake_unlink
#define close fake_close
#define geteuid fake_geteuid
#define main helper_main
#include "experimental/storage/n71-nand-private-probe.c"
#undef main
int main(void) {
 unsigned tail,j;
 char *args[]={"probe","--initial",NULL};
 for(tail=0;tail<2;tail++)for(j=0;j<8;j++) {
  int rc;opened=reads=created=unlinked=closed=0;fail_at=corrupt=unsafe=regular=0;
  base=tail?15624998U:0U;args[1]=tail?"--tail":"--initial";
  if(j>=1&&j<=4)fail_at=j;if(j==5)corrupt=1;if(j==6)unsafe=1;if(j==7)regular=1;
  rc=helper_main(2,args);
  assert(rc==(j==0?0:j==6?2:1));
  if(unsafe){assert(!opened&&!reads&&!created&&!unlinked);continue;}
  assert(opened==2&&created==1&&unlinked==1&&closed==1);
  assert(reads==(regular?0:fail_at?2+fail_at:6));
 }
 return 0;
}
"""

HANDLER=r"""
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <sys/types.h>
#include "n71_s3e_ro_block_core.h"
#define __user
#define THIS_MODULE NULL
#define CAP_SYS_RAWIO 1
#define FMODE_WRITE 2
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define msecs_to_jiffies(x) (x)
#define default_llseek NULL
#define pr_info(...) ((void)0)
struct completion {unsigned id,done;};
struct mutex {int locked;};
typedef struct {int n;} atomic_t;
struct inode {int unused;};
struct file {int f_mode;};
struct file_operations {void *owner;int (*open)(struct inode *,struct file *);
 ssize_t (*read)(struct file *,char *,size_t,loff_t *);void *llseek;};
static unsigned seq,capability=1,request_events,unregistered;
static int reply_timeout,copy_fail,reply_error,close_in_copy;
static bool ans_ro_probe_once=true;
static unsigned n71_series_base(void){return 0;}
static struct {void *target[4];struct n71_ro_block_flow flow;} n71_ro_block_memory;
static void init_completion(struct completion *c){c->id=++seq;c->done=0;}
static void reinit_completion(struct completion *c){c->done=0;}
static void complete(struct completion *c){c->done++;if(c->id==1)request_events++;}
static void mutex_init(struct mutex *m){m->locked=0;}
static int mutex_trylock(struct mutex *m){if(m->locked)return 0;m->locked=1;return 1;}
static void mutex_unlock(struct mutex *m){m->locked=0;}
static void atomic_set(atomic_t *a,int v){a->n=v;}
static int atomic_cmpxchg(atomic_t *a,int old,int v){int n=a->n;if(n==old)a->n=v;return n;}
static int capable(int c){(void)c;return capability;}
static int kthread_should_stop(void){return 0;}
static int register_chrdev(unsigned n,const char *s,const struct file_operations *f){(void)n;(void)s;(void)f;return 240;}
static void unregister_chrdev(unsigned n,const char *s){assert(n==240&&!strcmp(s,"n71nand_probe"));unregistered++;}
static unsigned long wait_for_completion_timeout(struct completion *,unsigned long);
static unsigned long copy_to_user(void *,const void *,unsigned long);
#include "n71_s3e_ro_probe_runtime.h"
static unsigned long wait_for_completion_timeout(struct completion *c,unsigned long ticks) {
 assert(ticks==8000);
 if(c->id==2){if(reply_timeout)return 0;n71_ro_probe.reply_rc=reply_error;return 1;}
 return c->done!=0;
}
static unsigned long copy_to_user(void *out,const void *in,unsigned long n){
 if(close_in_copy)n71_ro_probe_close(0);
 if(copy_fail)return n;
 memcpy(out,in,n);return 0;
}
static unsigned char targets[4][16384];
static void reset(void){
 unsigned i;memset(&n71_ro_probe,0,sizeof(n71_ro_probe));
 seq=request_events=unregistered=0;reply_timeout=copy_fail=reply_error=close_in_copy=0;
 capability=1;ans_ro_probe_once=true;
 for(i=0;i<4;i++){memset(targets[i],(i&1)?0x31:0x17,4096);n71_ro_block_memory.target[i]=targets[i];}
 n71_ro_probe_prepare();assert(!n71_ro_probe_start());
}
int main(void){
 struct inode inode={0};struct file file={0};char out[4096];loff_t off;unsigned i;
 reset();assert(n71_ro_probe_wait(0)==-ETIMEDOUT);capability=0;assert(n71_ro_probe_open(&inode,&file)==-EACCES);capability=1;
 file.f_mode=FMODE_WRITE;assert(n71_ro_probe_open(&inode,&file)==-EACCES);file.f_mode=0;
 assert(!n71_ro_probe_open(&inode,&file));assert(n71_ro_probe_open(&inode,&file)==-EACCES);
 off=0;assert(n71_ro_probe_read(&file,out,1,&off)==-EINVAL&&!request_events);
 off=4096;assert(n71_ro_probe_read(&file,out,4096,&off)==-EINVAL&&!request_events);
 n71_ro_probe.read_lock.locked=1;assert(n71_ro_probe_read(&file,out,4096,&off)==-EBUSY&&!request_events);n71_ro_probe.read_lock.locked=0;
 for(i=0;i<4;i++){off=4096*(i&1);assert(n71_ro_probe_read(&file,out,4096,&off)==4096);assert(!memcmp(out,targets[i],4096));}
 assert(n71_ro_probe.copied==4&&request_events==4&&!n71_ro_probe_finish(0));
 off=0;assert(n71_ro_probe_read(&file,out,4096,&off)==-EINVAL&&request_events==4);
 n71_ro_probe_close(0);assert(unregistered==1&&!n71_ro_probe.active);
 assert(n71_ro_probe_read(&file,out,4096,&off)==-EINVAL);
 for(i=0;i<3;i++){
  reset();reply_timeout=i==0;copy_fail=i==1;reply_error=i==2?-EIO:0;
  off=0;assert(n71_ro_probe_read(&file,out,4096,&off)==(i==0?-ETIMEDOUT:i==1?-EFAULT:-EIO));
  assert(n71_ro_probe.failed&&!n71_ro_probe.copied&&n71_ro_probe.consumed.done);
  assert(n71_ro_probe_finish(-EIO)==-EIO);n71_ro_probe_close(1);
  assert(unregistered==1&&n71_ro_block_memory.target[0]==targets[0]);
 }
 reset();assert(n71_ro_probe_finish(0)==-EIO&&n71_ro_probe.failed);n71_ro_probe_close(1);
 reset();close_in_copy=1;off=0;
 assert(n71_ro_probe_read(&file,out,4096,&off)==4096&&!n71_ro_probe.active);
 assert(!memcmp(out,targets[0],4096)&&n71_ro_probe.copied==1&&unregistered==1);
 assert(n71_ro_probe_read(&file,out,4096,&off)==-EINVAL);
 return 0;
}
"""

class ProbeTests(unittest.TestCase):
    def compile_run(self, text):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'case.c';exe=Path(td)/'case';src.write_text(text)
            p=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(PORT),'-I',str(ROOT),str(src),'-o',str(exe)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([str(exe)],text=True,capture_output=True,timeout=4)
            self.assertEqual(p.returncode,0,p.stderr)
            return p
    def test_actual_kernel_probe_handlers_faults_close_and_retained_target_lifetime(self):
        self.compile_run(HANDLER)
    def test_real_probe_policy_initial_tail_malformed_and_exhausted(self):
        self.compile_run(CORE)
    def test_actual_helper_private_data_correct_offsets_failures_no_retry_and_cleanup(self):
        p=self.compile_run(HELPER)
        self.assertEqual(p.stdout.count('PRIVATE_PREAD_PASS completed=4'),2)
        self.assertNotIn('0x17',p.stdout);self.assertNotIn('sha256',p.stdout)
    def test_helper_uses_device_filesystem_and_reports_open_errno(self):
        s=(ROOT/'experimental/storage/n71-nand-private-probe.c').read_text()
        self.assertIn('const char *path="/dev/n71nand-probe"',s)
        self.assertNotIn('/run/n71nand-probe',s)
        self.assertIn('PRIVATE_CHAR_OPEN_FAILED errno=%d',s)
    def test_probe_default_off_pre_hardware_and_block_opens_still_denied(self):
        s=(PORT/'n71_s3e_p0_asserted_reset_rootstart.c').read_text()
        self.assertIn('static bool ans_ro_probe_once;',s)
        init=s[s.index('static int __init n71_port0_init'):]
        self.assertLess(init.index('n71_ro_probe_mode_valid('),init.index('n71_board_gate()'))
        s=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        op=s[s.index('static int n71_ro_block_open'):s.index('static const struct block_device_operations')]
        self.assertIn('return -EACCES',op)
    def test_user_target_is_retained_and_software_bios_are_never_exposed(self):
        s=(PORT/'n71_s3e_ro_probe_runtime.h').read_text()
        self.assertIn('copy_to_user(out,n71_ro_block_memory.target[step],4096)',s)
        for bad in ['dma_map','dma_unmap','free_page','bio_put','mmap=', '.write=', 'print_hex_dump']:
            self.assertNotIn(bad,s)
        self.assertIn('capable(CAP_SYS_RAWIO)',s)
        self.assertIn('file->f_mode & FMODE_WRITE',s)
        self.assertIn('atomic_cmpxchg(&n71_ro_probe.opened,0,1)',s)
        self.assertLess(s.index('if (copy_to_user('),s.index('WRITE_ONCE(n71_ro_probe.copied,step+1U)'))
    def test_finish_requires_all_user_copies_and_close_wakes_before_join(self):
        s=(PORT/'n71_s3e_ro_probe_runtime.h').read_text()
        self.assertIn('READ_ONCE(n71_ro_probe.copied)!=N71_READ_SERIES_COUNT',s)
        self.assertIn('msecs_to_jiffies(8000)',s)
        self.assertIn('complete(&n71_ro_probe.request)',s)
        self.assertIn('unregister_chrdev(',s)
        s=(PORT/'n71_s3e_ro_block_runtime.h').read_text()
        client=s[s.index('static int n71_ro_block_client'):s.index('static int n71_ro_block_qualified')]
        self.assertLess(client.index('n71_ro_probe_wait(i)'),client.index('submit_bio_wait('))
        self.assertLess(client.index('memchr_inv('),client.index('n71_ro_probe_reply(0)'))
        self.assertLess(client.index('n71_ro_probe_finish(rc)'),client.index('WRITE_ONCE(n71_ro_block_memory.client_rc,rc)'))
        run=s[s.index('static int n71_ro_block_once'):]
        self.assertLess(run.index('n71_ro_probe_close(!!rc)'),run.index('kthread_stop('))
        self.assertIn('if (rc) n71_read_series_memory.series_ok=false;',run)
