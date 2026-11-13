#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read an OWNER-PRIVATE Apple ADT and prove the N71 logical PCIe/DART graph.

This tool accepts an authentic, owner-provided Apple Device Tree *file* on
the local workstation. It does not export the ADT, phandle identifiers,
calibration, firmware, serial, MAC, raw MMIO registers, or private fields.

All relationships here are logical original-iOS IOMMU references only;
physical PCIe requester-to-DART SID, bus training, root port reset
isolation and runtime WLAN functionality remain UNPROVEN.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import sys

ROOT="/device-tree/arm-io/"
PORT0=ROOT+"apcie/pci-bridge0/s3e"
PORT1=ROOT+"apcie/pci-bridge1/wlan"
PORT2=ROOT+"apcie/pci-bridge2/baseband-pcie"
MAPPER0=ROOT+"dart-apcie0/mapper-apcie0"
MAPPER1=ROOT+"dart-apcie1/mapper-apcie1"
MAPPER2=ROOT+"dart-apcie2/mapper-apcie2"
PARENT="iommu-parent"
HANDLE="AAPL,phandle"

class InvalidAdt(ValueError):pass

def require(ok,reason):
    if not ok:raise InvalidAdt(reason)

def parse_adt(data:bytes)->dict[str,dict[str,bytes]]:
    require(type(data) is bytes and 100<len(data)<=2_000_000,
            "Unexpected input Apple ADT extent")
    nodes={}
    counter=[0]
    def node(offset:int,parent:str,depth:int)->int:
        require(depth<40 and offset+8<=len(data),"ADT node header out of bounds")
        nprop,nchild=struct.unpack_from("<II",data,offset);offset+=8
        require(nprop<=300 and nchild<=300,"Unbounded ADT node count")
        counter[0]+=1
        require(counter[0]<=4096,"Unbounded ADT traversal")
        props={}
        for _ in range(nprop):
            require(offset+36<=len(data),"ADT attribute header incomplete")
            key=data[offset:offset+32].split(b"\0",1)[0]
            require(0<len(key)<32 and key.isascii(),"Invalid ADT key name")
            prop_name=key.decode("ascii")
            count=struct.unpack_from("<I",data,offset+32)[0]&0x7fffffff
            offset+=36
            require(count<=len(data)-offset,"ADT property extends beyond source")
            require(prop_name not in props,"Duplicated ADT property")
            props[prop_name]=data[offset:offset+count]
            offset=(offset+count+3)&~3
        name=props.get("name",b"").split(b"\0",1)[0]
        require(name and name.isascii() and b"/" not in name and
                len(name)<128, "Malformed ADT node name")
        full=parent+"/"+name.decode("ascii")
        if full in nodes:
            # The Apple ADT contains some duplicate non-critical node names.
            # Preserve each independently for global phandle uniqueness.
            require(full not in (PORT0,PORT1,PORT2,MAPPER0,MAPPER1,MAPPER2),
                    "Duplicated critical Apple port or mapper")
            suffix=1
            while f"{full}#duplicate{suffix}" in nodes:suffix+=1
            full=f"{full}#duplicate{suffix}"
        nodes[full]=props
        for _ in range(nchild):
            offset=node(offset,full,depth+1)
        return offset
    end=node(0,"",0)
    # Original stock Apple ADTs often reserve a zero-filled trailing buffer.
    require(all(byte==0 for byte in data[end:]),
            "Nonzero suffix after the parsed tree")
    require("/device-tree" in nodes,"No Apple ADT root")
    return nodes

