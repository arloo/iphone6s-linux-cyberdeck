"""Execute the actual selected-stream sequence with fake register I/O."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <string.h>
#include "n71-dart-ttbr-disabled-trial.h"
struct ctx { unsigned int regs[32], original[16]; int mode, perst, writes, held; };
unsigned int rd(void *p,unsigned int off) { return ((struct ctx*)p)->regs[off/4]; }
void wr(void *p,unsigned int off,unsigned int value) {
 struct ctx *c=p; if(off==0x0c){assert(value==0 || value==0x80); for(int i=0;i<4;i++)assert(c->regs[0x40/4+i]==0); if(c->mode==9 && value)return; c->regs[3]=value;c->writes++;return;} assert(off>=0x40 && off<=0x4c && !(off%4)); c->writes++;
 if(c->mode==4 && !value)return;
 if(c->mode==6 && c->held && value)return;
 c->regs[off/4]=value;
}
int low(void *p){return ((struct ctx*)p)->perst;}
void hold(void *p){struct ctx*c=p;c->held=1;if(c->mode==5)c->regs[0x50/4]^=1;if(c->mode==7)c->perst=0;}
int main(int argc,char **argv) {
 int mode=argv[1][0]-'0',rc;unsigned int z,r;struct ctx c={.mode=mode,.perst=1};
 const struct n71_dart_trial_ops ops={rd,wr,low,hold};
 for(int i=0;i<16;i++)c.original[i]=c.regs[0x40/4+i]=0x80001000+i;
 c.regs[0]=0xf02;c.regs[4]=0x100;
 if(mode==1)c.regs[3]=0x80;if(mode==2)c.regs[0]|=8;if(mode==3)c.regs[4]|=0x80000000;
 if(mode==8 || mode==9){for(int i=0;i<4;i++)c.regs[0x40/4+i]=0;rc=n71_dart_tcr0_pulse(&ops,&c);assert(rc==(mode==8?0:-1));assert(c.regs[3]==0);return 0;}
 rc=n71_dart_disabled_ttbr_trial(&ops,&c,&z,&r);
 if(mode>=1 && mode<=3){assert(rc==-1 && c.writes==0);return 0;}
 if(mode==0)assert(rc==0 && z==1 && r==1 && c.writes==8);
 if(mode==4)assert(rc==-2 && z==0 && r==1);
 if(mode==5 || mode==6 || mode==7)assert(rc==-3 && r==0);
 if(mode!=6)for(int i=0;i<4;i++)assert(c.regs[0x40/4+i]==c.original[i]);
 for(int i=4;i<16;i++)assert(c.regs[0x40/4+i]==(c.original[i]^(mode==5 && i==4 ? 1:0)));
 return 0;
}
"""
class Tests(unittest.TestCase):
 def test_compiled_sequence_and_rollback(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'test.c';f.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(f),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(10):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
