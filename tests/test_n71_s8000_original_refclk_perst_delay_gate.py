"""Synthetic original N71 Apple REFCLK-to-PERST 100-microsecond proof tests.

Every private Apple firmware/kernel, owner IORegistry, Wi-Fi password and
actual phone value is intentionally absent from the public test fixtures.
"""
from __future__ import annotations
import importlib.util,plistlib,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_original_refclk_perst_delay_gate.py"
sp=importlib.util.spec_from_file_location("n71_delay_test",TOOL)
assert sp and sp.loader
G=importlib.util.module_from_spec(sp);sp.loader.exec_module(G)

def code_fixture():
    code=bytearray(G.TEXT_LEN)
    for offset,instruction in G.SIG.items():
        struct.pack_into("<I",code,offset,instruction)
    struct.pack_into("<I",code,0x4bcc,0xb0ffb522)
    struct.pack_into("<I",code,0x4bd0,0x913de842)
    vm=0x10000000
    addr=G.SEQ.CTOR.adrp_target(vm+0x4bcc,
                                  G.u32(code,0x4bcc),2)
    addr+=(G.u32(code,0x4bd0)>>10)&0xfff
    return bytes(code),vm,addr

def shared_fixture():
    data=bytearray(G.SEQ.SHARED_TEXT_LENGTH)
    for at,ins in ((0x668,0x37200080),(0x66c,0x52800140),
                   (0x670,0x94001082),(0x674,0x17fffff8)):
        struct.pack_into("<I",data,at,ins)
    return bytes(data)

def fake_original_symbols():
    b=bytearray(512)
    # Minimal synthetic Mach-O AArch64, 8 commands, 7 opaque 8-byte
    # commands and one LC_SYMTAB; no copyrighted source bytes.
    struct.pack_into("<8I",b,0,0xfeedfacf,0x0100000c,0,2,8,80,0,0)
    struct.pack_into("<6I",b,32,2,24,192,2,256,40)
    for i in range(7):
        struct.pack_into("<2I",b,56+8*i,0x900+i,8)
    strings=b"\0_IODelay\0_IOSleep\0"
    b[256:256+len(strings)]=strings
    struct.pack_into("<IBBHQ",b,192,1,0x0f,1,0,0x11111000)
    struct.pack_into("<IBBHQ",b,208,10,0x0f,1,0,0x22222000)
    return bytes(b)

