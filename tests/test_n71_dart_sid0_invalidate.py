"""Run the real SID0 invalidate sequence and outer rollback with fake MMIO."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
C = r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-dart-ttbr-disabled-trial.h"
struct ctx { unsigned int regs[32], saved[16], polls, last; int mode, issued, reads, ticks, low, inner; };
unsigned int rd(void *p, unsigned int off) {
 struct ctx *c=p;
 if(off==0 && c->issued && c->mode==0 && ++c->reads>=3)c->regs[0]=0x102;
 return c->regs[off/4];
}
void wr(void *p,unsigned int off,unsigned int v) {
 struct ctx *c=p;
 assert(off==0 || off==12 || (off>=0x40 && off<=0x4c && !(off%4)));
 if(off==0){
  assert(v==0x102 && c->regs[3]==0x80 && c->low);
  for(int i=0;i<4;i++)assert(c->regs[16+i]==0);
  c->issued=1;c->regs[0]=c->mode==3?0x202:0x10a;
  if(c->mode==4){c->regs[4]|=0x80000000U;c->regs[0]=0x102;}
  if(c->mode==5)c->regs[0]=0x102;
  return;
 }
 if(off==12){
  assert(v==0 || v==0x80);
  for(int i=0;i<4;i++)assert(c->regs[16+i]==0);
  if(c->mode==1 && v)return;
  if(c->mode==5 && !v)return;
 } else assert(c->regs[3]==0); /* never restore a valid root while enabled */
 c->regs[off/4]=v;
}
int low(void *p){return ((struct ctx*)p)->low;}
void tick(void *p){struct ctx*c=p;c->ticks++;if(c->mode==6)c->low=0;}
void hold(void *p){
 struct ctx*c=p;
 const struct n71_dart_trial_ops o={.read=rd,.write=wr,.perst_low=low,.tick=tick};
 c->inner=n71_dart_tcr0_flush_trial(&o,c,&c->last,&c->polls);
}
int main(int argc,char **argv){
 struct ctx c={.mode=atoi(argv[1]),.low=1}; unsigned int z,r;int rc;
 const struct n71_dart_trial_ops o={.read=rd,.write=wr,.perst_low=low,.hold=hold,.command_change_mask=0xf00};
 c.regs[0]=0xf02;c.regs[4]=0x100;
 for(int i=0;i<16;i++)c.saved[i]=c.regs[16+i]=0x80001000+i;
 rc=n71_dart_disabled_ttbr_trial(&o,&c,&z,&r);
 if(c.mode==0){assert(rc==0 && z==1 && r==1 && c.inner==0);assert(c.regs[0]==0x102 && c.polls==3);}
 if(c.mode==1)assert(rc==0 && r==1 && c.inner==-1 && !c.issued);
 if(c.mode==2)assert(rc==-3 && r==0 && c.inner==-2 && c.polls==100 && c.ticks==100);
 if(c.mode==3)assert(rc==0 && r==1 && c.inner==-1);
 if(c.mode==4)assert(rc==-3 && r==0 && c.inner==-1);
 if(c.mode==5)assert(rc==-3 && r==0 && c.inner==-3 && c.regs[3]==0x80);
 if(c.mode==6)assert(rc==-3 && r==0 && c.inner==-2);
 if(c.mode!=5)assert(c.regs[3]==0);
 for(int i=0;i<16;i++)assert(c.regs[16+i]==(c.mode==5 && i<4?0:c.saved[i]));
 return 0;
}
'''
class Tests(unittest.TestCase):
 def test_selected_invalidation_and_failures(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(7):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
