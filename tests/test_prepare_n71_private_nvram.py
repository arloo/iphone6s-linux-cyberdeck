import importlib.util,struct,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/prepare_n71_private_nvram.py"
s=importlib.util.spec_from_file_location("nv",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_padding_token_and_preserved_calibration(self):
  b=m.pack_nvram(b"#comment\nboardrev=0x1\ncal=abc\n",bytes.fromhex("020000000001"))
  self.assertIn(b"cal=abc\0",b);self.assertIn(b"macaddr=02:00:00:00:00:01\0",b)
  n=(len(b)-4)//4;t=struct.unpack("<I",b[-4:])[0]
  self.assertEqual(t&65535,n);self.assertEqual(t>>16,(~n)&65535);self.assertEqual(b[-5],0)
 def test_existing_mac_is_preserved(self):
  b=m.pack_nvram(b"boardrev=1\nmacaddr=00:11:22:33:44:55\n")
  self.assertEqual(b.count(b"macaddr="),1);self.assertIn(b"00:11:22:33:44:55",b)
 def test_generated_mac_is_local_unicast(self):
  b=m.pack_nvram(b"boardrev=1\n");entry=next(x for x in b.split(b"\0") if x.startswith(b"macaddr="))
  self.assertEqual(int(entry.split(b"=")[1].split(b":")[0],16)&3,2)
 def test_rejects_unsupported_input(self):
  for b in [b"a=1",b"boardrev=1\nmacaddr=a\nmacaddr=b",b"boardrev=1\ndevpath0=x",b"boardrev=1\0",b"boardrev=1\nx=y z"]:
   with self.assertRaises(ValueError):m.pack_nvram(b)
 def test_rejects_nonlocal_override(self):
  with self.assertRaises(ValueError):m.pack_nvram(b"boardrev=1",bytes.fromhex("010000000001"))
