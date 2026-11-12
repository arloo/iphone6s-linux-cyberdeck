"""Synthetic, fail-closed census tests. Never use or distribute original ADT."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_dart1_consumer_census_gate.py"
FIXTURE=ROOT/"tests/test_n71_s8000_adt_window_gate.py"

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s)
    assert s and s.loader
    s.loader.exec_module(m)
    return m

gate=load("n71_dart1_census",TOOL)
synth=load("n71_census_fixtures",FIXTURE)

def nodes():
    b=synth.fixture()
    out=[]
    n=gate.BASE.ADT.parse_node(
        b,0,"",visitor=lambda p,v:out.append((p,v)),visit_all=True)
    assert n==len(b)
    return out

def cells(*args):
    return struct.pack("<"+"I"*len(args),*args)

def extra(refs,phandle=0x91,path="/device-tree/arm-io/test-peripheral"):
    return path,{"AAPL,phandle":cells(phandle),
                 "iommu-parent":cells(*refs)}

class TestN71Dart1ConsumerCensus(unittest.TestCase):
    def reject(self, entries):
        with self.assertRaises(gate.InvalidMapperCensus):
            gate.census_nodes(entries)

    def test_strict_original_topology_synthetic_fixture_pass(self):
        out=gate.audit_bytes(synth.fixture())
        self.assertEqual(out["iommu_parent_properties"],1)
        self.assertEqual(out["iommu_parent_cells"],1)
        self.assertEqual(out["dart1_mapper_declared_consumers"],1)

    def test_direct_complete_tree_count(self):
        out=gate.census_nodes(nodes())
        self.assertEqual(out["iommu_parent_cells"],1)

    def test_extra_consumer_of_dart1_rejected(self):
        self.reject(nodes()+[extra((0x84,))])

    def test_non_wlan_multi_cell_consumer_rejected(self):
        self.reject(nodes()+[extra((0x40,0x84,0x42))])

    def test_multi_cell_unrelated_references_accepted(self):
        out=gate.census_nodes(nodes()+[extra((0x40,0x42,0x30))])
        self.assertEqual(out["iommu_parent_properties"],2)
        self.assertEqual(out["iommu_parent_cells"],4)
        self.assertEqual(out["dart1_mapper_declared_consumers"],1)

    def test_extra_unreferenced_dart1_child_rejected(self):
        extra_child=(gate.BASE.DART_PATHS[1]+"/unreviewed-mapper",
                     {"AAPL,phandle":cells(0x92)})
        self.reject(nodes()+[extra_child])

    def test_direct_dart1_controller_consumer_rejected(self):
        self.reject(nodes()+[extra((0x41,))])

    def test_repeated_wlan_mapper_reference_rejected(self):
        x=nodes()
        for path,p in x:
            if path==gate.BASE.WLAN:
                p["iommu-parent"]=cells(0x84,0x84)
        self.reject(x)

    def test_missing_wlan_parent_reference_rejected(self):
        x=nodes()
        for path,p in x:
            if path==gate.BASE.WLAN:p.pop("iommu-parent")
        self.reject(x)

    def test_wlan_uses_another_existing_dart_rejected(self):
        x=nodes()
        for path,p in x:
            if path==gate.BASE.WLAN:p["iommu-parent"]=cells(0x40)
        self.reject(x)

    def test_unresolved_other_parent_rejected(self):
        self.reject(nodes()+[extra((0xdead,))])

    def test_zero_parent_reference_rejected(self):
        self.reject(nodes()+[extra((0,))])

    def test_invalid_12byte_vector_with_unknown_rejected(self):
        self.reject(nodes()+[extra((0x40,0x41,0xdead))])

    def test_malformed_5byte_other_parent_rejected(self):
        self.reject(nodes()+[("/device-tree/arm-io/aux",{
            "AAPL,phandle":cells(0x91),
            "iommu-parent":b"abcde"})])

    def test_empty_iommu_parent_rejected(self):
        self.reject(nodes()+[("/device-tree/arm-io/aux",{
            "AAPL,phandle":cells(0x91),"iommu-parent":b""})])

    def test_too_many_cells_rejected(self):
        self.reject(nodes()+[extra(tuple([0x40]*33))])

    def test_duplicate_global_phandle_rejected(self):
        self.reject(nodes()+[extra((0x40,),phandle=0x84)])

    def test_zero_global_phandle_rejected(self):
        self.reject(nodes()+[extra((0x40,),phandle=0)])

    def test_missing_mapper_phandle_rejected(self):
        x=nodes()
        for path,p in x:
            if path==gate.BASE.MAPPER:p.pop("AAPL,phandle")
        self.reject(x)

    def test_malformed_global_phandle_rejected(self):
        x=nodes()
        for path,p in x:
            if path==gate.BASE.MAPPER:p["AAPL,phandle"]=b"123"
        self.reject(x)

    def test_noncanonical_source_silicon_rejected(self):
        with self.assertRaises(gate.BASE.RejectedADT):
            gate.audit_bytes(synth.fixture(host_compat=("apcie,s8003",)))

    def test_wlan_wrong_port_rejected_by_independent_gate(self):
        with self.assertRaises(gate.BASE.RejectedADT):
            gate.audit_bytes(synth.fixture(wlan_under_bridge=0))

    def test_corrupt_original_file_rejected(self):
        with self.assertRaises(Exception):
            gate.audit_bytes(b"not a valid original ADT")

    def test_input_file_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"fixture";f.write_bytes(synth.fixture())
            symlink=Path(temp)/"alias";symlink.symlink_to(f)
            with self.assertRaises(gate.InvalidMapperCensus):
                gate.private_file(symlink)

    def test_secret_private_adt_path_not_echoed(self):
        secret="SYNTHETIC_SECRET_PATH_991"
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/(secret+".bin")
            f.write_bytes(b"malformed synthetic original")
            done=subprocess.run([sys.executable,str(TOOL),str(f)],
                                text=True,capture_output=True,timeout=15)
            self.assertNotEqual(done.returncode,0)
            self.assertIn("FAIL_CLOSED",done.stderr)
            self.assertNotIn(secret,done.stdout+done.stderr)
            self.assertNotIn(str(f),done.stdout+done.stderr)

    def test_no_unsafe_ast_calls_in_tool(self):
        import ast
        tree=ast.parse(TOOL.read_text())
        blocked={"ioremap","readl","writel","mmap","ioctl",
                 "socket","Popen","system","write_bytes","execv","run"}
        for n in ast.walk(tree):
            if isinstance(n,ast.Call):
                name=(n.func.id if isinstance(n.func,ast.Name) else
                      n.func.attr if isinstance(n.func,ast.Attribute) else "")
                self.assertNotIn(name,blocked)

    def test_synthetic_unknown_props_not_echoed(self):
        out=nodes()
        for path,p in out:
            if path==gate.BASE.WLAN:p["private-key"]=b"SYNTHETIC_SUPER_SECRET"
        value=gate.census_nodes(out)
        self.assertNotIn("SYNTHETIC",str(value))

    def test_not_claiming_hardware_dma_stream_identity(self):
        src=TOOL.read_text()
        for needed in ("DART1_PHYSICAL_STREAM_ID_PROVEN=NO",
                       "DART1_ACTUAL_EXCLUSIVE_DMA_OWNERSHIP_PROVEN=NO",
                       "DART1_HARDWARE_INITIALIZATION_AUTHORIZED=NO"):
            self.assertIn(needed,src)

if __name__=="__main__":
    unittest.main()
