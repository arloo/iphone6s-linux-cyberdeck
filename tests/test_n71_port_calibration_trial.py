"""Run the actual masked tuning transaction and rollback against fake MMIO."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "n71-port-calibration-trial.h"
struct ctx {unsigned int mem[3][4096],original[3][4096];int mode,level,ready,writes,ran;unsigned int trace[192],trace_bank[192];};
unsigned int rd(void*p,unsigned int bank,unsigned int off){struct ctx*c=p;assert(bank<3&&off<0x4000&&!(off&3));return c->mem[bank][off/4];}
void wr(void*p,unsigned int bank,unsigned int off,unsigned int v){
 struct ctx*c=p;assert(bank<3&&off<0x4000&&!(off&3));assert(c->writes<192);
 c->trace[c->writes]=off;c->trace_bank[c->writes]=bank;c->writes++;
 if(c->mode==14&&c->writes==2)return;
 if(c->mode==15&&c->ran&&c->writes==4)return;
 c->mem[bank][off/4]=v;
 if(c->mode==16&&c->writes==1)c->ready=0;
}
int level(void*p){return ((struct ctx*)p)->level;}
int ready(void*p){return ((struct ctx*)p)->ready;}
int run(void*p,unsigned int*s,unsigned int*n,unsigned int*r){
 struct ctx*c=p;c->ran=1;*s=1;*n=25;*r=1;
 if(c->mode==17)return -1;
 if(c->mode==18){c->level=1;*r=0;return -3;}
 if(c->mode==19)c->mem[0][2]^=0x10000;
 return 0;
}
int main(int argc,char**argv){
 static struct ctx c;struct n71_calib_record rec[97]={{0,8,0xff,0x42},{1,0x100,0xff00,0x5500},{2,0x90,0xf,3}};
 unsigned int s,n,p,r,w,count=3;int rc,mode=atoi(argv[1]);
 const struct n71_calib_ops ops={rd,wr,level,ready,run};
 c.mode=mode;c.ready=1;
 for(int b=0;b<3;b++)for(int i=0;i<4096;i++)c.original[b][i]=c.mem[b][i]=0xa5b60718U+b+i*0x100;
 if(mode==1)c.level=1;if(mode==2)c.ready=0;if(mode==3)count=0;if(mode==4)count=97;
 if(mode==5)rec[0].bank=3;if(mode==6)rec[0].off=9;if(mode==7)rec[0].off=0x194;
 if(mode==8)rec[0].mask=0;if(mode==9)rec[0].value=0x100;if(mode==10)rec[1]=rec[0];
 if(mode==11)rec[0]=(struct n71_calib_record){0,0x100,1,1};
 if(mode==12)rec[0]=(struct n71_calib_record){2,0x80,1,1};
 if(mode==13)rec[0]=(struct n71_calib_record){1,0x4000,1,1};
 if(mode==20){count=96;for(unsigned int i=0;i<count;i++)rec[i]=(struct n71_calib_record){1,i*4,0xff,i};}
 rc=n71_port_calibration_trial(&ops,&c,rec,count,&s,&n,&p,&r,&w);
 if(mode>=1&&mode<=13){assert(rc==-1&&c.writes==0&&!c.ran&&r==0);return 0;}
 if(mode==0||mode==20){assert(rc==0&&r==1&&p==1&&n==25&&w==count&&c.writes==count*2);}
 if(mode==14)assert(rc==-1&&r==1&&w==2&&!c.ran&&c.writes==4);
 if(mode==15)assert(rc==-2&&r==0&&w==3&&c.ran);
 if(mode==16)assert(rc==-1&&r==1&&w==1&&!c.ran&&c.writes==2);
 if(mode==17)assert(rc==-1&&r==1&&c.ran&&c.writes==6);
 if(mode==18)assert(rc==-3&&r==0&&c.level==1&&c.writes==3);
 if(mode==19)assert(rc==-2&&r==0&&c.writes==6);
 if(mode==0||mode==14||mode==16||mode==17||mode==20)assert(!memcmp(c.mem,c.original,sizeof(c.mem)));
 if(mode==0||mode==20)for(unsigned int i=0;i<count;i++){assert(c.trace[count+i]==rec[count-1-i].off);assert(c.trace_bank[count+i]==rec[count-1-i].bank);}
 return 0;
}
'''
class Tests(unittest.TestCase):
 def test_actual_transaction(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';src.write_text(C);exe=Path(d)/'test'
   subprocess.run([cc,'-std=c11','-O2','-Wall','-I',str(ROOT/'experimental/port1'),str(src),'-o',str(exe)],check=True,capture_output=True)
   for mode in range(21):
    with self.subTest(mode=mode):subprocess.run([str(exe),str(mode)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
