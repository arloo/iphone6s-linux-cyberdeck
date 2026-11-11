"""Synthetic-only validation for the A9 PCIe KEXT metadata reader."""
from pathlib import Path
import importlib.util
import struct
import tempfile
import subprocess
import sys
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"tools/n71_kernelcache_pcie_kext_map.py"
spec=importlib.util.spec_from_file_location("n71_pcie_kext_inspect",SCRIPT)
module=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

MV=0x1000000000
PRELINK_OFF=0x1000
EXEC_VM=MV+0x100000
EXEC_OFF=0x4000
INFO_OFF=0x8000
INFO_VM=MV+0x200000
NAMES=sorted(module.TARGETS)


def name16(s):
    return s.encode("ascii").ljust(16,bytes([0]))


def segment(seg,vm,sz,fo,fs,section=None):
    n=1 if section is not None else 0
    cmdsz=72+80*n
    v=struct.pack("<II16sQQQQiiII",
        module.LC_SEGMENT_64,cmdsz,name16(seg),
        vm,sz,fo,fs,7,5,n,0)
    if section:
        v+=struct.pack("<16s16sQQIIIIIIII",
            name16(section),name16(seg),vm,sz,fo,
            2,0,0,0,0,0,0)
    return v


def macho(commands,subtype=0):
    return struct.pack("<8I",module.MACH64,module.ARM64_CPU,subtype,
        2,len(commands),sum(map(len,commands)),0,0)+b"".join(commands)


def fixture(*,missing=None,duplicate=False,modified_size=False,
            bad_text_vm=False,secret=False):
    buf=bytearray(0xe000)
    commands=[
        segment("__PRELINK_TEXT",MV,0x2000,PRELINK_OFF,0x2000),
        segment("__PLK_TEXT_EXEC",EXEC_VM,0x4000,EXEC_OFF,0x4000),
        segment("__PRELINK_INFO",INFO_VM,0x2000,INFO_OFF,0x2000),
    ]
    header=macho(commands)
    buf[:len(header)]=header
    kexts=[]
    for ix,name in enumerate(NAMES):
        if name==missing:continue
        load=MV+0x100+ix*0x400
        executable=EXEC_VM+0x100+ix*0x100
        if bad_text_vm and ix==2:executable=MV-0x100
        nested=macho([
            segment("__TEXT",load,0x100,0,0x100),
            segment("__TEXT_EXEC",executable,0x40,0,0x40,"__text"),
        ])
        assert len(nested)==0x100
        off=PRELINK_OFF+load-MV
        buf[off:off+len(nested)]=nested
        codeoff=EXEC_OFF+executable-EXEC_VM
        if 0<=codeoff<len(buf)-0x40:
            buf[codeoff:codeoff+0x40]=bytes.fromhex("c0035fd6")*16
        reported_size="0x101" if modified_size and ix==1 else "0x100"
        kexts.append(
            "<dict><key>CFBundleIdentifier</key><string>"+name+"</string>"
            "<key>_PrelinkExecutableLoadAddr</key><integer>"+
            hex(load)+"</integer>"
            "<key>_PrelinkExecutableSize</key><integer>"+
            reported_size+"</integer></dict>")
    if duplicate:kexts.append(kexts[0])
    token="<key>NeverPublish</key><string>PRIVATE_DUMMY_VALUE</string>" if secret else ""
    xml=("<dict><key>_PrelinkInfoDictionary</key><array>"+
         "".join(kexts)+"</array>"+token+"</dict>").encode()
    assert len(xml)<=0x2000
    buf[INFO_OFF:INFO_OFF+len(xml)]=xml
    return bytes(buf)


class TestS8000PrelinkInspector(unittest.TestCase):
    def reject(self,blob):
        with self.assertRaises(module.BadKernelcache):
            module.map_pcie_kexts(blob)

    def test_four_synthetic_pcie_components_map_correctly(self):
        result=module.map_pcie_kexts(fixture())
        self.assertEqual(len(result),4)
        self.assertEqual(set(t[0] for t in result),module.TARGETS)
        self.assertTrue(all(size==0x40 for _,_,size in result))

    def test_missing_specific_s8000_extension_fails(self):
        self.reject(fixture(missing="com.apple.driver.AppleS8000PCIe"))

    def test_duplicate_extension_fails(self):
        self.reject(fixture(duplicate=True))

    def test_bad_reported_header_size_fails(self):
        self.reject(fixture(modified_size=True))

    def test_wrong_kext_executable_region_fails(self):
        self.reject(fixture(bad_text_vm=True))

    def test_not_arm64_macho_fails(self):
        b=bytearray(fixture())
        struct.pack_into("<I",b,4,0x01000007)
        self.reject(bytes(b))

    def test_corrupted_prelink_xml_fails(self):
        b=bytearray(fixture())
        b[INFO_OFF]=0xff
        self.reject(bytes(b))

    def test_no_proprietary_values_in_cli_output(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"synthetic-kernelcache.macho"
            path.write_bytes(fixture(secret=True))
            r=subprocess.run([sys.executable,str(SCRIPT),str(path)],
                             capture_output=True,text=True,check=False,
                             timeout=8)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("A9_PCIE_KEXT_METADATA_PASS",r.stdout)
            self.assertIn("HARDWARE_BLOCKED",r.stdout)
            self.assertNotIn("PRIVATE_DUMMY_VALUE",r.stdout)

    def test_readonly_no_binary_exports(self):
        text=SCRIPT.read_text()
        for bad in ("write_bytes(", "wb", "subprocess.run(", "os.system(",
                    "mmap(","/dev/mem","ptrace(","sendto("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad,text)


if __name__=="__main__":
    unittest.main()
