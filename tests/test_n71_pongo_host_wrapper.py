"""Run the actual wrapper in a fake host tree; never invoke real USB/root tools."""
from pathlib import Path
import hashlib, os, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
FAKE=r'''#!/usr/bin/env python3
import os,sys
from pathlib import Path
cmd=Path(sys.argv[0]).name; args=sys.argv[1:]; base=Path(os.environ['TEST_HOST'])
with (base/'events').open('a') as f:f.write(cmd+' '+' '.join(args)+'\n')
if cmd=='udevadm':
 if os.environ.get('TEST_FAIL_UDEV')=='1' and args[0]=='control':sys.exit(1)
 if os.environ.get('TEST_FAIL_SETTLE')=='1' and args[0]=='settle':sys.exit(1)
elif cmd=='modprobe':
 if args==['--showconfig']:print((base/'run/modprobe.d/cyberdeck-pongo-no-apple-mfi.conf').read_text())
 elif args and args[0]=='-r':
  p=base/'sys/module/apple_mfi_fastcharge'
  if p.exists():p.rmdir()
 else:(base/'sys/module/apple_mfi_fastcharge').mkdir(parents=True,exist_ok=True)
elif cmd=='lsusb':
 if args==['-d','05ac:4141'] and os.environ.get('TEST_PONGO','1')=='1':print('Bus 001 Device 002: ID 05ac:4141 Pongo')
elif cmd=='palera1n':sys.exit(int(os.environ.get('TEST_PALERA_RC','0')))
'''
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
  b=self.base
  for d in ('scripts','hoolock/bin','bin','sys/module/apple_mfi_fastcharge','usr/lib/udev/rules.d','etc/udev/rules.d'):(b/d).mkdir(parents=True)
  self.vendor=b/'usr/lib/udev/rules.d/80-drivers.rules'
  self.vendor_bytes=b'ACTION!="add", GOTO="drivers_end"\nENV{MODALIAS}=="?*", RUN{builtin}+="kmod load"\nLABEL="drivers_end"\n'
  self.vendor.write_bytes(self.vendor_bytes)
  (b/'hoolock/bin/Pongo.bin').write_bytes(b'FAKE TEST PONGO')
  for name in ('udevadm','modprobe','lsusb'):
   p=b/'bin'/name;p.write_text(FAKE);p.chmod(0o755)
  p=b/'hoolock/bin/palera1n';p.write_text(FAKE);p.chmod(0o755)
  text=(ROOT/'scripts/pongo-once-without-mfi-reload.sh').read_text()
  # Only fixture paths/root identity/hash change; wrapper control flow is intact.
  for original in ('/run/','/sys/module/','/usr/lib/udev/','/etc/udev/'):
   text=text.replace(original,str(b)+original)
  text=text.replace('[[ "$EUID" -ne 0 ]]','[[ 0 -ne 0 ]]')
  text=text.replace('1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',hashlib.sha256(b'FAKE TEST PONGO').hexdigest())
  self.script=b/'scripts/wrapper.sh';self.script.write_text(text)
  self.env=dict(os.environ,PATH=str(b/'bin')+os.pathsep+os.environ['PATH'],TEST_HOST=str(b))
  self.policy=b/'run/modprobe.d/cyberdeck-pongo-no-apple-mfi.conf';self.rule=b/'run/udev/rules.d/80-drivers.rules'
 def call(self,mode='run',**env):return subprocess.run(['bash',str(self.script),mode],env=dict(self.env,**env),capture_output=True,text=True)
 def events(self):return (self.base/'events').read_text().splitlines() if (self.base/'events').exists() else []
 def test_order_rule_scope_and_restore(self):
  p=self.call();self.assertEqual(p.returncode,0,p.stderr)
  e=self.events();self.assertLess(e.index('udevadm control --reload'),e.index('udevadm settle --timeout=10'))
  self.assertLess(e.index('udevadm settle --timeout=10'),e.index('modprobe -r apple_mfi_fastcharge'))
  self.assertLess(e.index('modprobe -r apple_mfi_fastcharge'),next(i for i,x in enumerate(e) if x.startswith('palera1n ')))
  rule=self.rule.read_bytes();first,body=rule.split(b'\n',1);self.assertEqual(body,self.vendor_bytes)
  self.assertIn(b'ENV{DEVTYPE}=="usb_device"',first);self.assertIn(b'GOTO="drivers_end"',first)
  self.assertIn('N71_PONGO_LIVE_USB_GADGET_05ac_4141_CONFIRMED',p.stdout)
  p=self.call('restore');self.assertEqual(p.returncode,0,p.stderr)
  self.assertFalse(self.rule.exists());self.assertFalse(self.policy.exists());self.assertEqual(self.vendor.read_bytes(),self.vendor_bytes)
 def test_no_false_success_without_gadget(self):
  p=self.call(TEST_PONGO='0');self.assertNotEqual(p.returncode,0);self.assertNotIn('4141_CONFIRMED',p.stdout)
 def test_gadget_confirms_after_nonzero_tool_exit(self):
  p=self.call(TEST_PALERA_RC='255');self.assertEqual(p.returncode,0);self.assertIn('N71_PALERA1N_EXIT_CODE=255',p.stdout)
 def test_reload_failure_prevents_exploit(self):
  p=self.call(TEST_FAIL_UDEV='1');self.assertNotEqual(p.returncode,0);self.assertFalse(any(x.startswith('palera1n ') for x in self.events()))
 def test_settle_failure_prevents_unload_and_exploit(self):
  p=self.call(TEST_FAIL_SETTLE='1');self.assertNotEqual(p.returncode,0);self.assertFalse(any(x.startswith(('palera1n ','modprobe -r')) for x in self.events()))
 def test_unknown_runtime_rule_blocks_without_mutation(self):
  self.rule.parent.mkdir(parents=True);self.rule.write_text('FOREIGN\n')
  p=self.call();self.assertNotEqual(p.returncode,0);self.assertEqual(self.rule.read_text(),'FOREIGN\n');self.assertFalse(self.events())
 def test_restore_checks_both_before_removing_either(self):
  self.assertEqual(self.call().returncode,0);self.rule.write_text('FOREIGN\n')
  p=self.call('restore');self.assertNotEqual(p.returncode,0);self.assertTrue(self.policy.exists())
 def test_custom_etc_rule_blocks(self):
  (self.base/'etc/udev/rules.d/80-drivers.rules').write_text('CUSTOM\n')
  p=self.call();self.assertNotEqual(p.returncode,0);self.assertFalse(self.policy.exists())
if __name__=='__main__':unittest.main()
