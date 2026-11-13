"""Synthetic Apple ADT tree and IOMMU phandle graph adversarial tests.

Uses invented small phandle numbers and fictitious third storage reference.
No original Apple ADT, firmware, hardware identities, MMIO or radios.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

SRC=Path(__file__).resolve().parents[1]/"tools/n71_original_apple_adt_iommu_parent_graph_gate.py"
sp=importlib.util.spec_from_file_location("n71_original_adt_graph_test",SRC)
assert sp and sp.loader
M=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=M
sp.loader.exec_module(M)

def u32(i:int)->bytes:return struct.pack("<I",i)
def node(name:str,attrs=None,children=()):
    properties={"name":name.encode()+b"\0",**(attrs or {})}
    out=bytearray(struct.pack("<II",len(properties),len(children)))
    for k,v in properties.items():
        key=k.encode()
        assert len(key)<32 and isinstance(v,bytes)
        out+=key.ljust(32,b"\0")+u32(len(v))+v
        out+=b"\0"*((-len(v))%4)
    for child in children:out+=child
    return bytes(out)

def specimen(*,wrong_wlan=False,wrong_modem=False,wrong_storage=False,
             wrong_port=False,wrong_index=False,duplicate_phandle=False,
             missing_wlan=False,dup_noncritical=False,dup_target=False):
    m0=11;m1=12;m2=13
    wi=u32(m0 if wrong_wlan else m1)
    mo=u32(m1 if wrong_modem else m2)
    s=u32(m1 if wrong_storage else m0)*2+u32(99)
    wlan=node("wlan",{"iommu-parent":wi})
    b0=node("pci-bridge0",{"apcie-port":u32(0)},[
        node("s3e",{"iommu-parent":s})])
    b1=node("pci-bridge1",{"apcie-port":u32(9 if wrong_port else 1)},
            [] if missing_wlan else [wlan])
    b2=node("pci-bridge2",{"apcie-port":u32(2)},[
        node("baseband-pcie",{"iommu-parent":mo})])
    apcie=node("apcie",children=[b0,b1,b2])
    da=[]
    for i,handle in enumerate((m0,m0 if duplicate_phandle else m1,m2)):
        ds=[node(f"mapper-apcie{i}",
                 {"AAPL,phandle":u32(handle),
                  "reg":u32(1 if wrong_index and i==1 else 0)})]
        if dup_target and i==1:ds.append(ds[0])
        da.append(node(f"dart-apcie{i}",children=ds))
    if dup_noncritical:da.append(node("other",children=[node("same"),node("same")]))
    return node("device-tree",children=[node("arm-io",children=[apcie,*da])])+b"\0"*128

def run(data:bytes)->bool:
    return M.verify_apple_logical_iommu_graph(M.parse_adt(data))

class TestN71OriginalAppleAdtGraph(unittest.TestCase):
    def test_synthetic_three_port_three_dart_graph(self):
        self.assertTrue(run(specimen()))
    def test_valid_adt_trailing_zero_padding(self):
        self.assertTrue(run(specimen()+b"\0"*100))
    def test_duplicate_noncritical_names_retained_independently(self):
        self.assertTrue(run(specimen(dup_noncritical=True)))
    def test_wrong_wlan_mapper_fails_closed(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(wrong_wlan=True))
    def test_wrong_modem_mapper_fails_closed(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(wrong_modem=True))
    def test_storage_cannot_be_mapped_to_wifi_dart(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(wrong_storage=True))
    def test_wrong_pcie_bridge_number_rejected(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(wrong_port=True))
    def test_nonzero_logical_wlan_mapper_index_rejected(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(wrong_index=True))
    def test_duplicate_mapper_phandle_rejected(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(duplicate_phandle=True))
    def test_missing_wlan_node_rejected(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(missing_wlan=True))
    def test_duplicated_target_mapper_path_rejected(self):
        with self.assertRaises(M.InvalidAdt):run(specimen(dup_target=True))
    def test_unexpected_nonzero_trailer_rejected(self):
        with self.assertRaises(M.InvalidAdt):M.parse_adt(specimen()+b"A")
    def test_truncated_binary_tree_rejected(self):
        with self.assertRaises(M.InvalidAdt):M.parse_adt(specimen()[:-300])
    def test_missing_actual_device_tree_root_rejected(self):
        fake=node("wrong-root",children=[node("arm-io")])+b"\0"*128
        with self.assertRaises(M.InvalidAdt):M.parse_adt(fake)
    def test_malicious_property_count_rejected(self):
        raw=bytearray(specimen());struct.pack_into("<I",raw,0,999_999)
        with self.assertRaises(M.InvalidAdt):M.parse_adt(bytes(raw))
    def test_malicious_size_overflow_rejected(self):
        raw=bytearray(specimen());struct.pack_into("<I",raw,40,0x7fffffff)
        with self.assertRaises(M.InvalidAdt):M.parse_adt(bytes(raw))
    def test_source_does_not_log_private_phandles(self):
        s=SRC.read_text()
        for sensitive in ("print(ref_to_path)", "print(parent)", "print(nodes)",
                          "print(data)", "print(ref)", "print(attrs)"):
            self.assertNotIn(sensitive,s)
        self.assertIn("N71_ORIGINAL_ADT_PARENT_PHANDLE_VALUES_OR_PRIVATE_CONTENT_EXPORTED=NO",s)
    def test_physical_link_not_automatically_claimed(self):
        s=SRC.read_text()
        self.assertIn("N71_PHYSICAL_PCIE_REQUESTER_TO_DART1_SID_PROVEN=NO",s)
        self.assertIn("N71_NATIVE_BCM4350_PCIE_WLAN_DATA_PATH_PROVEN=NO",s)
        self.assertIn("N71_PHONE_MMIO_RESET_DMA_FIRMWARE_OR_NAND_ACTION=NO",s)

if __name__=="__main__":unittest.main()
