"""Execute exact 64-bit BAR sizing and restoration with injected failures."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-endpoint-bar-size-trial.h"
struct ctx {unsigned int bars[4];int mode,checks,writes;};
int ready(void*p){struct ctx*c=p;return ++c->checks!=c->mode;}
unsigned int rd(void*p,unsigned int off){struct ctx*c=p;if(off==4)return c->mode==14?4:0;
 assert(off>=0x10&&off<=0x1c&&!(off&3));unsigned int i=(off-0x10)/4,v=c->bars[i];
 if(v!=~0U)return v;
 if(i&1)return v;
 if(c->mode==20)return 0xffffa004;
 if(c->mode==21)return 0xffffc000;
 return i==0?0xffffc004:0xffc00004;}
void wr(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert(off>=0x10&&off<=0x1c&&!(off&3));c->writes++;
 if(c->mode==16&&c->writes==1)return;if(c->mode==17&&c->writes==2)return;
 if(c->mode==18&&c->writes==3)return;if(c->mode==19&&c->writes==4)return;
 c->bars[(off-0x10)/4]=v;}
int main(int argc,char**argv){struct ctx c={.bars={4,0,4,0},.mode=atoi(argv[1])};struct n71_bar_result r;
 if(c.mode==15)c.bars[0]=0xc;
 const struct n71_bar_ops o={ready,rd,wr};int rc=n71_endpoint_bar_size_trial(&o,&c,&r);
 if(c.mode==0)assert(rc==0&&r.size[0]==0x4000&&r.size[1]==0x400000&&r.restored&&c.writes==8);
 if(c.mode>=1&&c.mode<=14)assert(rc==-1&&r.restored);
 if(c.mode==15||c.mode==16||c.mode==17||c.mode==20||c.mode==21)assert(rc==-2&&r.restored);
 if(c.mode==18||c.mode==19)assert(rc==-3&&!r.restored);
 if(c.mode!=15&&c.mode!=18&&c.mode!=19)assert(c.bars[0]==4&&c.bars[1]==0&&c.bars[2]==4&&c.bars[3]==0);
 return 0;}
'''
class Tests(unittest.TestCase):
 def test_sizing_rollback(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(22):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
