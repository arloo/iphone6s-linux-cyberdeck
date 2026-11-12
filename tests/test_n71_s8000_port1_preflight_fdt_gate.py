"""Strictly synthetic/nonbootable N71/S8000 PCIe port1 preflight DT tests."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_port1_preflight_fdt_gate.py"
DTS=ROOT/"examples/n71-pcie-port1/port1-preflight-disabled.dts"
GUARD=ROOT/"examples/n71-pcie-port1/pcie-apple-s8000-port1-preflight.c"

def load(path,alias):
    spec=importlib.util.spec_from_file_location(alias,path)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=obj
    spec.loader.exec_module(obj)
    return obj

G=load(TOOL,"n71_port1_preflight_gate")

def be32(n):
    return struct.pack(">I",n)

class TestN71S8000Port1Preflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("dtc"):
            raise RuntimeError("dtc required for actual compiled FDT")
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.path=Path(tmp.name)/"nonbootable-preflight.dtb"
        subprocess.run(["dtc","-q","-I","dts","-O","dtb","-o",
                        str(cls.path),str(DTS)],
                       capture_output=True,text=True,check=True,timeout=20)
        cls.blob=cls.path.read_bytes()
        cls.nodes=G.FDT.parse_fdt(cls.blob)

    def changed(self,key,value):
        nodes=copy.deepcopy(self.nodes)
        if value is None:
            nodes[G.PREFLIGHT].props.pop(key,None)
        else:
            nodes[G.PREFLIGHT].props[key]=value
        with self.assertRaises((G.UnsafePreflight,G.FDT.UnsafeTree)):
            G.validate_nodes(nodes)

    def test_actual_compiled_fdt_is_nonbootable_and_accepted(self):
        result=G.audit_bytes(self.blob)
        self.assertEqual(result["physical_descriptors"],3)
        self.assertFalse(result["hardware_activation_authorized"])
        self.assertTrue(result["status_disabled"])

    def test_actual_cli_on_compiled_fdt(self):
        p=subprocess.run([sys.executable,str(TOOL),str(self.path)],
                         capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0)
        self.assertIn("PREFLIGHT_FDT_OFFLINE_PASS",p.stdout)
        self.assertIn("HARDWARE_PROBE_MMIO_DART_RESET_PERMITTED=NO",p.stdout)

    def test_fails_on_enabled_status(self):
        self.changed("status",b"okay\0")

    def test_fails_on_missing_status(self):
        self.changed("status",None)

    def test_fails_on_m1_production_binding(self):
        self.changed("compatible",b"apple,pcie\0")

    def test_fails_on_direct_apple_s8000_native_binding(self):
        self.changed("compatible",b"apcie,s8000\0")

    def test_fails_on_missing_explicit_hardware_block(self):
        self.changed("research,hardware-activation-blocked",None)

    def test_fails_on_marker_with_nonempty_payload(self):
        self.changed("research,hardware-activation-blocked",b"1\0")

    def test_fails_on_wrong_wlan_port_index(self):
        self.changed("research,pcie-port-index",be32(0))

    def test_fails_on_storage_port0_index(self):
        self.changed("research,pcie-port-index",be32(2))

    def test_fails_on_guessed_dart_sid(self):
        self.changed("research,dart1-mapper-index",be32(1))

    def test_fails_on_refclk_time_units_guess(self):
        self.changed("research,refclk-to-perst-metadata",be32(1000))

    def test_fails_on_unreviewed_root_shared_resource(self):
        a=bytearray(self.nodes[G.PREFLIGHT].props["reg"])
        struct.pack_into(">II",a,0,0x6,0x00000000)
        self.changed("reg",bytes(a))

    def test_fails_on_storage_port0_resource(self):
        a=bytearray(self.nodes[G.PREFLIGHT].props["reg"])
        struct.pack_into(">II",a,0,0x6,0x01000000)
        self.changed("reg",bytes(a))

    def test_fails_on_baseband_port2_resource(self):
        a=bytearray(self.nodes[G.PREFLIGHT].props["reg"])
        struct.pack_into(">II",a,0,0x6,0x03000000)
        self.changed("reg",bytes(a))

    def test_fails_on_port3_resource(self):
        a=bytearray(self.nodes[G.PREFLIGHT].props["reg"])
        struct.pack_into(">II",a,0,0x6,0x04000000)
        self.changed("reg",bytes(a))

    def test_fails_on_wrong_dart1_resource(self):
        a=bytearray(self.nodes[G.PREFLIGHT].props["reg"])
        struct.pack_into(">II",a,32,0x6,0x02004000)
        self.changed("reg",bytes(a))

    def test_fails_on_more_than_3_resources(self):
        self.changed("reg",self.nodes[G.PREFLIGHT].props["reg"]+
                     struct.pack(">4I",0x6,0x00000000,0,0x8000))

    def test_fails_on_short_resource(self):
        self.changed("reg",self.nodes[G.PREFLIGHT].props["reg"][:-16])

    def test_fails_on_wrong_resource_names(self):
        self.changed("reg-names",b"port1-reg-a\0port1-reg-b\0shared-root\0")

    def test_fails_on_unreviewed_interrupts(self):
        self.changed("interrupts",be32(42))

    def test_fails_on_unreviewed_iommu(self):
        self.changed("iommus",be32(0))

    def test_fails_on_unreviewed_clock_enable(self):
        self.changed("clocks",be32(0x39))

    def test_fails_on_unreviewed_reset_controller(self):
        self.changed("resets",be32(0))

    def test_fails_on_unreviewed_dma_ranges(self):
        self.changed("dma-ranges",be32(0))

    def test_fails_on_renamed_node(self):
        nodes=copy.deepcopy(self.nodes)
        old=nodes.pop(G.PREFLIGHT)
        old.name="pcie-port1-preflight@603000000"
        old.path="/"+old.name
        nodes[old.path]=old
        with self.assertRaises(G.UnsafePreflight):
            G.validate_nodes(nodes)

    def test_fails_on_additional_endpoint_node(self):
        nodes=copy.deepcopy(self.nodes)
        nodes["/fake-wlan"]=G.FDT.Node(
            name="fake-wlan",path="/fake-wlan",
            props={"compatible":b"wlan-pcie,bcm4350\0"})
        with self.assertRaises(G.UnsafePreflight):
            G.validate_nodes(nodes)

    def test_fails_on_wrong_soc_apple_s8003(self):
        nodes=copy.deepcopy(self.nodes)
        nodes["/"].props["compatible"]=b"apple,n71\0apple,s8003\0"
        with self.assertRaises(G.UnsafePreflight):
            G.validate_nodes(nodes)

    def test_fails_on_wrong_address_cell_count(self):
        nodes=copy.deepcopy(self.nodes)
        nodes["/"].props["#address-cells"]=be32(1)
        with self.assertRaises(G.UnsafePreflight):
            G.validate_nodes(nodes)

    def test_fails_on_incorrect_status_type(self):
        self.changed("status",be32(0))

    def test_fails_closed_on_corrupt_fdt(self):
        with self.assertRaises(G.UnsafePreflight):
            G.audit_bytes(b"FAKE_DATA")

    def test_fails_closed_on_symlink_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            link=Path(tmp)/"link"
            link.symlink_to(self.path)
            cmd=subprocess.run([sys.executable,str(TOOL),str(link)],
                               capture_output=True,text=True,timeout=15)
            self.assertNotEqual(cmd.returncode,0)
            self.assertIn("FAIL_CLOSED",cmd.stderr)

    def test_original_linux_guard_source_has_no_hardware_actions(self):
        src=GUARD.read_text()
        executable=re.sub(r"/\*.*?\*/","",src,flags=re.S)
        executable=re.sub(r"//[^\n]*","",executable)
        self.assertIn("platform_get_resource_byname",executable)
        self.assertIn("of_property_read_u32",executable)
        self.assertIn("return -EOPNOTSUPP;",executable)
        for risk in ("ioremap","readl(","writel(","clk_prepare",
                     "reset_control","gpiod_","pci_host_probe",
                     "pci_scan","dma_map","dma_alloc","iommu_",
                     "request_irq(","pci_bus_","regulator_"):
            with self.subTest(risk=risk):
                self.assertNotIn(risk,executable)

    def test_compiled_fdt_contains_no_live_apple_pcie_binding(self):
        s=DTS.read_text()
        self.assertIn('status = "disabled";',s)
        self.assertNotIn('compatible = "apple,pcie"',s)
        self.assertNotIn('compatible = "apcie,s8000"',s)

    def test_hardware_cannot_be_inferred_from_fdt_only(self):
        src=TOOL.read_text()
        self.assertIn("LINUX_S8000_PCIE_LINK_AND_WLAN_INITIALIZED=NO",src)
        self.assertIn("HARDWARE_PROBE_MMIO_DART_RESET_PERMITTED=NO",src)

if __name__=="__main__":
    unittest.main()
