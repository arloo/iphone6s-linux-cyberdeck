"""Exercise WLAN-only BDF/config writes and reject any bus-master enable."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest,re
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include "n71-pci-config-policy.h"
int main(void){
 for(unsigned int b=0;b<9;b++)for(unsigned int d=0;d<256;d++) {
  int wanted=b==0&&d==8?0:b==1&&d==0?1:-1;
  assert(n71_cfg_target(b,d,0,4)==wanted);
  assert(n71_cfg_target(b,d,4092,4)==wanted);
  assert(n71_cfg_target(b,d,4095,1)==wanted);
  assert(n71_cfg_target(b,d,4093,4)==-1);
  assert(n71_cfg_target(b,d,0,3)==-1);
 }
 for(unsigned int t=0;t<3;t++)for(unsigned int v=0;v<65536;v++)
  assert(n71_cfg_write_allowed(t,4,2,v,2)==(t<2&&(v==0||v==2)));
 for(unsigned int t=0;t<3;t++)for(unsigned int off=0;off<4096;off+=4)for(unsigned int cmd=0;cmd<8;cmd++) {
  int wanted=t==0?(off==0x10||off==0x14):t==1?(off>=0x10&&off<=0x24):0;
  assert(n71_cfg_write_allowed(t,off,4,~0U,cmd)==(wanted&&cmd==0));
 }
 assert(!n71_cfg_write_allowed(0,0x18,4,0x00010100,0));
 assert(!n71_cfg_write_allowed(1,4,4,2,0));
 return 0;}
'''
class Tests(unittest.TestCase):
 def test_actual_policy(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(C)
   subprocess.run([cc,'-std=c11','-O2','-I',str(ROOT/'experimental/port1'),str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
 def test_driver_binding_not_enabled(self):
  s=(ROOT/'experimental/port1/n71-pci-core-enumerate.h').read_text()
  self.assertNotRegex(s,r'\bpci_bus_add_devices?\s*\(')
  self.assertNotRegex(s,r'\bpci_set_master\s*\(')
  self.assertIn('pci_dev_binding_disallowed(ep)',s)
  self.assertIn('pci_stop_root_bus(root);pci_remove_root_bus(root);',s)
if __name__=='__main__':unittest.main()
