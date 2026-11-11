"""Synthetic byte-boundary tests for private RAM-only Wi-Fi candidate isolation."""
from pathlib import Path
import gzip
import importlib.util
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/n71_wifi_ram_candidate_diff_gate.py"
sp=importlib.util.spec_from_file_location("n71_ram_wifi_diff",P)
g=importlib.util.module_from_spec(sp)
assert sp and sp.loader
sp.loader.exec_module(g)

def build():
    m1=b"FAKE_M1N1_PRIVATE_TEST_ONLY"
    dtb0=b"FAKE_A9_N71_DTB"
    dtb3=b"FAKE_A9_TSMC_UNTESTED_DTB"
    old=gzip.compress(b"MOCK-ARM64-IMAGE-KNOWN-GOOD",mtime=0)
    new=gzip.compress(b"MOCK-ARM64-IMAGE-WIFI-ALTERNATIVE",mtime=0)
    init=gzip.compress(b"MOCK-TOUCH-AUTOSTART-PRIVATE-RAMDISK",mtime=0)
    hdr=b"chosen.bootargs=console=tty0 hl_rd=shell\n"
    a=m1+hdr+dtb0+dtb3+old+init
    b=m1+hdr+dtb0+dtb3+new+init
    return a,b,m1,dtb0,dtb3,old,new,init

class TestN71WifiRAMCandidateDifference(unittest.TestCase):
    def rejects(self,data):
        with self.assertRaises(g.UnsafeRAMCandidate):
            g.compare_components(*data)

    def test_changed_kernel_alone_passes(self):
        result=g.compare_components(*build())
        self.assertTrue(result["same_m1n1"])
        self.assertTrue(result["same_private_ramdisk"])
        self.assertFalse(result["candidate_kernel_booted"])

    def test_changed_m1n1_fails(self):
        p=list(build())
        p[1]=b"CORRUPTED"+p[1][9:]
        self.rejects(p)

    def test_changed_apple_n71_dtb_fails(self):
        p=list(build())
        off=len(p[2])+len(b"chosen.bootargs=console=tty0 hl_rd=shell\n")
        raw=bytearray(p[1]);raw[off]^=1;p[1]=bytes(raw)
        self.rejects(p)

    def test_changed_tsmc_dtb_fails(self):
        p=list(build())
        off=len(p[2])+len(b"chosen.bootargs=console=tty0 hl_rd=shell\n")+len(p[3])
        raw=bytearray(p[1]);raw[off]^=1;p[1]=bytes(raw)
        self.rejects(p)

    def test_changed_bootargs_fails(self):
        p=list(build())
        p[1]=p[1].replace(b"hl_rd=shell",b"hl_rd=other")
        self.rejects(p)

    def test_changed_private_ramdisk_fails(self):
        p=list(build())
        p[1]=p[1][:-1]+bytes([p[1][-1]^1])
        self.rejects(p)

    def test_wrong_old_kernel_reference_fails(self):
        p=list(build())
        p[5]=gzip.compress(b"wrong old Linux kernel",mtime=0)
        self.rejects(p)

    def test_same_old_and_alternate_kernel_fails(self):
        p=list(build())
        p[6]=p[5]
        p[1]=p[0]
        self.rejects(p)

    def test_corrupted_kernel_crc_fails(self):
        p=list(build())
        bad=bytearray(p[6]);bad[-1]^=0x10
        p[6]=bytes(bad)
        p[1]=p[2]+b"chosen.bootargs=console=tty0 hl_rd=shell\n"+p[3]+p[4]+p[6]+p[7]
        self.rejects(p)

    def test_different_trailing_bytes_fails(self):
        p=list(build())
        p[1]+=b"extra secret"
        self.rejects(p)

    def test_no_bootargs_control_injection(self):
        p=list(build())
        p[0]=p[0].replace(b"hl_rd=shell",b"hl_rd=\x00hell")
        self.rejects(p)

    def test_no_other_file_access_or_write(self):
        text=P.read_text()
        for forbidden in ("write_bytes(","mmap(", "socket.", "subprocess.run(",
                          "insmod ", "modprobe ", "git push",
                          "ioremap(", "/dev/mem", "writel("):
            self.assertNotIn(forbidden,text)

    def test_cli_no_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/"fake"
            fake.write_bytes(b"test data only")
            r=subprocess.run(["python3",str(P),*([str(fake)]*8)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_output_explicit_no_live_wifi_claim(self):
        s=P.read_text()
        self.assertIn("ALTERNATE_KERNEL_BOOTED_OR_WLAN_FUNCTIONAL=NO",s)
        self.assertIn("NO_DEVICE_ACCESS_NO_BOOT_NO_NAND_CHANGE",s)

if __name__=="__main__":
    unittest.main()
