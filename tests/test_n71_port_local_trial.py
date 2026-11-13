"""Execute the actual port-control/PERST transaction against adversarial fake I/O."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-port-local-trial.h"
struct ctx { int mode,level,ready,ticks,writes,sets; unsigned int ctrl; };
unsigned int rd(void*p,unsigned int off){struct ctx*c=p;assert(off==0x80||off==0x88);return off==0x80?c->ctrl:(c->level?1:0);}
void wr(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert(off==0x80&&(v==0||v==1));c->writes++;if(c->mode==3&&v)return;if(c->mode==5&&!v)return;c->ctrl=v;}
int level(void*p){return ((struct ctx*)p)->level;}
void set(void*p,int v){struct ctx*c=p;c->sets++;if(c->mode==8&&!v)return;if(c->mode==9&&v)return;c->level=v;}
int ready(void*p){return ((struct ctx*)p)->ready;}
void delay(void*p){struct ctx*c=p;c->ticks++;if(c->mode==4&&c->ticks==3)c->ready=0;if(c->mode==6)c->level=1;}
int main(int argc,char**argv){
 struct ctx c={.mode=atoi(argv[1]),.ready=1};unsigned int s,n,r;int rc;
 struct n71_port_trial_ops o={rd,wr,level,set,ready,delay};
 if(c.mode==1)c.level=1;if(c.mode==2)c.ctrl=2;if(c.mode==10)c.ready=0;
 rc=n71_port_local_trial(&o,&c,c.mode>=7&&c.mode<=9,&s,&n,&r);
 if(c.mode==0)assert(rc==0&&n==25&&r==1&&c.ctrl==0&&c.level==0&&c.sets==0);
 if(c.mode==1||c.mode==2||c.mode==10)assert(rc==-1&&c.writes==0);
 if(c.mode==3)assert(rc==-1&&r==1&&n==0&&c.ctrl==0);
 if(c.mode==4)assert(rc==-1&&r==1&&n==2&&c.ctrl==0);
 if(c.mode==5)assert(rc==-2&&r==0&&c.ctrl==1);
 if(c.mode==6)assert(rc==-3&&r==0&&c.ctrl==1);
 if(c.mode==7)assert(rc==0&&n==25&&r==1&&c.level==0&&c.ctrl==0&&c.sets==2&&s==1);
 if(c.mode==8)assert(rc==-3&&r==0&&c.ctrl==1&&c.level==1);
 if(c.mode==9)assert(rc==-1&&r==1&&c.ctrl==0&&c.level==0&&c.sets==2);
 return 0;
}
'''
class Tests(unittest.TestCase):
 def test_actual_sequence(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(11):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
