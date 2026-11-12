"""Synthetic-only live iOS N71 DART1/port1 reference provenance tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_live_dart1_pcie_link_gate.py"
SP=importlib.util.spec_from_file_location("n71_live_dart1",TOOL)
assert SP and SP.loader
G=importlib.util.module_from_spec(SP)
SP.loader.exec_module(G)

def uint32(n):
    return struct.pack("<I",n)

def fixtures():
    original={
      G.ADT.HOST+"/pci-bridge1":{
        "apcie-port":uint32(1),
        "t-refclk-to-perst":uint32(100),
        "function-clkreq":b"\x02\x00\x00\x00"*4,
        "function-dart_force_active":b"\x03\x00\x00\x00"*2,
      },
      G.ADT.MAPPER:{"reg":uint32(0)},
      G.ADT.DART_PATHS[1]:{"reg":b"\x00\x00\x00\x01"*4},
    }
    bridge={**original[G.ADT.HOST+"/pci-bridge1"],
            "IOPCIConfigured":True,
            "IOPCIResourced":True,
            "IOPCIExpressLinkStatus":0x1011}
    mapper={**original[G.ADT.MAPPER]}
    dart={**original[G.ADT.DART_PATHS[1]]}
    driver={"IOClass":"AppleS5L8960XDART",
            "IONameMatched":"dart,s5l8960x",
            "IOMatchedAtBoot":True,
            "IOProviderClass":"AppleARMIODevice"}
    plists=[plistlib.dumps({"IORegistry":x})
            for x in (bridge,mapper,dart,driver)]
    return original,plists

class TestN71S8000OriginalLiveDART1(unittest.TestCase):
    def checked(self,original,plists):
        with patch.object(G,"original_expected",return_value=original):
            return G.check_live(b"SYNTHETIC_ADT",*plists)

    def mutate(self,which,key,value):
        originals,plists=fixtures()
        data=plistlib.loads(plists[which])
        if value is None:data["IORegistry"].pop(key,None)
        else:data["IORegistry"][key]=value
        plists[which]=plistlib.dumps(data)
        with self.assertRaises(G.RejectedOriginalLive):
            self.checked(originals,plists)

    def test_valid_synthetic_gen1x1_reference(self):
        orig,plists=fixtures()
        result=self.checked(orig,plists)
        self.assertEqual(result["matched_props"],6)
        self.assertEqual(result["apple_port"],1)
        self.assertEqual(result["mapper_index"],0)
        self.assertEqual(result["speed_code"],1)
        self.assertEqual(result["lane_width"],1)
        self.assertEqual(result["refclk_perst_metadata"],100)

    def test_port2_rejected(self):
        self.mutate(0,"apcie-port",uint32(2))

    def test_mapper_other_index_rejected(self):
        self.mutate(1,"reg",uint32(1))

    def test_mapper_wrong_width_rejected(self):
        self.mutate(1,"reg",b"\0\0")

    def test_dart_window_mismatch_rejected(self):
        self.mutate(2,"reg",b"\x44"*16)

    def test_dart_window_absent_rejected(self):
        self.mutate(2,"reg",None)

    def test_clkreq_mismatch_rejected(self):
        self.mutate(0,"function-clkreq",b"\x99"*16)

    def test_clkreq_wrong_length_rejected(self):
        self.mutate(0,"function-clkreq",b"\0"*12)

    def test_dart_force_active_change_rejected(self):
        self.mutate(0,"function-dart_force_active",b"\x09"*8)

    def test_dart_force_active_missing_rejected(self):
        self.mutate(0,"function-dart_force_active",None)

    def test_refclk_perst_101_rejected(self):
        self.mutate(0,"t-refclk-to-perst",uint32(101))

    def test_refclk_perst_byte_swapped_rejected(self):
        self.mutate(0,"t-refclk-to-perst",struct.pack(">I",100))

    def test_refclk_perst_oversized_rejected(self):
        self.mutate(0,"t-refclk-to-perst",b"\0"*8)

    def test_ios_unconfigured_port_rejected(self):
        self.mutate(0,"IOPCIConfigured",False)

    def test_ios_unresourced_port_rejected(self):
        self.mutate(0,"IOPCIResourced",False)

    def test_pcie_gen2_status_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus",0x1012)

    def test_pcie_zero_lane_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus",0x1001)

    def test_pcie_x2_lane_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus",0x1021)

    def test_pcie_link_training_in_progress_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus",0x1811)

    def test_pcie_slot_clock_missing_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus",0x0011)

    def test_ios_non_integer_status_rejected(self):
        self.mutate(0,"IOPCIExpressLinkStatus","0x1011")

    def test_dart_class_other_rejected(self):
        self.mutate(3,"IOClass","AppleS5L8960XDART-v2")

    def test_dart_name_match_missing_rejected(self):
        self.mutate(3,"IONameMatched",None)

    def test_dart_not_at_boot_rejected(self):
        self.mutate(3,"IOMatchedAtBoot",False)

    def test_dart_other_provider_rejected(self):
        self.mutate(3,"IOProviderClass","TestProvider")

    def test_fake_nested_plist_rejected(self):
        with self.assertRaises(G.RejectedOriginalLive):
            G.read_registry(plistlib.dumps({"other":{}}))

    def test_malformed_plist_rejected(self):
        with self.assertRaises(G.RejectedOriginalLive):
            G.read_registry(b"not a valid plist")

    def test_original_missing_nodes_rejected(self):
        orig,_=fixtures()
        with patch.object(G.CENSUS,"audit_bytes",return_value={
           "dart1_mapper_declared_consumers":1,"dart1_child_nodes":1}),\
             patch.object(G.ADT.ADT,"parse_node",return_value=0):
            with self.assertRaises(G.RejectedOriginalLive):
                G.original_expected(b"SYNTHETIC")

    def test_original_census_unknown_second_consumer_rejected(self):
        with patch.object(G.CENSUS,"audit_bytes",return_value={
           "dart1_mapper_declared_consumers":2,"dart1_child_nodes":1}):
            with self.assertRaises(G.RejectedOriginalLive):
                G.original_expected(b"SYNTHETIC")

    def test_private_input_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"original"
            p.write_bytes(b"SYNTHETIC_VALID_TEST_DATA")
            link=Path(directory)/"sym"
            link.symlink_to(p)
            with self.assertRaises(G.RejectedOriginalLive):
                G.read_private_file(link,1000)

    def test_private_path_not_printed_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            secret="SECRET_ONLY_LOCAL_RESEARCH_IOREG"
            p=Path(directory)/(secret+".plist")
            p.write_bytes(b"not_real_apple_data")
            result=subprocess.run([sys.executable,str(TOOL)]+[str(p)]*5,
                                  text=True,capture_output=True,timeout=20)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("FAIL_CLOSED",result.stderr)
            self.assertNotIn(secret,result.stderr+result.stdout)

    def test_no_hardware_effects_in_tool_source(self):
        import ast
        src=TOOL.read_text()
        tree=ast.parse(src)
        forbidden={"ioremap","readl","writel","mmap","ioctl",
                   "system","Popen","run","socket","write_bytes"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else (
                  node.func.attr if isinstance(node.func,ast.Attribute) else "")
                self.assertNotIn(name,forbidden)

    def test_no_false_live_dma_claim(self):
        s=TOOL.read_text()
        self.assertIn("LIVE_DART1_HARDWARE_STREAM_ID_DMA_TTBR_PROVEN=NO",s)
        self.assertIn("PORT1_LINUX_HARDWARE_INITIALIZATION_AUTHORIZED=NO",s)
        self.assertIn("REFCLK_TO_PERST_METADATA_TIME_UNITS_PROVEN=NO",s)

if __name__=="__main__":
    unittest.main()
