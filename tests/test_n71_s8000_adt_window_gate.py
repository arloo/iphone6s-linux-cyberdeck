"""Synthetic S8000 Apple ADT physical-window and DART mapping safety tests.

No real Apple ADT, device firmware, MAC, serial, or calibration is used.
"""
from __future__ import annotations
import copy
import importlib.util
import io
import struct
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_s8000_adt_window_gate.py"
spec=importlib.util.spec_from_file_location("n71_a9_windows",TOOL)
module=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def cells(*values):
    return struct.pack("<"+"I"*len(values),*values)


def regs(*windows):
    return b"".join(struct.pack("<QQ",base,size) for base,size in windows)


def prop(key,value):
    return (key.encode("ascii").ljust(32,b"\0") +
            struct.pack("<I",len(value)) + value +
            b"\0"*((-len(value))%4))


PHANDLE_BY_NODE = {
    "device-tree": 0x01,
    "arm-io": 0x02,
    "apcie": 0x03,
    "pci-bridge0": 0x30,
    "pci-bridge1": 0x31,
    "pci-bridge2": 0x32,
    "wlan": 0x33,
    "dart-apcie0": 0x40,
    "dart-apcie1": 0x41,
    "dart-apcie2": 0x42,
    "mapper-apcie1": 0x84,
}

def node(name,properties=(),children=(),phandle=None):
    if phandle is None:
        phandle=PHANDLE_BY_NODE[name]
    allprops=(("name",name.encode()+b"\0"),
              ("AAPL,phandle",cells(phandle)),*properties)
    return (struct.pack("<II",len(allprops),len(children))+
            b"".join(prop(k,v) for k,v in allprops)+
            b"".join(children))


def compat(*labels):
    return b"".join(x.encode("ascii")+b"\0" for x in labels)


def fixture(*,host_windows=None,host_compat=None,dart_layout=None,
            dart1_compat=None,wlan_compat=None,mapper_id=0,
            iommu_parent=0x84,port_count=4,skip_dart=None,
            wlan_under_bridge=1,secret=False,mapper_phandle=0x84,
            mapper_iommu_id=None,dart_page_size=4096,
            dart_vm_size=0x3ffff000):
    host_windows=host_windows or module.HOST_LAYOUT
    dart_layout=dart_layout or module.DART_LAYOUT
    bridge_children=[]
    for n in range(3):
        children=[]
        if n==wlan_under_bridge:
            extras=[
                ("compatible",compat(*(wlan_compat or
                                    ("wlan-pcie,bcm4350","wlan-pcie,bcm")))),
                ("iommu-parent",cells(iommu_parent)),
            ]
            if secret:
                extras.append(("private-key",b"DO_NOT_PUBLISH_PRIVATE_VALUE"))
            children.append(node("wlan",extras))
        bridge_children.append(node(f"pci-bridge{n}",children=children))
    host=node("apcie",[
        ("compatible",compat(*(host_compat or ("apcie,s8000",)))),
        ("reg",regs(*host_windows)),
        ("#ports",cells(port_count)),
        ("bus-range",cells(0,8)),
        ("interrupts",cells(0xf4,0xf7,0xfa,0xfd)),
        ("msi-vector-offset",cells(0x100)),
        ("clock-gates",cells(0x39,0x3a,0x3b,0x3c,0x3d,0x3e)),
        ("power-gates",cells(0x38)),
    ],bridge_children)
    darts=[]
    for n in range(3):
        if n==skip_dart:continue
        props=[
            ("compatible",compat(*(dart1_compat if n==1 and dart1_compat is not None
                                      else ("dart,s8000","dart,s5l8960x")))),
            ("reg",regs(dart_layout[n])),
            ("interrupts",cells(0xf5+3*n)),
        ]
        if n==1:
            props.extend([
                ("page-size",cells(dart_page_size)),
                ("vm-size",cells(dart_vm_size)),
            ])
        mapper_props=[
            ("compatible",compat("iommu-mapper")),
            ("reg",cells(mapper_id)),
        ]
        if mapper_iommu_id is not None:
            mapper_props.append(("iommu-id",cells(mapper_iommu_id)))
        descendants=[node("mapper-apcie1",mapper_props,
                          phandle=mapper_phandle)] if n==1 else []
        darts.append(node(f"dart-apcie{n}",props,descendants))
    arm=node("arm-io",children=[host,*darts])
    return node("device-tree",children=[arm])


