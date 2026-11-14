"""Exercise actual BAR/window/MSE transaction, including failed decode teardown."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-endpoint-mmio-trial.h"
struct ctx{unsigned int root[64],ep[64];int mode,checks,reads,writes;};
int ready(void*p){struct ctx*c=p;return !(c->mode>=1&&c->mode<=5&&++c->checks==c->mode);}
unsigned int rr(void*p,unsigned int off){struct ctx*c=p;assert(off==4||off==0x20);return c->root[off/4];}
unsigned int er(void*p,unsigned int off){struct ctx*c=p;assert(off==4||(off>=0x10&&off<=0x1c&&!(off&3))||off==0x80);return c->ep[off/4];}
void rw(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert(off==0x20);c->writes++;if(c->mode==7&&v==0xc070c000)return;c->root[off/4]=v;}
void ew(void*p,unsigned int off,unsigned int v){struct ctx*c=p;assert((off>=0x10&&off<=0x1c&&!(off&3))||off==0x80);c->writes++;
 if(c->mode==6&&off==0x10&&v==0xc0000004)return;
 if(c->mode==8&&off==0x80&&v==0x18000000)return;
 if(c->mode==13&&off==0x10&&v==4)return;
 c->ep[off/4]=v;}
void rc(void*p,unsigned int v){struct ctx*c=p;assert(v==0||v==2);if(c->mode==10&&v==2)return;if(c->mode==12&&!v)return;c->root[1]=v;}
void ec(void*p,unsigned int v){struct ctx*c=p;assert(v==0||v==2);if(c->mode==9&&v==2)return;if(c->mode==11&&!v)return;c->ep[1]=v;}
unsigned int chip(void*p){struct ctx*c=p;c->reads++;assert(c->root[1]==2&&c->ep[1]==2&&c->root[8]==0xc070c000&&c->ep[4]==0xc0000004&&c->ep[6]==0xc0400004&&c->ep[32]==0x18000000);return c->mode==14?0xffffffff:0x15554350;}
int main(int argc,char**argv){struct ctx c={.mode=atoi(argv[1])};struct n71_mmio_result r;
 c.ep[4]=c.ep[6]=4;c.ep[32]=0x18123000;c.root[8]=0x0000fff0;
 const struct n71_mmio_ops o={ready,rr,er,rw,ew,rc,ec,chip};int x=n71_endpoint_mmio_trial(&o,&c,&r);
 if(c.mode==0)assert(x==0&&r.chip==0x15554350&&r.reads==1&&r.restored);
 if(c.mode>=1&&c.mode<=10)assert(x==-1&&r.restored);
 if(c.mode>=11&&c.mode<=13)assert(x==-3&&!r.restored);
 if(c.mode==14)assert(x==-2&&r.restored);
 if(c.mode<11||c.mode==14)assert(!c.ep[1]&&!c.root[1]&&c.ep[4]==4&&!c.ep[5]&&c.ep[6]==4&&!c.ep[7]&&c.ep[32]==0x18123000&&c.root[8]==0x0000fff0);
 if(c.mode==11||c.mode==12)assert(c.ep[4]==0xc0000004&&c.ep[6]==0xc0400004);
 return 0;}
'''
class Tests(unittest.TestCase):
 def test_memory_only_transaction(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(C)
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   for mode in range(15):
    with self.subTest(mode=mode):subprocess.run([str(p/'t'),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
