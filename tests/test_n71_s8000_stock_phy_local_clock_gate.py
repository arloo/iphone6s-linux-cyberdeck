# SPDX-License-Identifier: MIT
"""Synthetic, no-device, no-Apple-binary regressions for S8000 source gate."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import n71_s8000_stock_phy_local_clock_gate as gate

def stock_mock():
    phy_offsets=(0x108,0x118,0x308,0x318,0x518,0x1a18,0x1a58)
    phy_offsets+=tuple(0x2000+i*4 for i in range(34))
    def records(offsets):
        return b"".join(gate.TUNE.pack(x,4,0xff,0x55) for x in offsets)
    root=gate.ADT.ROOT
    resource=(
        ((0x610000000,0x1000000),)+
        tuple((x,0x4000) for x in gate.PORT_WINDOWS)+
        ((gate.APP_ROOT_PHYS,0x8000),(gate.APP_PHY_PHYS,0x4000))
    )
    common={"compatible":b"apcie,s8000\0",
            "reg":b"".join(struct.pack("<QQ",*r) for r in resource),
            "clock-gates":struct.pack("<6I",*gate.STOCK_CLOCK_IDS),
            "power-gates":struct.pack("<I",0x38),
            "apcie-phy-tunables":records(phy_offsets),
            "apcie-common-tunables":records(tuple(0x100+i*4 for i in range(34)))}
    devices=bytearray(103*48)
    for i in range(103):
        devices[48*i+3]=i+1
        name=f"OTHER{i+1:02x}".encode()
        if i+1 in gate.STOCK_CLOCK_IDS:
            name=gate.STOCK_CLOCK_DEVICES[i+1-gate.STOCK_CLOCK_IDS[0]].encode()
        devices[48*i+32:48*i+32+len(name)]=name
    clocks=bytearray(9*24)
    struct.pack_into("<I",clocks,5*24,0x06010022)
    clocks[5*24+8:5*24+16]=b"PCIE_APP"
    nodes={root+"apcie":common,root+"pmgr":{
        "clocks":bytes(clocks),"devices":bytes(devices)}}
    c=records((0x90,0x130,0x134,0x138,0x13c,0x140))
    r=records((0x98,0x154))
    for port in range(3):
        nodes[root+f"apcie/pci-bridge{port}"]={
            "apcie-config-tunables":c,"pcie-rc-tunables":r}
    return nodes

class S8000PHYLocalClockGateTests(unittest.TestCase):
    def test_valid_full_stock_graph(self):
        result=gate.verify_nodes(stock_mock())
        self.assertEqual(result["phy_records"],41)
        self.assertEqual(result["per_port_config_records"],6)
        self.assertEqual(result["per_port_root_records"],2)
    def test_wrong_soc_rejected(self):
        nodes=stock_mock();nodes[gate.ADT.ROOT+"apcie"]["compatible"]=b"apcie,s8003\0"
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_missing_shared_phy_resource_rejected(self):
        nodes=stock_mock();b=bytearray(nodes[gate.ADT.ROOT+"apcie"]["reg"]);b[10*16]^=1
        nodes[gate.ADT.ROOT+"apcie"]["reg"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_port0_physical_bank_changed(self):
        nodes=stock_mock();b=bytearray(nodes[gate.ADT.ROOT+"apcie"]["reg"]);b[16]^=2
        nodes[gate.ADT.ROOT+"apcie"]["reg"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_malformed_phy_record_count(self):
        nodes=stock_mock();n=nodes[gate.ADT.ROOT+"apcie"]
        n["apcie-phy-tunables"]=n["apcie-phy-tunables"][:-gate.TUNE.size]
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_phy_duplicated_offset(self):
        nodes=stock_mock();n=nodes[gate.ADT.ROOT+"apcie"]
        b=bytearray(n["apcie-phy-tunables"])
        struct.pack_into("<I",b,gate.TUNE.size,struct.unpack_from("<I",b,0)[0])
        n["apcie-phy-tunables"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_invalid_mask_value(self):
        nodes=stock_mock();n=nodes[gate.ADT.ROOT+"apcie"]
        b=bytearray(n["apcie-phy-tunables"])
        struct.pack_into("<Q",b,16,0x100)
        n["apcie-phy-tunables"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_root_power_id_must_match(self):
        nodes=stock_mock();nodes[gate.ADT.ROOT+"apcie"]["power-gates"]=struct.pack("<I",0x39)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_clock_gate_ancestry_changed(self):
        nodes=stock_mock();nodes[gate.ADT.ROOT+"apcie"]["clock-gates"]=struct.pack("<6I",0x39,0x3a,0x3c,0x3d,0x3e,0x40)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_pcie_app_clock_name_changed(self):
        nodes=stock_mock();p=nodes[gate.ADT.ROOT+"pmgr"];b=bytearray(p["clocks"])
        b[5*24+8:5*24+16]=b"PCIE_OFF"
        p["clocks"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_missing_port0_tunables(self):
        nodes=stock_mock();del nodes[gate.ADT.ROOT+"apcie/pci-bridge0"]
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_baseband_tunables_mismatch(self):
        nodes=stock_mock();p=nodes[gate.ADT.ROOT+"apcie/pci-bridge2"]
        b=bytearray(p["apcie-config-tunables"]);b[-1]^=1
        p["apcie-config-tunables"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)
    def test_root_shared_status_cannot_be_tuned(self):
        nodes=stock_mock();p=nodes[gate.ADT.ROOT+"apcie"]
        b=bytearray(p["apcie-common-tunables"])
        struct.pack_into("<I",b,0,0x2c)
        p["apcie-common-tunables"]=bytes(b)
        with self.assertRaises(gate.RejectedSource):gate.verify_nodes(nodes)

if __name__=="__main__":
    unittest.main()