class TestS8000ADTWindowGate(unittest.TestCase):
    def assert_reject(self,blob):
        with self.assertRaises(module.RejectedADT):
            module.audit_bytes(blob)

    def test_known_window_topology_passes_and_is_blocked_for_hw(self):
        output=module.audit_bytes(fixture())
        self.assertIn("S8000_ADT_METADATA_GATE_PASS",output)
        self.assertIn("DART1_FALLBACK=dart,s5l8960x",output)
        self.assertIn("HARDWARE_BLOCKED",output)
        self.assertIn("WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED",output)
        self.assertIn("DART1_PAGE_SIZE=4096",output)
        self.assertIn("DART1_VM_SIZE=0x3ffff000",output)

    def test_wrong_foundry_or_host_rejected(self):
        for value in (("apcie,s8003",),("apcie,t8103",),("apple,pcie",)):
            with self.subTest(value=value):
                self.assert_reject(fixture(host_compat=value))

    def test_four_ports_required(self):
        self.assert_reject(fixture(port_count=3))

    def test_port1_register_mapping_changed_rejected(self):
        w=list(module.HOST_LAYOUT)
        w[3]=(0x601000000,0x4000)
        self.assert_reject(fixture(host_windows=tuple(w)))

    def test_dart1_window_moved_rejected(self):
        d=dict(module.DART_LAYOUT)
        d[1]=(0x603008000,0x4000)
        self.assert_reject(fixture(dart_layout=d))

    def test_dart1_fallback_family_required(self):
        for v in (("dart,s8000",),("dart,t8103",),("dart,s8000","dart,t8103")):
            with self.subTest(compat=v):
                self.assert_reject(fixture(dart1_compat=v))

    def test_dart1_missing_rejected(self):
        self.assert_reject(fixture(skip_dart=1))

    def test_wlan_not_allowed_on_storage_port0(self):
        self.assert_reject(fixture(wlan_under_bridge=0))

    def test_wlan_not_allowed_on_modem_port2(self):
        self.assert_reject(fixture(wlan_under_bridge=2))

    def test_only_bcm4350_wlan_compatible(self):
        self.assert_reject(fixture(wlan_compat=("wlan-pcie,bcm4360",)))

    def test_wlan_iommu_reference_must_be_nonzero(self):
        self.assert_reject(fixture(iommu_parent=0))

    def test_wlan_cannot_point_directly_to_dart1(self):
        self.assert_reject(fixture(iommu_parent=0x41))

    def test_wlan_cannot_reference_dart0_storage(self):
        self.assert_reject(fixture(iommu_parent=0x40))

    def test_wlan_cannot_reference_unknown_node(self):
        self.assert_reject(fixture(iommu_parent=0xdead))

    def test_wrong_mapper_phandle_rejected(self):
        self.assert_reject(fixture(mapper_phandle=0x85))

    def test_duplicate_global_phandle_rejected(self):
        self.assert_reject(fixture(mapper_phandle=0x31))

    def test_unreviewed_mapper_iommu_id_override_rejected(self):
        self.assert_reject(fixture(mapper_iommu_id=0x85))

    def test_wlan_dart_page_size_must_be_4k(self):
        self.assert_reject(fixture(dart_page_size=16384))

    def test_wlan_dart_vm_size_must_match_s8000_adt(self):
        self.assert_reject(fixture(dart_vm_size=0x40000000))

    def test_mapper_reg_index_must_remain_zero(self):
        self.assert_reject(fixture(mapper_id=1))

    def test_private_unknown_properties_not_echoed(self):
        test_data=fixture(secret=True)
        self.assertIn(b"DO_NOT_PUBLISH_PRIVATE_VALUE",test_data)
        result=module.audit_bytes(test_data)
        self.assertNotIn("DO_NOT_PUBLISH_PRIVATE_VALUE",result)

    def test_overlap_guard_rejects_protected_port_collision(self):
        with self.assertRaises(module.RejectedADT):
            module.disjoint([
                ("storage",0x601000000,0x4000),
                ("wlan",0x601000000,0x4000),
            ])

    def test_overlap_guard_rejects_dart_collision(self):
        with self.assertRaises(module.RejectedADT):
            module.disjoint([
                ("wlan",0x602004000,0x4000),
                ("dart1",0x602006000,0x4000),
            ])

    def test_disjoint_port1_dart_and_storage(self):
        module.disjoint([
            ("storage",0x601000000,0x8000),
            ("wlan-control",0x602000000,0x4000),
            ("wlan-aux",0x602004000,0x4000),
            ("dart1",0x602008000,0x4000),
            ("modem",0x603000000,0x8000),
        ])

    def test_corrupt_or_short_private_adt_rejected(self):
        self.assert_reject(fixture()[:70])

    def test_structural_broken_adt_header_rejected(self):
        raw=bytearray(fixture())
        raw[:8]=b"\\xff"*8
        self.assert_reject(bytes(raw))

    def test_no_live_memory_or_controller_writes(self):
        text=TOOL.read_text()
        for forbidden in ("/dev/mem","/dev/kmem","/dev/mtd",
                          "mmap(","iowrite","writel(","setpci",
                          "ioremap(", "ctypes.CDLL(", "subprocess.run("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,text)


if __name__=="__main__":
    unittest.main()
