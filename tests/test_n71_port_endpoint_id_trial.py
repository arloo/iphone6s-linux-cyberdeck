"""Run temporary WLAN-only bus route and ID read with rollback faults."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-port-endpoint-id-trial.h"
struct ctx{unsigned int bus;int mode,checks,reads,writes;};
int ready(void*p){struct ctx*c=p;c->checks++;return !(c->mode>=1&&c->mode<=6&&c->checks==c->mode);}
unsigned int rr(void*p,unsigned int off){struct ctx*c=p;assert(off==0||off==0x18);return off==0?(c->mode==7?0xffffffff:0x1004106b):c->bus;}
void wr(void*p,unsigned int v){struct ctx*c=p;c->writes++;assert(v==0xab010100||v==0xab000000);
 if(c->mode==9&&c->writes==1)return;if(c->mode==10&&c->writes==2)return;c->bus=v;}
unsigned int er(void*p,unsigned int off){struct ctx*c=p;assert(off==(unsigned)c->reads*4&&c->reads<3);c->reads++;
 if(off==0)return c->mode==11?0xffffffff:0x43a314e4;
 return off==4?0x00100000:0x02800001;}
int observe(void*p){struct ctx*c=p;assert(c->bus==0xab010100&&c->reads==3);return c->mode==12?0:-1;}
int main(int argc,char**argv){struct ctx c={.bus=0xab000000,.mode=atoi(argv[1])};struct n71_endpoint_result r;
 struct n71_endpoint_ops o={ready,rr,wr,er};if(c.mode>=12)o.observe=observe;if(c.mode==8)c.bus=0xab020200;
 int rc=n71_endpoint_id_trial(&o,&c,&r);
 if(c.mode==0)assert(rc==0&&r.id==0x43a314e4&&r.reads==3&&r.restored&&c.writes==2);
 if(c.mode==1||c.mode==2||c.mode==7||c.mode==8)assert(rc==-1&&c.writes==0&&c.reads==0);
 if(c.mode>=3&&c.mode<=6)assert(rc==-1&&r.restored&&c.writes==2&&c.reads==c.mode-3);
 if(c.mode==9)assert(rc==-1&&r.restored&&c.reads==0);
 if(c.mode==10)assert(rc==-3&&!r.restored&&c.reads==3);
 if(c.mode==12)assert(rc==0&&r.restored&&c.writes==2);
 if(c.mode==13)assert(rc==-1&&r.restored&&c.writes==2);
 if(c.mode==11)assert(rc==-2&&r.restored&&c.reads==1);
 if(c.mode!=8&&c.mode!=10)assert(c.bus==0xab000000);return 0;}
'''
class Tests(unittest.TestCase):
 def test_route_read_and_rollback(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(14):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
