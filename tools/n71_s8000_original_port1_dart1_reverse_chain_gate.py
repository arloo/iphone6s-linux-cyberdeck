#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed original N71 S8000 PCIe port1→DART1 reverse verification.

Runs OFFLINE against four owner-provided LOCAL original Apple captures:
kernelcache Mach-O, Apple ADT, root IORegistry and PCIe bridge1 IORegistry.

Checks source-level vtable/resource provenance, actual original iOS PCIe
Gen1 x1 root-port link status, logical DART1 exclusive WLAN phandle and
root per-port selector source. Never reads hardware or exports private data.
No native Linux BCM4350 enumeration, requester SID or reset isolation proven.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import plistlib
import struct
import sys

HERE=Path(__file__).resolve().parent

def load(alias:str,filename:str):
    sp=importlib.util.spec_from_file_location(alias,HERE/filename)
    if not sp or not sp.loader:raise ImportError(filename)
    module=importlib.util.module_from_spec(sp)
    sys.modules[sp.name]=module
    sp.loader.exec_module(module)
    return module

REG=load("n71_final_reverse_root","n71_s8000_root_resource_gate.py")
MEM=load("n71_final_reverse_ios_mem","n71_ios_iodevicememory_order_gate.py")
ADT_GRAPH=load("n71_final_reverse_adt","n71_original_apple_adt_iommu_parent_graph_gate.py")
ROOT_CONTROL=load("n71_final_reverse_control","n71_s8000_original_port1_root_bit_control_chain_gate.py")

class UnprovenHardware(ValueError):pass

def need(ok,reason):
    if not ok:raise UnprovenHardware(reason)

def source_provider_chain(original:bytes)->bool:
    main,mods=REG.auditable_root_code(original)
    REG.verify_root_inheritance(original,main,mods)
    REG.verify_index_methods(original,main,mods)
    a9=mods["a9"]
    p968=REG.G.read_data_pointer(original,main,a9["vptr"]+968)
    p976=REG.G.read_data_pointer(original,main,a9["vptr"]+976)
    need(p976==p968+0x7c,"Unrecognized original IOMemoryDescriptor provider method")
    segment=main["__TEXT_EXEC"]
    def read_original(vaddr:int,length:int)->bytes:
        need(segment["vm"]<=vaddr and
             vaddr+length<=segment["vm"]+segment["filesize"],
             "Original provider outside signed Apple source segment")
        offset=segment["offset"]+vaddr-segment["vm"]
        return original[offset:offset+length]
    a=read_original(p968,0x7c)
    b=read_original(p976,0x44)
    get_word=lambda block,off:struct.unpack_from("<I",block,off)[0]
    # IOPCIDevice getMemoryDescriptor: preserve x1 (requested resource
    # index) across the indexed lookup, with x0 becoming an array.
    slot968={0x00:0xa9be4ff4,0x0c:0xaa0103f3,0x1c:0xf9408508,
             0x20:0xd63f0100,0x60:0xf9400288,0x64:0xf9408d02,
             0x68:0xaa1403e0,0x6c:0xaa1303e1,0x78:0xd61f0040}
    # Map method: call slot968 with original requested index x1,
    # preserve mapping options x2, then call returned descriptor method.
    slot976={0x00:0xa9be4ff4,0x0c:0xaa0203f3,0x14:0xf941e508,
             0x18:0xd63f0100,0x24:0xf9407502,0x28:0xaa1303e1,
             0x34:0xd61f0040}
    for offset,opcode in slot968.items():
        need(get_word(a,offset)==opcode,"Original indexed resource lookup changed")
    for offset,opcode in slot976.items():
        need(get_word(b,offset)==opcode,"Original provider mapping call changed")
    return True