def verify_apple_logical_iommu_graph(nodes:dict[str,dict[str,bytes]])->bool:
    for path in (PORT0,PORT1,PORT2,MAPPER0,MAPPER1,MAPPER2):
        require(path in nodes,"Expected original Apple port or mapper missing")
    ref_to_path={}
    for path,attrs in nodes.items():
        if HANDLE not in attrs:continue
        ref=attrs[HANDLE]
        require(type(ref) is bytes and len(ref)==4,
                "Original Apple phandle is not a 4-byte reference")
        require(ref not in ref_to_path,"Duplicate Apple phandle")
        ref_to_path[ref]=path
    require(len(ref_to_path)>=3,"Required Apple DART mapper phandles incomplete")
    for path,number in (
        (ROOT+"apcie/pci-bridge0",0),
        (ROOT+"apcie/pci-bridge1",1),
        (ROOT+"apcie/pci-bridge2",2),
    ):
        require(path in nodes and
                nodes[path].get("apcie-port")==number.to_bytes(4,"little"),
                "Wrong Apple original PCIe bridge port index")
    for path in (MAPPER0,MAPPER1,MAPPER2):
        require(nodes[path].get("reg")==b"\0"*4,
                "Apple original DART mapper logical index is not zero")
    def owned_reference(path:str,expected_mapper:str):
        parent=nodes[path].get(PARENT,b"")
        require(len(parent)==4,"Single-master IOMMU parent is not one phandle")
        require(ref_to_path.get(parent)==expected_mapper,
                "Original Apple IOMMU link does not resolve to expected mapper")
    owned_reference(PORT1,MAPPER1)
    owned_reference(PORT2,MAPPER2)
    # Storage carries three IOMMU parent cells; two explicitly reference
    # DART0's logical mapper; the third is intentionally *not* inferred.
    storage=nodes[PORT0].get(PARENT,b"")
    require(len(storage)==12,"Storage Apple IOMMU parent fanout changed")
    require(ref_to_path.get(storage[:4])==MAPPER0 and
            ref_to_path.get(storage[4:8])==MAPPER0,
            "Original storage IOMMU first two links not DART0")
    require(nodes[MAPPER0][HANDLE]!=nodes[MAPPER1][HANDLE] and
            nodes[MAPPER1][HANDLE]!=nodes[MAPPER2][HANDLE] and
            nodes[MAPPER0][HANDLE]!=nodes[MAPPER2][HANDLE],
            "DART0/1/2 must have distinct logical phandles")
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("owner_private_apple_runtime_adt",type=Path)
    args=p.parse_args()
    try:
        f=args.owner_private_apple_runtime_adt
        require(f.is_file() and not f.is_symlink() and f.stat().st_size<=2_000_000,
                "No private ADT, or unsafe symlink")
        verify_apple_logical_iommu_graph(parse_adt(f.read_bytes()))
    except (InvalidAdt,OSError,UnicodeError,struct.error,RecursionError):
        print("N71_ORIGINAL_APPLE_ADT_LOGICAL_IOMMU_GRAPH_NOT_PROVEN",file=sys.stderr)
        return 2
    print("N71_ORIGINAL_APPLE_ADT_LOGICAL_PCIE_DART_GRAPH_PASS")
    print("N71_STORAGE_PCIE_BRIDGE0_TO_DART0_LOGICAL_MAPPER_PASS=YES")
    print("N71_WLAN_PCIE_BRIDGE1_TO_DART1_LOGICAL_MAPPER_PASS=YES")
    print("N71_BASEBAND_PCIE_BRIDGE2_TO_DART2_LOGICAL_MAPPER_PASS=YES")
    print("N71_ORIGINAL_APPLE_DART0_DART1_DART2_MAPPERS_DISTINCT=YES")
    print("N71_THREE_APPLE_DART_MAPPER_LOGICAL_INDEX_ZERO_PASS=YES")
    print("N71_ORIGINAL_ADT_PARENT_PHANDLE_VALUES_OR_PRIVATE_CONTENT_EXPORTED=NO")
    print("N71_PHYSICAL_PCIE_REQUESTER_TO_DART1_SID_PROVEN=NO")
    print("N71_NATIVE_BCM4350_PCIE_WLAN_DATA_PATH_PROVEN=NO")
    print("N71_PHONE_MMIO_RESET_DMA_FIRMWARE_OR_NAND_ACTION=NO")
    return 0

if __name__=="__main__":raise SystemExit(main())
