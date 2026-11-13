"""Execute nested source-defined port1 auxiliary control and PERST rollback."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-port-aux-trial.h"
struct ctx{unsigned int aux[4],ctrl;int mode,level,ready,ticks,writes;};
unsigned int ar(void*p,unsigned int off){struct ctx*c=p;assert(off>=0x4020&&off<=0x40e0&&!((off-0x4020)%64));return c->aux[(off-0x4020)/64];}
void aw(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert(off==0x4060);c->writes++;if(c->mode==1&&v==3)return;if(c->mode==2&&v==7)return;c->aux[1]=v;}
unsigned int rd(void*p,unsigned int off){struct ctx*c=p;assert(off==0x80||off==0x88);return off==0x80?c->ctrl:c->level;}
void wr(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert(off==0x80&&(v==0||v==1));c->ctrl=v;}
int level(void*p){return ((struct ctx*)p)->level;}
void set(void*p,int v){struct ctx*c=p;if(c->mode==4&&!v)return;c->level=v;}
int ready(void*p){return ((struct ctx*)p)->ready;}
void delay(void*p){struct ctx*c=p;c->ticks++;if(c->mode==3)c->aux[2]^=1;if(c->mode==5)c->ready=0;}
int main(int argc,char**argv){
 struct ctx c={.aux={1,7,5,9},.ready=1,.mode=atoi(argv[1])};unsigned int s,n,r,a;int rc;
 const struct n71_port_trial_ops po={rd,wr,level,set,ready,delay};const struct n71_port_aux_ops ao={ar,aw};
 if(c.mode==6)c.ready=0;
 rc=n71_port_aux_trial(&po,&ao,&c,&s,&n,&r,&a);
 if(c.mode==0)assert(rc==0&&s==1&&n==25&&r==1&&a==1&&c.level==0&&c.ctrl==0);
 if(c.mode==1)assert(rc==-1&&a==1&&n==0);
 if(c.mode==2)assert(rc==-2&&a==0&&c.aux[1]==3);
 if(c.mode==3)assert(rc==-2&&a==0&&c.aux[2]==4);
 if(c.mode==4)assert(rc==-3&&a==0&&c.level==1&&c.ctrl==1&&c.aux[1]==3);
 if(c.mode==5)assert(rc==-1&&a==1&&c.level==0&&c.ctrl==0);
 if(c.mode==6)assert(rc==-1&&a==0&&c.writes==0);
 assert(c.aux[0]==1&&c.aux[3]==9);
 if(c.mode!=2&&c.mode!=4)assert(c.aux[1]==7);
 return 0;
}
'''
class Tests(unittest.TestCase):
 def test_actual_aux_sequence(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(7):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
