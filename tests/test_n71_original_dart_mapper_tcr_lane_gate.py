"""Strictly synthetic tests: original N71 DART mapper -> stream TCR lane provenance.

No original Apple machine code or firmware is distributed. Synthetic instruction
words mirror separately documented control flow facts and are mutation tested.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
TOOL=BASE/"tools/n71_original_dart_mapper_tcr_lane_gate.py"
SPEC=importlib.util.spec_from_file_location("s5l_original_lane",TOOL)
assert SPEC and SPEC.loader
gate=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

def programs():
    family=bytearray(gate.EXPECTED_LENGTHS[gate.FAMILY])
    dart=bytearray(gate.EXPECTED_LENGTHS[gate.S5L])
    for off,opcode in gate.FAMILY_WORDS.items():
        struct.pack_into("<I",family,off,opcode)
    for off,opcode in gate.S5L_WORDS.items():
        struct.pack_into("<I",dart,off,opcode)
    # These are throwaway zero-filled synthetic fixtures, not original KEXTs.
    struct.pack_into("<I",family,0x3b6c,0x90000001)
    struct.pack_into("<I",family,0x3b70,0x91000021)
    return family,dart

class TestOriginalAppleDARTLane(unittest.TestCase):
    def test_expected_pinned_synthetic_instructions(self):
        a,b=programs()
        gate.check_pinned_instructions(a,b)

    def test_all_family_original_instructions_fail_closed(self):
        a,b=programs()
        for at in gate.FAMILY_WORDS:
            with self.subTest(offset=at):
                x=bytearray(a)
                x[at]^=0x40
                with self.assertRaises(gate.RejectedDARTProvenance):
                    gate.check_pinned_instructions(x,b)

    def test_all_hardware_original_instructions_fail_closed(self):
        a,b=programs()
        for at in gate.S5L_WORDS:
            with self.subTest(offset=at):
                x=bytearray(b)
                x[at]^=0x10
                with self.assertRaises(gate.RejectedDARTProvenance):
                    gate.check_pinned_instructions(a,x)

    def test_family_wrong_length_rejected(self):
        a,b=programs()
        with self.assertRaises(gate.RejectedDARTProvenance):
            gate.check_pinned_instructions(a[:-1],b)

    def test_hardware_wrong_length_rejected(self):
        a,b=programs()
        with self.assertRaises(gate.RejectedDARTProvenance):
            gate.check_pinned_instructions(a,b[:-1])

    def test_out_of_bounds_original_instruction_rejected(self):
        with self.assertRaises(gate.RejectedDARTProvenance):
            gate.word(b"\0\0\0",0)

    def test_unaligned_original_instruction_rejected(self):
        with self.assertRaises(gate.RejectedDARTProvenance):
            gate.word(b"\0"*12,1)

    def test_valid_synthetic_original_field_to_hardware_vtable(self):
        a,b=programs()
        family_vm=0x5000
        hardware_vm=0x6000
        text=b"reg\0"+b"\0"*32
        fake={
            gate.FAMILY:{"code":bytes(a),"vm":family_vm,"base":0,
                         "nested":{"__TEXT":{"sections":{"__cstring":{
                             "vm":0x1000,"offset":0,"size":len(text)}}}}},
            gate.S5L:{"code":bytes(b),"vm":hardware_vm},
        }
        add=gate.word(a,0x3b70)
        reference=0x1000-((add>>10)&0xfff)
        def fake_ptr(blob,main,address):
            if address==0x2000+1408:return hardware_vm+0x1a10
            if address==0x2000+1736:return hardware_vm+0x1c00
            raise AssertionError("Unexpected original virtual method slot")
        with patch.object(gate,"extract_original_modules",
                          return_value=({},fake)),\
             patch.object(gate.G,"adrp_target",return_value=reference),\
             patch.object(gate.G,"adrp_add_str_vptr",return_value=0x2000),\
             patch.object(gate.G,"read_data_pointer",side_effect=fake_ptr):
            gate.verify_original_code(text)

    def test_modified_original_string_reg_rejected(self):
        a,b=programs()
        fake={
            gate.FAMILY:{"code":bytes(a),"vm":0x5000,"base":0,
                         "nested":{"__TEXT":{"sections":{"__cstring":{
                             "vm":0x1000,"offset":0,"size":20}}}}},
            gate.S5L:{"code":bytes(b),"vm":0x6000},
        }
        with patch.object(gate,"extract_original_modules",return_value=({},fake)),\
             patch.object(gate.G,"adrp_target",return_value=0x1000-((gate.word(a,0x3b70)>>10)&0xfff)):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original_code(b"sid\0"+b"\0"*32)

    def test_synthetic_modified_property_instruction_rejected(self):
        a,b=programs()
        struct.pack_into("<I",a,0x3b70,0x91000022)
        fake={gate.FAMILY:{"code":bytes(a),"vm":0x5000,"base":0,
                           "nested":{"__TEXT":{"sections":{"__cstring":{
                              "vm":0x1000,"offset":0,"size":32}}}}},
              gate.S5L:{"code":bytes(b),"vm":0x6000}}
        with patch.object(gate,"extract_original_modules",return_value=({},fake)),\
             patch.object(gate.G,"adrp_target",return_value=0x1000):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original_code(b"reg\0"+b"\0"*30)

    def test_dart_original_logical_index_zero(self):
        def parse_mock(blob,offset,parent,visitor,visit_all):
            visitor(gate.ADT.MAPPER,{"reg":struct.pack("<I",0)})
            return len(blob)
        with patch.object(gate.CENSUS,"audit_bytes",
                          return_value={"dart1_mapper_declared_consumers":1,
                                        "dart1_child_nodes":1,
                                        "dart1_direct_controller_consumers":0}),\
             patch.object(gate.ADT.ADT,"parse_node",side_effect=parse_mock),\
             patch.object(gate,"verify_original_code"):
            self.assertEqual(gate.verify_original(b"synthetic",b"adt")["tcr_byte_lane"],0)

    def test_dart_mapper_logical_index_one_rejected(self):
        def parse_mock(blob,offset,parent,visitor,visit_all):
            visitor(gate.ADT.MAPPER,{"reg":struct.pack("<I",1)})
            return len(blob)
        with patch.object(gate.CENSUS,"audit_bytes",
                          return_value={"dart1_mapper_declared_consumers":1,
                                        "dart1_child_nodes":1,
                                        "dart1_direct_controller_consumers":0}),\
             patch.object(gate.ADT.ADT,"parse_node",side_effect=parse_mock),\
             patch.object(gate,"verify_original_code"):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original(b"synthetic",b"adt")

    def test_multiple_original_mapper_entries_rejected(self):
        def parse_mock(blob,offset,parent,visitor,visit_all):
            visitor(gate.ADT.MAPPER,{"reg":struct.pack("<I",0)})
            visitor(gate.ADT.MAPPER,{"reg":struct.pack("<I",0)})
            return len(blob)
        with patch.object(gate.CENSUS,"audit_bytes",
                          return_value={"dart1_mapper_declared_consumers":1,
                                        "dart1_child_nodes":1,
                                        "dart1_direct_controller_consumers":0}),\
             patch.object(gate.ADT.ADT,"parse_node",side_effect=parse_mock),\
             patch.object(gate,"verify_original_code"):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original(b"synthetic",b"adt")

    def test_unexpected_other_dart1_consumer_rejected(self):
        with patch.object(gate.CENSUS,"audit_bytes",
                          return_value={"dart1_mapper_declared_consumers":2,
                                        "dart1_child_nodes":1,
                                        "dart1_direct_controller_consumers":0}):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original(b"synthetic",b"adt")

    def test_unexpected_direct_dart1_controller_consumer_rejected(self):
        with patch.object(gate.CENSUS,"audit_bytes",
                          return_value={"dart1_mapper_declared_consumers":1,
                                        "dart1_child_nodes":1,
                                        "dart1_direct_controller_consumers":1}):
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.verify_original(b"synthetic",b"adt")

    def test_invalid_original_metadata_rejected(self):
        with self.assertRaises(Exception):
            gate.extract_original_modules(b"not an Apple Mach-O")

    def test_corrupt_original_kernel_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"malformed-original"
            p.write_bytes(b"NOT_A_REAL_KERNELCACHE"*1024)
            with self.assertRaises(Exception):
                gate.extract_original_modules(p.read_bytes())

    def test_symlink_private_input_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"original"
            p.write_bytes(b"synthetic original")
            link=Path(t)/"link"
            link.symlink_to(p)
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.private_bytes(link,1024)

    def test_oversize_private_input_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"private"
            p.write_bytes(b"synthetic source bytes")
            with self.assertRaises(gate.RejectedDARTProvenance):
                gate.private_bytes(p,8)

    def test_unsafe_private_path_never_echoed_by_cli(self):
        with tempfile.TemporaryDirectory() as t:
            secret="SYNTHETIC_SECRET_DART_PRIVATE_999"
            p=Path(t)/(secret+".bin")
            p.write_bytes(b"original-not-valid")
            proc=subprocess.run([sys.executable,str(TOOL),str(p),str(p)],
                capture_output=True,text=True,timeout=20)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn("FAIL_CLOSED",proc.stderr)
            self.assertNotIn(secret,proc.stdout+proc.stderr)
            self.assertNotIn(str(p),proc.stdout+proc.stderr)

    def test_no_hardware_or_network_writes(self):
        import ast
        src=TOOL.read_text()
        tree=ast.parse(src)
        blocked={"ioremap","readl","writel","write_bytes","socket",
                 "mmap","ioctl","Popen","run","system","execv"}
        for n in ast.walk(tree):
            if isinstance(n,ast.Call):
                name=(n.func.id if isinstance(n.func,ast.Name) else
                      n.func.attr if isinstance(n.func,ast.Attribute) else "")
                self.assertNotIn(name,blocked)

    def test_no_false_linux_dma_authorization(self):
        src=TOOL.read_text()
        for expected in (
            "ACTUAL_PCIE_REQUESTER_TO_SID_ROUTING_PROVEN=NO",
            "DART1_LIVE_TTBR_IOVA_DMA_ISOLATION_PROVEN=NO",
            "HARDWARE_MMIO_GPIO_RESET_AND_LINUX_WIFI_AUTHORIZED=NO",
            "PROPRIETARY_OR_PRIVATE_ORIGINAL_PAYLOAD_EXPORTED=NO"):
            self.assertIn(expected,src)

if __name__=="__main__":
    unittest.main()
