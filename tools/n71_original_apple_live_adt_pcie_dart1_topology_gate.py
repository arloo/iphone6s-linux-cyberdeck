#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed comparison of owner-private N71 Apple ADTs without disclosing them.

Original ARM64 Apple PCIe, DART1 and WLAN subtrees are compared using EVERY
raw property value, not only properties understood by a Linux DTB parser.
Differences elsewhere are counted but NOT printed: they may contain private
board identifiers, boot state or calibration. NO iPhone hardware access.
"""
from __future__ import annotations
from dataclasses import dataclass
import argparse
import os
from pathlib import Path
import struct
import sys

LIMIT=16*1024*1024
MAX_LEVELS=40
MAX_NODES=4096
MAX_PROPS=4096
PREFIXES=("/device-tree/arm-io/apcie",
          "/device-tree/arm-io/dart-apcie1")
WINDOW_A=0x602000000
WINDOW_B=0x602004000
WINDOW_DART1=0x602008000
WINDOW_SIZE=0x4000

class TopologyNotProven(ValueError):
    pass

@dataclass(frozen=True)
class Check:
    nodes:int
    changed_non_pcie_properties:int
    relevant_properties:int

def fail(cond,reason):
    if not cond:raise TopologyNotProven(reason)

def read_private(path:Path)->bytes:
    fail(path.is_file() and not path.is_symlink(),"Private original ADT not a regular file")
    stat=path.stat()
    fail(8<stat.st_size<=LIMIT,"Original ADT size outside allowed range")
    with path.open("rb") as stream:data=stream.read(LIMIT+1)
    fail(len(data)==stat.st_size,"Original ADT changed while being read")
    return data

def parse_all(blob:bytes):
    fail(8<len(blob)<=LIMIT,"Malformed or oversized ADT")
    items=[]
    def walk(offset:int,parent:str,depth:int)->int:
        fail(depth<=MAX_LEVELS,"ADT nesting exceeded limit")
        fail(offset+8<=len(blob),"Incomplete ADT header")
        nprops,nchildren=struct.unpack_from("<II",blob,offset)
        fail(nprops<=MAX_PROPS and nchildren<=MAX_NODES,
             "Unexpected ADT counts")
        offset+=8
        props:list[tuple[str,bytes]]=[]
        for _ in range(nprops):
            fail(offset+36<=len(blob),"Truncated ADT property header")
            raw=blob[offset:offset+32].split(b"\0",1)[0]
            fail(0<len(raw)<=32 and all(32<=b<=126 for b in raw),
                 "Non-ASCII or empty property name")
            name=raw.decode("ascii")
            n=struct.unpack_from("<I",blob,offset+32)[0]&0x7fffffff
            offset+=36
            fail(n<=len(blob)-offset,"Truncated ADT property")
            props.append((name,blob[offset:offset+n]))
            offset=(offset+n+3)&~3
        names=[v for k,v in props if k=="name"]
        fail(len(names)==1,"Ambiguous or missing ADT node name")
        raw_name=names[0].split(b"\0",1)[0]
        fail(len(raw_name)<128 and all(32<=b<=126 for b in raw_name),
             "Invalid ADT node name")
        full=parent+"/"+raw_name.decode("ascii")
        fail(len(full)<1024,"Excessive ADT node path")
        items.append((full,tuple(props)))
        fail(len(items)<=MAX_NODES,"Too many ADT nodes")
        for _ in range(nchildren):
            offset=walk(offset,full,depth+1)
        return offset
    end=walk(0,"",0)
    fail(all(x==0 for x in blob[end:]),"Nonzero trailing ADT padding")
    return items

def relevant(path:str)->bool:
    return any(path==prefix or path.startswith(prefix+"/")
               for prefix in PREFIXES) or path.endswith("/wlan")

def reg_windows(items,path):
    selected=[props for node,props in items if node==path]
    fail(len(selected)==1,"Missing or duplicated original PCIe/DART1 node")
    regs=[p for name,p in selected[0] if name=="reg"]
    fail(len(regs)==1 and len(regs[0])%16==0,
         "Unverified original Apple register layout")
    return list(struct.iter_unpack("<QQ",regs[0]))

def compare(original:bytes,live:bytes)->Check:
    a,b=parse_all(original),parse_all(live)
    fail(len(a)==len(b),"Original/live Apple ADT topology count differs")
    changed_other=0
    relevant_props=0
    for (a_path,a_props),(b_path,b_props) in zip(a,b):
        fail(a_path==b_path,"Original/live ADT path or order differs")
        if relevant(a_path):
            fail(a_props==b_props,
                 "Apple PCIe/DART1/WLAN original properties changed")
            relevant_props+=len(a_props)
        elif a_props!=b_props:
            # Count each changed property position, never print contents.
            changed_other+=sum(x!=y for x,y in zip(a_props,b_props))
            changed_other+=abs(len(a_props)-len(b_props))
    fail(relevant_props>0,"No original PCIe/DART1/WLAN properties were parsed")
    apcie="/device-tree/arm-io/apcie"
    dart1="/device-tree/arm-io/dart-apcie1"
    root=reg_windows(b,apcie)
    dma=reg_windows(b,dart1)
    for addr in (WINDOW_A,WINDOW_B):
        fail(root.count((addr,WINDOW_SIZE))==1,
             "Apple port1 window missing or duplicated")
    fail(dma==[(WINDOW_DART1,WINDOW_SIZE)],
         "Apple port1 DART1 resource different than expected")
    fail(any(node==apcie+"/pci-bridge1/wlan" for node,_ in b),
         "Original BCM4350 WLAN node missing from Apple PCIe port1")
    return Check(len(a),changed_other,relevant_props)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("original_apple_adt",type=Path)
    ap.add_argument("current_ram_linux_adt",type=Path)
    args=ap.parse_args()
    try:
        result=compare(read_private(args.original_apple_adt),
                       read_private(args.current_ram_linux_adt))
    except Exception:
        print("N71_ORIGINAL_APPLE_LIVE_PCIE_DART1_TOPOLOGY_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_ORIGINAL_APPLE_LIVE_PCIE_DART1_WLAN_SUBTREES_EXACT_PASS")
    print("ORIGINAL_APPLE_ADT_NODES",result.nodes)
    print("ORIGINAL_APPLE_PCIE_DART1_WLAN_PROPERTIES_IDENTICAL=YES")
    print("OTHER_ADT_PROPERTY_CHANGES",result.changed_non_pcie_properties)
    print("ORIGINAL_APPLE_PORT1_EXCLUSIVE_MMIO_WINDOWS=YES")
    print("ORIGINAL_APPLE_DART1_WINDOW_BOUND=YES")
    print("ORIGINAL_PCIE1_WLAN_ORIGINAL_ADT_NODE_PRESENT=YES")
    print("HARDWARE_REQUESTER_TO_SID_AND_DMA_FUNCTIONALITY_PROVEN=NO")
    print("DART1_MMIO_AND_WLAN_RADIO_ACTIONS_PERFORMED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
