"""Test actual adapted SID0 reset body and local-only overlay references."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest,struct
ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'experimental/iommu/native-runtime'
PREFIX=r'''
#include <assert.h>
#include <errno.h>
#include <string.h>
typedef unsigned int u32;
#define DART_S5L8960X 1
#define DART_MAX_STREAMS 256
struct hw{int type;};
struct apple_dart{struct hw*hw;unsigned int num_streams;void*regs;void*dev;};
struct apple_dart_stream_map{struct apple_dart*dart;unsigned long sidmap[4];};
static u32 mem[1024];static int owner,mode,writes;
int n71_runtime_owner_ok(void){return owner;}
unsigned int readl(void*p){return *(u32*)p;}
void bitmap_zero(unsigned long*p,int n){memset(p,0,n/8);}
void set_bit(int i,unsigned long*p){assert(i==0);p[0]|=1;}
void apple_dart_hw_disable_dma(struct apple_dart_stream_map*m){assert(m->sidmap[0]==1);writes++;if(mode!=5)mem[3]&=~255U;}
void apple_dart_hw_clear_ttbr(struct apple_dart_stream_map*m,unsigned int i){assert(m->sidmap[0]==1&&i<4);writes++;if(!(mode==6&&i==2))mem[16+i]=0;}
#define dev_info(...) ((void)0)
'''
SUFFIX=r'''
int main(void){for(mode=0;mode<=6;mode++){
 struct hw h={DART_S5L8960X};struct apple_dart d={&h,4,mem,0};u32 original[16];int rc;
 owner=1;writes=0;memset(mem,0,sizeof(mem));mem[3]=0x80;
 for(int i=0;i<16;i++)mem[16+i]=original[i]=0x80001000U+i;
 if(mode==1)owner=0;if(mode==2)h.type=2;if(mode==3)d.num_streams=3;if(mode==4)mem[3]=0x8080;
 rc=apple_dart_hw_reset(&d);
 if(mode==0)assert(rc==0&&mem[3]==0&&writes==5);
 if(mode>=1&&mode<=3)assert(rc==-EOPNOTSUPP&&writes==0);
 if(mode==4)assert(rc==-EBUSY&&writes==0);
 if(mode==5)assert(rc==-EIO&&writes==1&&mem[16]);
 if(mode==6)assert(rc==-EIO&&writes==5&&mem[18]==original[2]);
 for(int i=4;i<16;i++)assert(mem[16+i]==original[i]);
 assert(mem[0]==0&&mem[4]==0);
 }return 0;}
'''
class Tests(unittest.TestCase):
 def test_actual_scoped_reset_body(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  lines=(T/'native-driver-adapter.patch').read_text().splitlines()
  start=next(i for i,l in enumerate(lines) if l.startswith('+    struct apple_dart_stream_map m='))
  body=[]
  for l in lines[start:]:
   if l.startswith('+'):body.append(l[1:])
   if l=='+    return 0;':break
  self.assertTrue(body[-1].strip()=='return 0;')
  src=PREFIX+'\nstatic int apple_dart_hw_reset(struct apple_dart*dart){\n'+'\n'.join(body)+'\n}\n'+SUFFIX
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(src)
   subprocess.run([cc,'-std=gnu11','-O2',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
 def test_local_overlay_without_live_symbols(self):
  dtc=shutil.which('dtc')
  if not dtc:self.skipTest('dtc unavailable')
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'o.dtbo';subprocess.run([dtc,'-I','dts','-O','dtb','-o',str(out),str(T/'native.dts')],check=True,capture_output=True)
   b=out.read_bytes();self.assertEqual(struct.unpack_from('>I',b)[0],0xd00dfeed)
   self.assertEqual(struct.unpack_from('>I',b,4)[0],len(b))
   self.assertIn(b'__local_fixups__',b);self.assertNotIn(b'__symbols__',b)
 def test_decode_disabled_before_domain_teardown(self):
  s=(T/'native-runtime.h').read_text()
  self.assertLess(s.index('writel(0,(u8 __iomem *)dart+0xc)'),s.index('if(consumer)platform_device_unregister(consumer)'))
  self.assertIn('domain->type!=IOMMU_DOMAIN_DMA',s)
  self.assertIn('n71_port_perst_level(&n71_owner_copy)==0',s)
  self.assertIn('n71_dma_retained_buffer=buffer;buffer=0;',s)
if __name__=='__main__':unittest.main()
