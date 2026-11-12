#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify N71/S8000 iOS IODeviceMemory order against private Apple ADT.

OFFLINE read-only checker. Inputs are privately acquired iOS IORegistry entry
and Apple ADT. Neither input nor unknown properties are printed, serialized,
uploaded, or written. Passing validates an OS-exposed resource ordering,
NOT safe MMIO access, DMA, PCIe link initialization or WLAN association.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import plistlib
import struct
import sys

GATE_PATH=Path(__file__).resolve().with_name("n71_s8000_adt_window_gate.py")
spec=importlib.util.spec_from_file_location("n71_live_adt",GATE_PATH)
assert spec and spec.loader
ADT_GATE=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ADT_GATE)

MAX_REGISTRY_BYTES=2_000_000
LIVE_APCIE_KEY="IORegistry"
HOST_LAYOUT=ADT_GATE.HOST_LAYOUT
MATCHED_INDEXES=(0,9,10)
MAX_PHYSICAL=1<<48

class RegistryNotVerified(ValueError):
    pass

def require(ok:bool,reason:str)->None:
    if not ok:
        raise RegistryNotVerified(reason)

def validate_live_registry(data:bytes)->tuple[tuple[int,int],...]:
    require(0<len(data)<=MAX_REGISTRY_BYTES,"IORegistry input size rejected")
    try:
        doc=plistlib.loads(data)
    except Exception as exc:
        # Parse errors must not embed private XML or plist content.
        raise RegistryNotVerified("Malformed private IORegistry plist") from exc
    require(isinstance(doc,dict) and set(doc)=={LIVE_APCIE_KEY},
            "Expected only IORegistry root")
    root=doc[LIVE_APCIE_KEY]
    require(isinstance(root,dict),"Missing IORegistry entry")
    require(root.get("IOPCIConfigured") is True,
            "Live PCIe host not marked configured")
    compatible=root.get("compatible")
    require(compatible==b"apcie,s8000\0",
            "Live device is not the pinned Samsung A9 PCIe host")
    ports=root.get("#ports")
    require(isinstance(ports,bytes) and ports==struct.pack("<I",4),
            "Live PCIe root is not verified four-port N71 hardware")
    raw=root.get("reg")
    require(isinstance(raw,bytes) and len(raw)==11*16,
            "Live original Apple reg tuple bytes missing")
    reg=tuple(struct.iter_unpack("<QQ",raw))
    require(reg==HOST_LAYOUT,"Live reg tuples mismatch verified N71 ADT")
    resources=root.get("IODeviceMemory")
    require(isinstance(resources,list) and len(resources)==11,
            "Actual device-memory provider must expose eleven ranges")
    mem=[]
    for index,wrapped in enumerate(resources):
        require(isinstance(wrapped,list) and len(wrapped)==1,
                "Unexpected live IODeviceMemory element container")
        entry=wrapped[0]
        require(isinstance(entry,dict) and set(entry)=={"address","length"},
                "Unexpected live IODeviceMemory address/length structure")
        address,length=entry["address"],entry["length"]
        require(type(address) is int and type(length) is int,
                "Memory range is not an integer tuple")
        require(0<length<=0x10000000 and address>0 and
                address+length<=MAX_PHYSICAL and
                address%4096==0 and length%4096==0,
                "Live memory range invalid or overflowing")
        require((address,length)==HOST_LAYOUT[index],
                "Actual IODeviceMemory order differs from ADT reg order")
        mem.append((address,length))
    # This proves exact index-order equality, not merely set equality.
    ADT_GATE.disjoint([(f"range{i}",a,n)
                       for i,(a,n) in enumerate(mem)])
    return tuple(mem)

def compare_private_inputs(registry:bytes,adt:bytes)->tuple[tuple[int,int],...]:
    try:
        result=ADT_GATE.audit_bytes(adt)
    except ADT_GATE.RejectedADT as exc:
        raise RegistryNotVerified("Original N71 private ADT rejected") from exc
    require("S8000_ADT_METADATA_GATE_PASS" in result and
            "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in result,
            "Private ADT independent hardware checks did not pass")
    return validate_live_registry(registry)

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_ios_ioregentry_apcie",type=Path)
    p.add_argument("private_n71_adt",type=Path)
    a=p.parse_args()
    try:
        require(0<a.private_ios_ioregentry_apcie.stat().st_size<=MAX_REGISTRY_BYTES,
                "Invalid iOS registry file size")
        require(0<a.private_n71_adt.stat().st_size<=ADT_GATE.ADT.MAX_FILE,
                "Invalid private ADT file size")
        result=compare_private_inputs(
            a.private_ios_ioregentry_apcie.read_bytes(),
            a.private_n71_adt.read_bytes())
    except (OSError,RegistryNotVerified,struct.error,ADT_GATE.RejectedADT):
        # Do not echo private file paths, plist fields or raw parser errors.
        print("N71_IOS_IODEVICEMEMORY_ORDER_FAIL_CLOSED: private input rejected",
              file=sys.stderr)
        return 1
    print("N71_IOS_IODEVICEMEMORY_ORDER_MATCH_PASS")
    print("ALL_11_PROVIDER_RESOURCES_MATCH_PRIVATE_ADT_IN_ORDER=YES")
    for label,index in zip(("CONFIG","COMMON","ADDITIONAL"),MATCHED_INDEXES):
        base,length=result[index]
        print("PROVIDER_INDEX",index,"ROLE",label,
              "PHYSICAL_BASE",hex(base),"BYTES",hex(length))
    print("IOS_IOREGISTRY_RAW_VALUES_EXPORTED=NO")
    print("HARDWARE_BLOCKED: register bit semantics, port1 reset/clocks, "
          "DART1 SID/IOVA/DMA isolation and native Wi-Fi")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
