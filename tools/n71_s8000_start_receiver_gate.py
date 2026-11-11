#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71/A9 original PCIe inherited-start receiver/provisioning audit.

Strictly offline, read-only analysis of operator-supplied original
iOS 15.8.8/19H422 private ARM64 Mach-O and private N71 Apple ADT.
Static method argument flow and IOKit personality match do NOT demonstrate
a running iOS vtable or a safe Linux MMIO mapping/PCIe initialization.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent

def load_module(name:str,filename:str):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

KMAP=load_module("n71_start_kext_map","n71_kernelcache_pcie_kext_map.py")
PHY=load_module("n71_start_phy_map","n71_s8000_phy_resource_gate.py")
ADT=load_module("n71_start_adt","n71_s8000_adt_window_gate.py")

EMBEDDED="com.apple.driver.AppleEmbeddedPCIE"
SPECIAL="com.apple.driver.AppleS8000PCIe"

class ReceiverUnproven(ValueError):
    pass

def require(cond:bool,reason:str):
    if not cond:raise ReceiverUnproven(reason)

ENTRY=0x1a78
SELECTORS=(
    (0x1ed8,0xf943a108),
    (0x1f4c,0xf943ad08),
)

def word(blob:bytes,at:int)->int:
    require(0<=at<=len(blob)-4 and at%4==0,
            "Truncated ARM64 inherited-start routine")
    return struct.unpack_from("<I",blob,at)[0]

def inspect_start_argument_flow(code:bytes)->int:
    """Validate self=x0 -> x19 and provider=x1 -> x20 at routine entry.

    For both calls, x19 owns the selector vptr; returned x0 becomes
    memory-resource index x1; provider x20 owns mapping virtual call.
    """
    require(len(code)==46924,"Unrecognized original EmbeddedPCIe code")
    require(word(code,ENTRY)==0xaa0103f4,
            "Start provider is not preserved in X20")
    require(word(code,ENTRY+4)==0xaa0003f3,
            "Start self/controller is not preserved in X19")
    for at,select_slot in SELECTORS:
        expected=(
            0xf9400268,select_slot,0xaa1303e0,0xd63f0100,
            0xaa0003e1,0xf9400288,0xf941e908,0xaa1403e0,
            0x52800002,0xd63f0100,
        )
        for n,encoded in enumerate(expected):
            require(word(code,at+n*4)==encoded,
                    "Inherited-start selector/provider flow changed")
    return len(SELECTORS)

def plist_kv(d:ET.Element)->dict[str,ET.Element]:
    children=list(d)
    result={}
    for i,t in enumerate(children):
        if t.tag=="key":
            key=t.text or ""
            require(key not in result and i+1<len(children),
                    "Duplicate or truncated private personality key")
            result[key]=children[i+1]
    return result

def verify_s8000_personality(macho:bytes)->bool:
    main=KMAP.macho_segments(macho,0)
    inf=main.get("__PRELINK_INFO")
    require(inf is not None and inf["filesize"]<KMAP.MAX_PRELINK_XML,
            "Missing or oversized original Apple prelink XML")
    require(inf["offset"]+inf["filesize"]<=len(macho),
            "Prelink XML file bounds")
    xml=macho[inf["offset"]:inf["offset"]+inf["filesize"]].rstrip(b"\0")
    require(xml.startswith(b"<dict>"),"Unsupported private metadata format")
    try:
        root=ET.fromstring(b'<plist version="1.0">'+xml+b'</plist>')
    except ET.ParseError as exc:
        raise ReceiverUnproven("Malformed original Apple prelink metadata") from exc
    matches=0
    for elem in root.iter("dict"):
        data=plist_kv(elem)
        ident=data.get("CFBundleIdentifier")
        if ident is None or ident.tag!="string" or ident.text!=SPECIAL:
            continue
        matches+=1
        pers=data.get("IOKitPersonalities")
        require(pers is not None and pers.tag=="dict",
                "Original S8000 bundle lacks IOKit personalities")
        chosen=plist_kv(pers).get("AppleS8000PCIe")
        require(chosen is not None and chosen.tag=="dict",
                "Original S8000 personality name mismatch")
        match=plist_kv(chosen)
        fields={"IOClass":"AppleS8000PCIe",
                "IOProviderClass":"AppleARMIODevice",
                "IONameMatch":"apcie,s8000"}
        for key,value in fields.items():
            node=match.get(key)
            require(node is not None and node.tag=="string" and node.text==value,
                    "Original S8000 IOKit matching metadata changed")
    require(matches==1,"S8000 bundle missing or duplicated")
    return True

def audit(macho:bytes,adt:bytes)->dict:
    require(1000<len(macho)<=KMAP.MAX_MACHO,"Original image size rejected")
    # Validates private ADT without exposing device-specific values.
    msg=ADT.audit_bytes(adt)
    require("S8000_ADT_METADATA_GATE_PASS" in msg and
            "HARDWARE_BLOCKED" in msg,
            "Private N71 Apple Device Tree failed strict hardware gate")
    code,_=PHY.module_text(macho,EMBEDDED)
    n=inspect_start_argument_flow(code)
    require(verify_s8000_personality(macho),
            "No original S8000 controller binding")
    return {"self_dispatchs":n, "binding_match":True}

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_kernelcache_macho",type=Path)
    parser.add_argument("private_n71_adt",type=Path)
    a=parser.parse_args()
    try:
        require(0<a.private_kernelcache_macho.stat().st_size<=KMAP.MAX_MACHO,
                "Oversize original Apple Mach-O")
        require(0<a.private_n71_adt.stat().st_size<=ADT.ADT.MAX_FILE,
                "Oversize private N71 ADT")
        report=audit(a.private_kernelcache_macho.read_bytes(),
                     a.private_n71_adt.read_bytes())
    except (ReceiverUnproven,PHY.MappingNotVerified,
            ADT.RejectedADT,KMAP.BadKernelcache,OSError,KeyError,
            UnicodeError,struct.error) as exc:
        print("N71_PCIE_RECEIVER_GATE_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_PCIE_START_ARGUMENT_FLOW_PASS")
    print("SELECTORS_DISPATCH_TO_CONTROLLER_SELF",report["self_dispatchs"])
    print("MEMORY_MAPPINGS_DISPATCH_TO_DISTINCT_PROVIDER",report["self_dispatchs"])
    print("ORIGINAL_APPLE_S8000_CONTROLLER_PERSONALITY_MATCH=YES")
    print("S8000_RUNTIME_VTABLE_AT_CALLSITE_PROVEN=NO")
    print("MMIO_RESOURCE_NUMBERS_AND_PHYSICAL_BASES_PROVEN=NO")
    print("HARDWARE_BLOCKED: no PCIe link training, DMA, RF, NAND or MMIO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
