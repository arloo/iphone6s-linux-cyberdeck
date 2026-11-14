"""Bounded OTP reads never expose bytes and leave size0 on incomplete capture."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include "n71-endpoint-otp-snapshot.h"
struct ctx{int mode,checks,reads;};
int ready(void*p){struct ctx*c=p;return ++c->checks!=c->mode;}
unsigned int rd(void*p,unsigned int off){struct ctx*c=p;c->reads++;
 if(off==4)return (c->mode==160?0:c->mode==161?1:7)<<19;
 if(off==0xfc)return 0x18100000;
 assert(off>=0x8c0&&off<0xc00&&!(off&3));return 0x44332211;}
int main(int argc,char**argv){struct ctx c={.mode=atoi(argv[1])};unsigned char b[N71_OTP_MAX_BYTES];struct n71_otp_result r;
 const struct n71_otp_ops o={ready,rd};int rc=n71_endpoint_otp_snapshot(&o,&c,b,&r);
 if(c.mode==0)assert(rc==0&&r.bytes==832&&r.reads==210&&b[0]==0x11&&b[831]==0x44);
 if(c.mode>=1&&c.mode<=159)assert(rc==-1&&r.bytes==0);
 if(c.mode==160)assert(rc==-2&&r.bytes==0);
 if(c.mode==161)assert(rc==0&&r.bytes==64);
 return 0;}
'''
class Tests(unittest.TestCase):
 def test_bounded_capture(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(C)
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   for mode in range(162):
    with self.subTest(mode=mode):subprocess.run([str(p/'t'),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
