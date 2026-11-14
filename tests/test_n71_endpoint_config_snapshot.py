"""Bounded read-only PCI capability walk rejects malformed chains and guard loss."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-endpoint-config-snapshot.h"
struct ctx {unsigned int cfg[64];int checks,reads,mode;};
int ready(void*p){struct ctx*c=p;return ++c->checks!=c->mode;}
unsigned int rd(void*p,unsigned int off){struct ctx*c=p;assert(off<=0xfc&&!(off&3));c->reads++;return c->cfg[off/4];}
int main(int argc,char**argv){struct ctx c={0};struct n71_snapshot r;int mode=atoi(argv[1]);
 c.cfg[4]=4;c.cfg[6]=0xc;c.cfg[0x34/4]=0x40;c.cfg[0x40/4]=0x5010;c.cfg[0x50/4]=0x00110000;
 if(mode>=1&&mode<=14)c.mode=mode;
 if(mode==15)c.cfg[0x0c/4]=0x10000;
 if(mode==16)c.cfg[0x34/4]=0x3c;
 if(mode==17)c.cfg[0x34/4]=0x41;
 if(mode==18)c.cfg[0x50/4]=0x4001;
 if(mode==19)c.cfg[0x40/4]=0;
 if(mode==20)c.cfg[0x50/4]=0x10;
 if(mode==21){c.cfg[0x34/4]=0xfc;c.cfg[0xfc/4]=0x10;}
 const struct n71_snapshot_ops o={ready,rd};int rc=n71_endpoint_snapshot(&o,&c,&r);
 if(mode==0)assert(rc==0&&r.bars[0]==4&&r.bars[2]==0xc&&r.pcie==0x40&&r.caps==2&&r.reads==11);
 if(mode>=1&&mode<=12)assert(rc==-1);
 if(mode==13||mode==14)assert(rc==0);
 if(mode>=15)assert(rc==-2);
 assert(c.reads<=12);return 0;}
'''
class Tests(unittest.TestCase):
 def test_readonly_snapshot(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(22):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
