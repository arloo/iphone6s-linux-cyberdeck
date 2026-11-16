"""Execute the actual optional PCI write policies against adversarial inputs."""
from pathlib import Path
import unittest,subprocess,tempfile,shutil
ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'experimental/iommu/native-runtime'
PREFIX=r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32;
typedef uint8_t u8;
#define __iomem
struct n71_dart_trial_mmio {void *endpoint;};
static unsigned char registers[4096];
static struct n71_dart_trial_mmio mm={registers};
static struct n71_dart_trial_mmio *n71_pci_dma_context=&mm;
static bool ready=true,n71_brcmf_trial_active;
static struct {bool active;} n71_msi_scope;
static u32 n71_brcmf_saved_cfg[1024];
static bool n71_config_ready(struct n71_dart_trial_mmio *m){return ready;}
static unsigned int readw(void *p){uint16_t v;memcpy(&v,p,2);return v;}
'''
class Tests(unittest.TestCase):
 def execute(self,source,body):
  cc=shutil.which('cc')
  if not cc:self.skipTest('Host C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(PREFIX+source+'\nint main(void){'+body+'return 0;}\n')
   subprocess.run([cc,'-std=gnu11','-O2',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
 def test_msi_never_authorizes_bus_master_or_other_requester(self):
  text=(T/'n71-native-msi-domain.h').read_text();source=text[text.index('static bool n71_native_msi_cfg_allowed('):]
  self.execute(source,r'''
   for(int active=0;active<2;active++){
    n71_msi_scope.active=active;
    for(unsigned int target=0;target<4;target++){
     assert(!n71_native_msi_cfg_allowed(target,4,2,6));
     assert(!n71_native_msi_cfg_allowed(target,4,2,0x406));
     for(unsigned int off=0;off<4096;off++)
      if(target!=1)assert(!n71_native_msi_cfg_allowed(target,off,2,8));
    }
   }
   assert(n71_native_msi_cfg_allowed(1,0x5c,4,0xbffff000));
   assert(!n71_native_msi_cfg_allowed(1,0x5c,4,0xbfffc000));
   assert(n71_native_msi_cfg_allowed(1,0x64,2,8));
   assert(!n71_native_msi_cfg_allowed(1,0x64,2,16));
   assert(!n71_native_msi_cfg_allowed(1,0x64,4,8));
   ready=false;assert(!n71_native_msi_cfg_allowed(1,0x64,2,8));
   ready=true;n71_pci_dma_context=0;assert(!n71_native_msi_cfg_allowed(1,0x64,2,8));
  ''')
 def test_brcmf_only_authorizes_owned_live_scope_and_bounded_core_windows(self):
  text=(T/'n71-brcmfmac-bind-trial.h').read_text();a=text.index('static bool n71_native_brcmf_cfg_allowed(');b=text.index('static int n71_native_brcmf_bind_trial(',a)
  self.execute(text[a:b],r'''
   for(unsigned int off=0;off<4096;off++)assert(!n71_native_brcmf_cfg_allowed(1,off,2,6));
   n71_brcmf_trial_active=true;
   for(unsigned int target=2;target<5;target++)
    for(unsigned int off=0;off<4096;off++)assert(!n71_native_brcmf_cfg_allowed(target,off,2,6));
   assert(n71_native_brcmf_cfg_allowed(1,4,2,6));
   assert(!n71_native_brcmf_cfg_allowed(1,4,2,7));
   assert(n71_native_brcmf_cfg_allowed(1,0x80,4,0x18000000));
   assert(n71_native_brcmf_cfg_allowed(1,0x80,4,0x181ff000));
   assert(!n71_native_brcmf_cfg_allowed(1,0x80,4,0x18200000));
   assert(!n71_native_brcmf_cfg_allowed(1,0x80,4,0x18000004));
   assert(!n71_native_brcmf_cfg_allowed(0,0x80,4,0x18000000));
   n71_brcmf_saved_cfg[0x228/4]=0x12345678;
   assert(n71_native_brcmf_cfg_allowed(1,0x228,4,0x12345678));
   assert(!n71_native_brcmf_cfg_allowed(1,0x228,4,0x12345679));
   ready=false;assert(!n71_native_brcmf_cfg_allowed(1,4,2,6));
   ready=true;n71_pci_dma_context=0;assert(!n71_native_brcmf_cfg_allowed(1,4,2,6));
  ''')
if __name__=='__main__':unittest.main()
