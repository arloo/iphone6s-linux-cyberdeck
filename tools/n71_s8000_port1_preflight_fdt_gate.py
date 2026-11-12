#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict OFFLINE FDT verifier for a NONBOOTABLE S8000 PCIe metadata preflight.

Rejects anything but a disabled, isolated fake N71/S8000 Linux research
node with 3 fixed Apple-S8000 WLAN port1 / DART1 *descriptor-only*
physical regions, matching the privately cross-compiled Linux guard.
Does not access, map or change any hardware or emit private data.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

TOOL=Path(__file__).resolve().parent/"n71_pcie_fdt_gate.py"
SPEC=importlib.util.spec_from_file_location("n71_preflight_fdt_parser",TOOL)
assert SPEC and SPEC.loader
FDT=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=FDT
SPEC.loader.exec_module(FDT)

PREFLIGHT="/pcie-port1-preflight@602000000"
COMPAT=("apple,s8000-pcie-research-blocked",)
NAMES=("port1-reg-a","port1-reg-b","dart1-reg")
REGIONS=((0x602000000,0x4000),
         (0x602004000,0x4000),
         (0x602008000,0x4000))
REQUIRED={
    "compatible","status","research,hardware-activation-blocked",
    "research,pcie-port-index","research,dart1-mapper-index",
    "research,refclk-to-perst-delay-us","reg","reg-names"
}

class UnsafePreflight(ValueError):
    pass

def need(value,reason):
    if not value:raise UnsafePreflight(reason)

def validate_nodes(nodes):
    # The FDT may not contain *any* extra board device, root PCIe
    # host, DART controller or hidden node that might activate hardware.
    need(set(nodes)=={"/",PREFLIGHT},
         "Unexpected standalone FDT nodes")
    root=nodes["/"]
    node=nodes[PREFLIGHT]
    need(FDT.string_list(root,"compatible")==
         ("apple,n71","apple,s8000","apple,arm-platform"),
         "Not the verified N71 Samsung S8000 board")
    need(FDT.be32(root,"#address-cells")==2 and
         FDT.be32(root,"#size-cells")==2,
         "Wrong fixed S8000 64-bit descriptor cell format")
    need(set(root.props)=={
        "compatible","model","#address-cells","#size-cells"},
         "Unexpected root properties")
    need(node.name=="pcie-port1-preflight@602000000",
         "Unreviewed PCIe preflight device")
    need(set(node.props)==REQUIRED,
         "Unsafe or missing PCIe research preflight property")
    need(FDT.string_list(node,"compatible")==COMPAT,
         "Potential accidental production Apple PCIe driver bind")
    need(FDT.disabled(node),
         "Research node MUST remain disabled, not bootable")
    need(node.props["research,hardware-activation-blocked"]==b"",
         "Explicit blocked-hardware marker absent")
    need(FDT.be32(node,"research,pcie-port-index")==1,
         "Not the original WLAN PCIe port1")
    need(FDT.be32(node,"research,dart1-mapper-index")==0,
         "Unproven DART1 original mapper index")
    need(FDT.be32(node,"research,refclk-to-perst-delay-us")==100,
         "Original Apple REFCLK/PERST metadata mismatch")
    need(FDT.string_list(node,"reg-names")==NAMES,
         "Missing/unreviewed WLAN port1 and DART1 region name")
    reg=node.props["reg"]
    need(len(reg)==3*4*4,
         "Unexpected S8000 port1 only three regions required")
    decoded=[]
    for hi,lo,size_hi,size_lo in struct.iter_unpack(">4I",reg):
        need(size_hi==0,"Oversized physical region")
        decoded.append(((hi<<32)|lo,size_lo))
    need(tuple(decoded)==REGIONS,
         "S8000 port1/DART1 candidate physical windows do not match original Apple ADT")
    return {"physical_descriptors":3,"original_wlan_port":1,
            "dart1_mapper_logical":0,"status_disabled":True,
            "hardware_activation_authorized":False}

def audit_bytes(blob:bytes):
    need(40<=len(blob)<=FDT.MAX_BYTES,"Invalid standalone preflight FDT size")
    try:
        return validate_nodes(FDT.parse_fdt(blob))
    except (FDT.UnsafeTree,struct.error) as exc:
        raise UnsafePreflight("Malformed/unapproved offline FDT") from exc

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("standalone_offline_preflight_dtb",type=Path)
    args=p.parse_args()
    try:
        path=args.standalone_offline_preflight_dtb
        need(path.is_file() and not path.is_symlink(),
             "Offline FDT absent or symlink")
        s=path.stat().st_size
        need(40<=s<=FDT.MAX_BYTES,"Offline FDT size rejected")
        result=audit_bytes(path.read_bytes())
    except Exception:
        print("N71_S8000_PORT1_PREFLIGHT_OFFLINE_FAIL_CLOSED",file=sys.stderr)
        return 1
    print("N71_S8000_PORT1_PREFLIGHT_FDT_OFFLINE_PASS")
    print("ORIGINAL_APPLE_PORT1_DART1_WHITELISTED_WINDOW_COUNT",
          result["physical_descriptors"])
    print("WLAN_ORIGINAL_PORT_INDEX",result["original_wlan_port"])
    print("APPLE_DART1_LOGICAL_MAPPER_INDEX",
          result["dart1_mapper_logical"])
    print("FDT_STATUS_DISABLED=YES")
    print("SHARED_ROOT_STORAGE_BASEBAND_DMA_MAPPED=NO")
    print("LINUX_S8000_PCIE_LINK_AND_WLAN_INITIALIZED=NO")
    print("HARDWARE_PROBE_MMIO_DART_RESET_PERMITTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