class TestAuthenticDelayProofSynthetic(unittest.TestCase):
    def test_exact_synthetic_original_property_flow(self):
        data,vm,prop=code_fixture()
        out=G.check_original_port_property_flow(
            data,vm,b"t-refclk-to-perst\0",prop)
        self.assertEqual(out,{"offset":416,"width":4})

    def test_mutations_all_original_instruction_signatures(self):
        data,vm,prop=code_fixture()
        for at in G.SIG:
            with self.subTest(offset=hex(at)):
                bad=bytearray(data)
                bad[at]^=0x11
                with self.assertRaises(G.UnsafeDelay):
                    G.check_original_port_property_flow(
                        bad,vm,b"t-refclk-to-perst\0",prop)

    def test_wrong_private_embedded_code_length(self):
        data,vm,prop=code_fixture()
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                data[:-1],vm,b"t-refclk-to-perst\0",prop)

    def test_missing_original_property_string(self):
        data,vm,prop=code_fixture()
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                data,vm,b"t-refclk-to-foobar\0",prop)

    def test_duplicated_original_property_string(self):
        data,vm,prop=code_fixture()
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                data,vm,b"t-refclk-to-perst\0"*2,prop)

    def test_changed_property_string_address(self):
        data,vm,prop=code_fixture()
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                data,vm,b"t-refclk-to-perst\0",prop+1)

    def test_changed_property_address_instruction(self):
        data,vm,prop=code_fixture();bad=bytearray(data)
        bad[0x4bcc]^=0x10
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                bad,vm,b"t-refclk-to-perst\0",prop)

    def test_changed_property_add_instruction(self):
        data,vm,prop=code_fixture();bad=bytearray(data)
        bad[0x4bd0]^=0x01
        with self.assertRaises(G.UnsafeDelay):
            G.check_original_port_property_flow(
                bad,vm,b"t-refclk-to-perst\0",prop)

    def test_synthetic_xnu_symbols_resolve(self):
        symbols=G.kernel_named_symbols(
            fake_original_symbols(),{b"_IODelay",b"_IOSleep"})
        self.assertEqual(symbols[b"_IODelay"],0x11111000)
        self.assertEqual(symbols[b"_IOSleep"],0x22222000)

    def test_fake_xnu_wrong_architecture_rejected(self):
        b=bytearray(fake_original_symbols())
        struct.pack_into("<I",b,4,0x01000007)
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_fake_xnu_missing_symtab_rejected(self):
        b=bytearray(fake_original_symbols())
        struct.pack_into("<I",b,32,0x999)
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_fake_xnu_multiple_symtabs_rejected(self):
        b=bytearray(fake_original_symbols())
        struct.pack_into("<I",b,56,2)
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_fake_xnu_truncated_symtab_rejected(self):
        b=bytearray(fake_original_symbols())
        struct.pack_into("<I",b,40,0xffffffff)
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_fake_xnu_missing_iodelay_rejected(self):
        b=bytearray(fake_original_symbols())
        b[257:265]=b"_IOOther"
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_fake_xnu_iodelay_not_defined_rejected(self):
        b=bytearray(fake_original_symbols())
        b[196]=0
        with self.assertRaises(G.UnsafeDelay):
            G.kernel_named_symbols(b,{b"_IODelay",b"_IOSleep"})

    def test_callback_symbol_exactly_iodelay(self):
        with patch.object(G.SEQ,"analyze_method",return_value={
              "fixed_callback_argument":100,
              "dynamic_callback_argument_field":416,
              "two_calls_same_callback":True}),\
             patch.object(G.SEQ.CTOR,"ctor_stub_callee",
                          return_value=0x11111000),\
             patch.object(G,"kernel_named_symbols",
                          return_value={
                           b"_IODelay":0x11111000,
                           b"_IOSleep":0x22222000}):
            self.assertTrue(G.check_original_callback(
                 b"SYNTHETIC",{}, {},0x100000,
                 shared_fixture()))

    def test_original_shared_bit4_iod_delay_signatures_each_fail_closed(self):
        for at in (0x668,0x66c,0x670,0x674):
            with self.subTest(shared_bit4_delay_opcode=hex(at)):
                src=bytearray(shared_fixture())
                src[at]^=1
                with patch.object(G.SEQ,"analyze_method",return_value={
                      "fixed_callback_argument":100,
                      "dynamic_callback_argument_field":416,
                      "two_calls_same_callback":True}):
                    with self.assertRaises(G.UnsafeDelay):
                        G.check_original_callback(
                            b"SYNTHETIC",{},{},0x100000,bytes(src))

    def test_iosleep_wrong_unit_import_rejected(self):
        with patch.object(G.SEQ,"analyze_method",return_value={
              "fixed_callback_argument":100,
              "dynamic_callback_argument_field":416,
              "two_calls_same_callback":True}),\
             patch.object(G.SEQ.CTOR,"ctor_stub_callee",
                          return_value=0x22222000),\
             patch.object(G,"kernel_named_symbols",
                          return_value={
                           b"_IODelay":0x11111000,
                           b"_IOSleep":0x22222000}):
            with self.assertRaises(G.UnsafeDelay):
                G.check_original_callback(b"SYNTHETIC",{}, {},0x100000,
                                         shared_fixture())

    def test_inconsistent_original_import_calls_rejected(self):
        with patch.object(G.SEQ,"analyze_method",return_value={
              "fixed_callback_argument":100,
              "dynamic_callback_argument_field":416,
              "two_calls_same_callback":True}),\
             patch.object(G.SEQ.CTOR,"ctor_stub_callee",
                          side_effect=(0x11111000,0x22222000,0x11111000)),\
             patch.object(G,"kernel_named_symbols",
                          return_value={
                           b"_IODelay":0x11111000,
                           b"_IOSleep":0x22222000}):
            with self.assertRaises(G.UnsafeDelay):
                G.check_original_callback(b"SYNTHETIC",{}, {},0x100000,
                                         shared_fixture())

    def test_changed_dynamic_original_field_rejected(self):
        with patch.object(G.SEQ,"analyze_method",return_value={
             "fixed_callback_argument":100,
             "dynamic_callback_argument_field":420,
             "two_calls_same_callback":True}):
            with self.assertRaises(G.UnsafeDelay):
                G.check_original_callback(b"SYNTHETIC",{}, {},0x100000,
                                         shared_fixture())

    def test_original_adt_matches_synthetic_ios100(self):
        p=plistlib.dumps({"IORegistry":{
            "t-refclk-to-perst":struct.pack("<I",100),
            "IOPCIConfigured":True,"IOPCIResourced":True}})
        def parse(data,at,parent,visitor,visit_all,extra_props):
            visitor(G.ADT.HOST+"/pci-bridge1",
                    {"t-refclk-to-perst":struct.pack("<I",100)})
        with patch.object(G.ADT,"audit_bytes",return_value=
               "S8000_ADT_METADATA_GATE_PASS\n"
               "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED"),\
             patch.object(G.ADT.ADT,"parse_node",side_effect=parse):
            self.assertEqual(G.original_live_value(b"ORIGINAL_SYNTH",p),100)

    def test_original_adt_wrong_delay_value_rejected(self):
        p=plistlib.dumps({"IORegistry":{
            "t-refclk-to-perst":struct.pack("<I",100),
            "IOPCIConfigured":True,"IOPCIResourced":True}})
        def parse(data,at,parent,visitor,visit_all,extra_props):
            visitor(G.ADT.HOST+"/pci-bridge1",
                    {"t-refclk-to-perst":struct.pack("<I",101)})
        with patch.object(G.ADT,"audit_bytes",return_value=
               "S8000_ADT_METADATA_GATE_PASS\n"
               "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED"),\
             patch.object(G.ADT.ADT,"parse_node",side_effect=parse):
            with self.assertRaises(G.UnsafeDelay):
                G.original_live_value(b"ORIGINAL_SYNTH",p)

    def test_live_plist_wrong_delay_value_rejected(self):
        p=plistlib.dumps({"IORegistry":{
            "t-refclk-to-perst":struct.pack("<I",100000),
            "IOPCIConfigured":True,"IOPCIResourced":True}})
        def parse(data,at,parent,visitor,visit_all,extra_props):
            visitor(G.ADT.HOST+"/pci-bridge1",
                    {"t-refclk-to-perst":struct.pack("<I",100)})
        with patch.object(G.ADT,"audit_bytes",return_value=
               "S8000_ADT_METADATA_GATE_PASS\n"
               "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED"),\
             patch.object(G.ADT.ADT,"parse_node",side_effect=parse):
            with self.assertRaises(G.UnsafeDelay):
                G.original_live_value(b"ORIGINAL_SYNTH",p)

    def test_live_plist_not_resourced_rejected(self):
        p=plistlib.dumps({"IORegistry":{
            "t-refclk-to-perst":struct.pack("<I",100),
            "IOPCIConfigured":True,"IOPCIResourced":False}})
        def parse(data,at,parent,visitor,visit_all,extra_props):
            visitor(G.ADT.HOST+"/pci-bridge1",
                    {"t-refclk-to-perst":struct.pack("<I",100)})
        with patch.object(G.ADT,"audit_bytes",return_value=
               "S8000_ADT_METADATA_GATE_PASS\n"
               "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED"),\
             patch.object(G.ADT.ADT,"parse_node",side_effect=parse):
            with self.assertRaises(G.UnsafeDelay):
                G.original_live_value(b"ORIGINAL_SYNTH",p)

    def test_private_input_missing_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/"missing"
            with self.assertRaises(G.UnsafeDelay):
                G.private_read(path,1024)

    def test_private_input_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            source=Path(p)/"real"
            source.write_bytes(b"SYNTHETIC_original")
            link=Path(p)/"sym"
            link.symlink_to(source)
            with self.assertRaises(G.UnsafeDelay):
                G.private_read(link,1024)

    def test_secret_private_path_absent_from_cli_errors(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/"SYNTHETIC_PRIVATE_CREDENTIAL_1234567"
            path.write_bytes(b"SYNTHETIC_CORRUPT")
            result=subprocess.run(
                [sys.executable,str(TOOL),str(path),str(path),str(path)],
                capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("FAIL_CLOSED",result.stderr)
            self.assertNotIn(str(path),result.stderr+result.stdout)

    def test_forbidden_hardware_apis_not_present(self):
        src=TOOL.read_text()
        for name in ("ioremap","writel(","readl(","dma_map","dma_alloc",
                     "pci_host_probe","system(","Popen(","socket(","ioctl("):
            with self.subTest(name=name):
                self.assertNotIn(name,src)

    def test_no_false_linux_wifi_activation_claim(self):
        s=TOOL.read_text()
        self.assertIn("LINUX_PORT1_DART1_DMA_AND_WIFI_HARDWARE_AUTHORIZED=NO",s)
        self.assertIn("IOS_REFCLK_AND_RESET_OPERATION_ELECTRICAL_SAFETY_PROVEN=NO",s)

if __name__=="__main__":
    unittest.main()
