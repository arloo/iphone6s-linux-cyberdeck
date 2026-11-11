"""Synthetic original A9 port1 register-bit provenance, no Apple executable data."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s8000_port1_status_bit_provenance_gate.py"
spec=importlib.util.spec_from_file_location("n71_status_bit_gate",SCRIPT)
m=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

def ldr_x(dest,base,offset):
    assert offset%8==0
    return 0xF9400000|((offset//8)<<10)|(base<<5)|dest

def fixture():
    import struct
    s=bytearray(18552)
    e=bytearray(46924)
    original_shared={
        0x3c0:0xAA0103E2,
        0x3c8:ldr_x(8,0,0),
        0x3cc:ldr_x(8,8,2016),
        0x3d0:0x528000A1,
        0x3d4:0xD63F0100,
        0x3d8:0xAA0003E1,
        0x3dc:ldr_x(8,19,0),
        0x3e0:ldr_x(8,8,1808),
        0x3e4:0xAA1303E0,
        0x3e8:0xD63F0100,
        0x3ec:0x12000000,
        0x3f8:0xD65F03C0,
    }
    original_embedded={
        # Synthetic root vslot1880 -> resource index -> provider
        # memory-map vslot976 -> virtual pointer vslot120.
        0x1f4c:ldr_x(8,19,0),
        0x1f50:ldr_x(8,8,1880),
        0x1f54:0xAA1303E0,
        0x1f58:0xD63F0100,
        0x1f5c:0xAA0003E1,
        0x1f60:ldr_x(8,20,0),
        0x1f64:ldr_x(8,8,976),
        0x1f68:0xAA1403E0,
        0x1f6c:0x52800002,
        0x1f70:0xD63F0100,
        0x1f74:0xF900D260,
        0x1f78:0xB40010A0,
        0x1f7c:ldr_x(8,0,0),
        0x1f80:ldr_x(8,8,120),
        0x1f84:0xD63F0100,
        0x1f88:0xF900D660,
        0x4664:ldr_x(8,0,424),
        0x4668:0xB8614913,
        0x469c:0xAA1303E0,
        0x46ac:0xD65F03C0,
    }
    for off,word in original_shared.items():
        struct.pack_into("<I",s,off,word)
    for off,word in original_embedded.items():
        struct.pack_into("<I",e,off,word)
    return bytes(s),bytes(e)

def mutate(bytecode,off,word):
    import struct
    b=bytearray(bytecode)
    struct.pack_into("<I",b,off,word)
    return bytes(b)

class TestN71A9RootStatusBitProvenance(unittest.TestCase):
    def setUp(self):
        self.shared,self.embedded=fixture()

    def verify(self,shared=None,embedded=None):
        return m.qualify_code(
            shared if shared is not None else self.shared,
            embedded if embedded is not None else self.embedded)

    def rejects(self,shared=None,embedded=None):
        with self.assertRaises(m.UnqualifiedStatusBit):
            self.verify(shared,embedded)

    def test_original_synthetic_read_chain_accepts(self):
        r=self.verify()
        self.assertEqual(r["relative_byte_offset"],0x1ac)
        self.assertEqual(r["bit_mask"],1)
        self.assertFalse(r["bit_is_link_ready_verified"])

    def test_other_port_selector_id_is_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3d0,0x52800081))

    def test_wrong_s8000_a9_virtual_selector_slot_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3cc,ldr_x(8,8,2008)))

    def test_wrong_root_read32_vtable_slot_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3e0,ldr_x(8,8,1816)))

    def test_wrong_status_bit_mask_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3ec,0x12000400))

    def test_missing_root_status_return_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3f8,0))

    def test_wrong_root_common_resource_selector_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f50,
                                     ldr_x(8,8,1888)))

    def test_wrong_memory_provider_mapping_method_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f64,
                                     ldr_x(8,8,984)))

    def test_wrong_provider_memory_argument_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f5c,0xAA0103E1))

    def test_missing_memory_map_availability_guard_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f78,0))

    def test_wrong_virtual_address_method_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f80,
                                     ldr_x(8,8,128)))

    def test_mapping_written_to_unrelated_root_field_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x1f88,0xF900D260))

    def test_wrong_root_reg_base_pointer_field_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x4664,ldr_x(8,0,432)))

    def test_wrong_embedded_load_type_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x4668,0xF8614913))

    def test_wrong_embedded_index_register_rejected(self):
        self.rejects(embedded=mutate(self.embedded,0x4668,0xB8624913))

    def test_bad_argument_provenance_rejected(self):
        self.rejects(shared=mutate(self.shared,0x3d8,0xAA0103E1))

    def test_root_parent_vtable_target_chain_positive(self):
        modules={
            "embedded":{"vm":0x1000,"vptr":0x8000},
            "shared":{"vm":0x2000,"vptr":0x9000},
            "a9":{"vm":0x3000,"vptr":0xA000}
        }
        ptrs={
            modules["a9"]["vptr"]+2008:modules["shared"]["vm"]+0x3b4,
            modules["a9"]["vptr"]+2016:modules["a9"]["vm"]+0x7d8,
            modules["a9"]["vptr"]+1808:modules["embedded"]["vm"]+0x4654,
        }
        with patch.object(m.CTOR,"read_data_pointer",
                          side_effect=lambda blob,main,slot:ptrs[slot]):
            m.qualify_vtable_targets(b"",{},modules)

    def test_wrong_root_read32_target_rejected(self):
        mods={
          "embedded":{"vm":0x1000,"vptr":0x8000},
          "shared":{"vm":0x2000,"vptr":0x9000},
          "a9":{"vm":0x3000,"vptr":0xA000}
        }
        vals={
            0xA000+2008:0x2000+0x3b4,
            0xA000+2016:0x3000+0x7d8,
            0xA000+1808:0x1000+0x4658,
        }
        with patch.object(m.CTOR,"read_data_pointer",
                          side_effect=lambda blob,main,slot:vals[slot]):
            with self.assertRaises(m.UnqualifiedStatusBit):
                m.qualify_vtable_targets(b"",{},mods)

    def test_private_input_mandatory_no_synthetic_success(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fake-original"
            p.write_bytes(self.shared)
            q=Path(td)/"fake-adt"
            q.write_bytes(b"fake")
            r=subprocess.run([sys.executable,str(SCRIPT),str(p),str(q)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_original_adt_and_selector_independently_reaudited(self):
        s=SCRIPT.read_text()
        self.assertIn("ROOT.audit(original,adt)",s)
        self.assertIn("COMMON.inspect_macho(original)",s)
        self.assertIn("PORT.analyze_method(shared)",s)

    def test_never_calculate_absolute_hw_register_address(self):
        s=SCRIPT.read_text()
        self.assertIn("ROOT_POINTER_IODEVICE_MEMORY_PROVIDER_ORDER_PROVEN=NO",s)
        self.assertIn("SAFE_MMIO_DART1_DMA_AND_WIFI_HARDWARE_AUTHORIZED=NO",s)
        self.assertNotIn("0x600000000 +",s)

    def test_no_private_binary_dump_or_device_api(self):
        s=SCRIPT.read_text()
        for bad in ("write_bytes(", "subprocess.run(", "mmap(", "ioremap(",
                    "writel(", "insmod ", "socket.", "/dev/mem", "git push"):
            self.assertNotIn(bad,s)

if __name__=="__main__":
    unittest.main()
