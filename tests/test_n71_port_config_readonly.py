"""Execute the fixed read-only root header transaction with guard failures."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-port-config-readonly.h"
struct ctx {int mode,reads,checks;};
int ready(void *p){struct ctx*c=p;c->checks++;return c->mode<1||c->mode>5||c->checks!=c->mode;}
unsigned int readcfg(void*p,unsigned int off){
 struct ctx*c=p;static const unsigned int o[]={0,4,8,0x18},v[]={0x1004106b,0x00100006,0x06040001,0x00020200};
 assert(c->reads<4&&off==o[c->reads]);unsigned int x=v[c->reads++];
 if(c->mode==6&&off==0)x=0xffffffffU;
 if(c->mode==7&&off==8)x=0x02000000;
 return x;
}
int main(int argc,char**argv){struct ctx c={.mode=atoi(argv[1])};struct n71_config_ro_result r;
 const struct n71_config_ro_ops ops={ready,readcfg};int rc=n71_port_config_readonly(&ops,&c,&r);
 if(c.mode==0)assert(rc==0&&r.id==0x1004106b&&r.buses==0x00020200&&r.reads==4);
 if(c.mode>=1&&c.mode<=5)assert(rc==-1&&r.reads==(unsigned)(c.mode-1));
 if(c.mode==6)assert(rc==-2&&r.reads==1);
 if(c.mode==7)assert(rc==-2&&r.reads==4);
 assert(r.reads==(unsigned)c.reads);return 0;}
'''
class Tests(unittest.TestCase):
 def test_fixed_header_and_guard_loss(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(8):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