def verify_dart1_exclusive(nodes:dict)->bool:
    need(ADT_GRAPH.verify_apple_logical_iommu_graph(nodes),
         "Original N71 logical PCIe/DART graph failed")
    mapper=nodes[ADT_GRAPH.MAPPER1]["AAPL,phandle"]
    need(type(mapper) is bytes and len(mapper)==4,
         "Bad DART1 mapper handle")
    incoming=[]
    for path,properties in nodes.items():
        parents=properties.get("iommu-parent",b"")
        need(type(parents) is bytes and len(parents)%4==0,
             "Invalid or incomplete Apple IOMMU parent list")
        for offset in range(0,len(parents),4):
            if parents[offset:offset+4]==mapper:
                incoming.append((path,offset//4))
    need(incoming==[(ADT_GRAPH.PORT1,0)],
         "DART1 has an unverified extra IOMMU parent, or no WLAN reference")
    storage=nodes[ADT_GRAPH.PORT0]["iommu-parent"]
    need(len(storage)==12,"Storage must have three original IOMMU parents")
    handles={}
    for path,properties in nodes.items():
        handle=properties.get("AAPL,phandle")
        if handle is None:continue
        need(type(handle) is bytes and len(handle)==4 and handle not in handles,
             "Duplicate or malformed Apple ADT phandle")
        handles[handle]=path
    need(handles.get(storage[8:12])=="/device-tree/arm-io/nvme-mmu0",
         "Storage third IOMMU is not original nvme-mmu0")
    return True

def verify_ios_link(bridge:dict)->bool:
    need(bridge.get("IOPCIConfigured") is True and
         bridge.get("IOPCIResourced") is True,
         "Original Apple PCIe bridge was not configured")
    need(bridge.get("apcie-port")==struct.pack("<I",1),
         "Original Apple PCIe link not on WLAN port1")
    need(bridge.get("vendor-id")==struct.pack("<I",0x106b) and
         bridge.get("device-id")==struct.pack("<I",0x1004),
         "Original Apple root-port bridge identity mismatch")
    status=bridge.get("IOPCIExpressLinkStatus")
    need(type(status) is int and 0<=status<=0xffff,
         "Invalid original link-status register metadata")
    need(status==0x1011 and (status&0xf)==1 and
         (status>>4)&0x3f==1 and not(status&(1<<11)),
         "Original Apple port1 link not verified as stable Gen1 x1")
    return True

def audit(original:bytes,adt:bytes,root_plist:bytes,port_plist:bytes)->bool:
    source_provider_chain(original)
    nodes=ADT_GRAPH.parse_adt(adt)
    verify_dart1_exclusive(nodes)
    resources=MEM.compare_private_inputs(root_plist,adt)
    need(len(resources)==11 and
         resources[0]==(0x610000000,0x1000000) and
         resources[3]==(0x602000000,0x4000) and
         resources[4]==(0x602004000,0x4000),
         "Root config index0 and WLAN port1 resources mismatch")
    bridge=plistlib.loads(port_plist).get("IORegistry")
    need(type(bridge) is dict and verify_ios_link(bridge),
         "Original iOS root port1 link verification failed")
    ROOT_CONTROL.inspect(original,adt,root_plist,port_plist)
    need(ROOT_CONTROL.offsets(1)=={2:0x180,3:0x194,4:0x1a4,5:0x1ac},
         "Original WLAN port1 root selector changed")
    return True

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("original_private_n71_macho","original_private_n71_adt",
                "original_private_ios_root_plist",
                "original_private_ios_port1_plist"):
        parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    limits=(150_000_000,200_000,2_000_000,2_000_000)
    try:
        blobs=[]
        for item,limit in zip(vars(args).values(),limits):
            need(item.is_file() and not item.is_symlink() and
                 8<item.stat().st_size<limit,
                 "Unrecognized owner-private original source file")
            blobs.append(item.read_bytes())
        need(audit(*blobs),"Incomplete Apple original source chain")
    except (OSError,ValueError,KeyError,IndexError,TypeError,RecursionError):
        print("N71_S8000_PORT1_ORIGINAL_REVERSE_EVIDENCE_NOT_PROVEN",file=sys.stderr)
        return 2
    print("N71_S8000_ORIGINAL_PORT1_DART1_REVERSE_CHAIN_PASS")
    print("N71_ORIGINAL_ROOT_PROVIDER_INDEX_UNCHANGED_AND_MAPPED_PASS")
    print("N71_WLAN_DART1_EXCLUSIVE_LOGICAL_PHANDLE_GRAPH_PASS")
    print("N71_STORAGE_THIRD_IOMMU_IS_NVME_MMU0_PASS")
    print("N71_ORIGINAL_IOS_PCIE_PORT1_LINK_GEN1_X1_PASS")
    print("N71_PORT1_ROOT_PORT_SELECTOR_OFFSETS_SOURCE_PASS")
    print("N71_GLOBAL_CONFIG_INDEX0_IS_NOT_PORT1_LOCAL=YES")
    print("N71_DART1_PHYSICAL_REQUESTER_SID_OR_CLOCK_RESET_ISOLATION_PROVEN=NO")
    print("N71_LINUX_NATIVE_BCM4350_PCIE_WIFI_PROVEN=NO")
    print("N71_NO_PHONE_MMIO_DMA_REBOOT_OR_NAND=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
