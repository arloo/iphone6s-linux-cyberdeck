"""Synthetic adversarial regression for N71 original port1/DART1 reverse chain.

No original Apple private data, firmware or physical iPhone is used.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_original_port1_dart1_reverse_chain_gate.py"
spec=importlib.util.spec_from_file_location("n71_final_reverse_test",SRC)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

def u32(x):return struct.pack("<I",x)

def fake_nodes():
    a=M.ADT_GRAPH
    prefix="/device-tree/arm-io/"
    return {
        a.MAPPER0:{"AAPL,phandle":u32(11),"reg":u32(0)},
        a.MAPPER1:{"AAPL,phandle":u32(12),"reg":u32(0)},
        a.MAPPER2:{"AAPL,phandle":u32(13),"reg":u32(0)},
        a.PORT0:{"iommu-parent":u32(11)+u32(11)+u32(99)},
        a.PORT1:{"iommu-parent":u32(12)},
        a.PORT2:{"iommu-parent":u32(13)},
        prefix+"apcie/pci-bridge0":{"apcie-port":u32(0)},
        prefix+"apcie/pci-bridge1":{"apcie-port":u32(1)},
        prefix+"apcie/pci-bridge2":{"apcie-port":u32(2)},
        prefix+"nvme-mmu0":{"AAPL,phandle":u32(99)},
    }

def fake_port():
    return {
        "IOPCIConfigured":True,
        "IOPCIResourced":True,
        "apcie-port":u32(1),
        "vendor-id":u32(0x106b),
        "device-id":u32(0x1004),
        "IOPCIExpressLinkStatus":0x1011,
    }

class TestN71OriginalPort1Dart1Reverse(unittest.TestCase):
    def test_synthetic_all_three_darts_with_storage_nvme_mmu(self):
        self.assertTrue(M.verify_dart1_exclusive(fake_nodes()))
    def test_dart1_only_wlan_node_allowed(self):
        d=fake_nodes()
        d["/device-tree/arm-io/other"]={"iommu-parent":u32(12)}
        with self.assertRaises(M.UnprovenHardware):M.verify_dart1_exclusive(d)
    def test_storage_must_not_alias_dart1(self):
        d=fake_nodes();d[M.ADT_GRAPH.PORT0]["iommu-parent"]=u32(11)+u32(11)+u32(12)
        with self.assertRaises(M.UnprovenHardware):M.verify_dart1_exclusive(d)
    def test_dart2_modem_must_not_alias_dart1(self):
        d=fake_nodes();d[M.ADT_GRAPH.PORT2]["iommu-parent"]=u32(12)
        with self.assertRaises((M.UnprovenHardware,M.ADT_GRAPH.InvalidAdt)):
            M.verify_dart1_exclusive(d)
    def test_third_storage_parent_must_be_nvme_mmu(self):
        d=fake_nodes();d["/device-tree/arm-io/nvme-mmu0"]["AAPL,phandle"]=u32(98)
        with self.assertRaises(M.UnprovenHardware):M.verify_dart1_exclusive(d)
    def test_truncated_storage_parent_fail_closed(self):
        d=fake_nodes();d[M.ADT_GRAPH.PORT0]["iommu-parent"]=u32(11)+u32(11)
        with self.assertRaises((M.UnprovenHardware,M.ADT_GRAPH.InvalidAdt)):
            M.verify_dart1_exclusive(d)
    def test_malformed_extra_iommu_parent_cell_fail_closed(self):
        d=fake_nodes();d["/device-tree/arm-io/malformed"]={"iommu-parent":b"\x01"}
        with self.assertRaises(M.UnprovenHardware):M.verify_dart1_exclusive(d)
    def test_duplicate_handle_fail_closed(self):
        d=fake_nodes();d["/device-tree/arm-io/duplicate"]={"AAPL,phandle":u32(12)}
        with self.assertRaises((M.UnprovenHardware,M.ADT_GRAPH.InvalidAdt)):
            M.verify_dart1_exclusive(d)
    def test_original_ios_gen1_x1_link_model(self):
        self.assertTrue(M.verify_ios_link(fake_port()))
    def test_not_configured_rejected(self):
        b=fake_port();b["IOPCIConfigured"]=False
        with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_not_resourced_rejected(self):
        b=fake_port();b["IOPCIResourced"]=False
        with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_other_port_rejected(self):
        b=fake_port();b["apcie-port"]=u32(2)
        with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_wrong_root_vendor_or_device_rejected(self):
        for field,value in (("vendor-id",u32(0x14e4)),("device-id",u32(0x9999))):
            with self.subTest(field=field):
                b=fake_port();b[field]=value
                with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_gen2_or_x2_link_rejected(self):
        for status in (0x1012,0x1021,0x1022):
            with self.subTest(status=status):
                b=fake_port();b["IOPCIExpressLinkStatus"]=status
                with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_unstable_training_rejected(self):
        b=fake_port();b["IOPCIExpressLinkStatus"]=0x1811
        with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_invalid_link_metadata_type_rejected(self):
        for value in (True,0x1011.to_bytes(2,"little"),"0x1011",None,-1,65536):
            with self.subTest(value=value):
                b=fake_port();b["IOPCIExpressLinkStatus"]=value
                with self.assertRaises(M.UnprovenHardware):M.verify_ios_link(b)
    def test_bad_macho_source_must_fail_closed(self):
        with self.assertRaises((M.UnprovenHardware,ValueError,KeyError,
                                IndexError,struct.error,AssertionError)):
            M.source_provider_chain(b"not Apple Mach-O")
    def test_original_port1_selector_offline_matches_source(self):
        self.assertEqual(M.ROOT_CONTROL.offsets(1),
                         {2:0x180,3:0x194,4:0x1a4,5:0x1ac})
    def test_no_physical_sid_or_wifi_claim(self):
        src=SRC.read_text()
        for text in ("N71_DART1_PHYSICAL_REQUESTER_SID_OR_CLOCK_RESET_ISOLATION_PROVEN=NO",
                     "N71_LINUX_NATIVE_BCM4350_PCIE_WIFI_PROVEN=NO",
                     "N71_NO_PHONE_MMIO_DMA_REBOOT_OR_NAND=YES"):
            self.assertIn(text,src)
    def test_no_phone_operations_in_script(self):
        src=SRC.read_text()
        for unsafe in ("import subprocess","os.system(","/dev/mem",
                       "insmod(", "modprobe(", "palera1n ", "readl(",
                       "writel(", "pci_host_probe("):
            self.assertNotIn(unsafe,src)

if __name__=="__main__":unittest.main()
