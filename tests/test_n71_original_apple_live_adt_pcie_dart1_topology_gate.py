"""Strict synthetic adversarial tests for original Apple N71 ADT comparisons."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_original_apple_live_adt_pcie_dart1_topology_gate.py"
spec=importlib.util.spec_from_file_location("n71_live_adt_gate_test",TOOL)
G=importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name]=G
spec.loader.exec_module(G)

def field(key:str,value:bytes)->bytes:
    blob=key.encode().ljust(32,b"\0")+struct.pack("<I",len(value))+value
    return blob+b"\0"*((-len(blob))%4)

def node(name:str,children=(),**attrs)->bytes:
    props=[field("name",name.encode()+b"\0")]
    props.extend(field(k.replace("__","-"),v) for k,v in attrs.items())
    return struct.pack("<II",len(props),len(children))+b"".join(props)+b"".join(children)

def regs(*ranges)->bytes:
    return b"".join(struct.pack("<QQ",addr,size) for addr,size in ranges)

def synthetic(extra=b"BASE",dart_addr=G.WINDOW_DART1,
              port1_addr=G.WINDOW_A,missing_wlan=False,
              alter_wlan=False,extra_pcie=b"UNCHANGED")->bytes:
    wlan=node("wlan",revision=b"ALT" if alter_wlan else b"C5")
    bridge=node("pci-bridge1",() if missing_wlan else (wlan,))
    root=node("apcie",(bridge,),
              reg=regs((0x610000000,0x1000000),
                       (port1_addr,0x4000),(G.WINDOW_B,0x4000)),
              metadata=extra_pcie)
    dart=node("dart-apcie1",reg=regs((dart_addr,0x4000)))
    unrelated=node("unrelated",boot_token=extra)
    return node("device-tree",(
        node("arm-io",(root,dart,unrelated)),))+b"\0"*80

class TestLiveAppleADTTopologyGate(unittest.TestCase):
    def test_exact_equal_synthetic(self):
        a=synthetic()
        result=G.compare(a,a)
        self.assertEqual(result.changed_non_pcie_properties,0)
        self.assertGreater(result.relevant_properties,0)

    def test_different_unrelated_boot_state_accepted(self):
        result=G.compare(synthetic(),synthetic(extra=b"LATER"))
        self.assertEqual(result.changed_non_pcie_properties,1)

    def test_changed_dart1_window_rejected(self):
        with self.assertRaises(G.TopologyNotProven):
            G.compare(synthetic(),synthetic(dart_addr=0x601008000))

    def test_changed_port1_window_rejected(self):
        with self.assertRaises(G.TopologyNotProven):
            G.compare(synthetic(),synthetic(port1_addr=0x601000000))

    def test_changed_wlan_firmware_revision_rejected(self):
        with self.assertRaises(G.TopologyNotProven):
            G.compare(synthetic(),synthetic(alter_wlan=True))

    def test_changed_unknown_pcie_property_rejected(self):
        with self.assertRaises(G.TopologyNotProven):
            G.compare(synthetic(),synthetic(extra_pcie=b"CHANGE"))

    def test_missing_wlan_child_rejected(self):
        with self.assertRaises(G.TopologyNotProven):
            G.compare(synthetic(),synthetic(missing_wlan=True))

    def test_invalid_root_magic_or_too_short_rejected(self):
        for b in (b"",b"\0"*8,b"INVALID"):
            with self.subTest(size=len(b)):
                with self.assertRaises(G.TopologyNotProven):
                    G.parse_all(b)

    def test_reject_nonzero_trailing_padding(self):
        with self.assertRaises(G.TopologyNotProven):
            G.parse_all(synthetic()+b"X")

    def test_private_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/"fake";src.write_bytes(synthetic())
            symlink=Path(t)/"symbolic";symlink.symlink_to(src)
            with self.assertRaises(G.TopologyNotProven):
                G.read_private(symlink)

    def test_private_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(G.TopologyNotProven):
                G.read_private(Path(t)/"missing")

    def test_nothing_prints_original_properties(self):
        s=TOOL.read_text()
        self.assertIn("DART1_MMIO_AND_WLAN_RADIO_ACTIONS_PERFORMED=NO",s)
        self.assertIn("HARDWARE_REQUESTER_TO_SID_AND_DMA_FUNCTIONALITY_PROVEN=NO",s)
        for bad in ("print(blob)","print(original)","print(live)","print(a_props)","print(b_props)"):
            self.assertNotIn(bad,s)

if __name__=="__main__":
    unittest.main()
