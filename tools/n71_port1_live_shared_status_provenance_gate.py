#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Combine ORIGINAL Apple PCIe control-flow proof with real iOS resource order.

Read-only analysis of three PRIVATE local files: original N71/S8000 kernelcache
Mach-O (original iOS 15.8.8), original N71 Apple ADT, and captured iOS 15.7.9
'apcie' IORegistry entry. No device access, writes or original payload export.
Produces only fixed S8000 public hardware-address metadata.

This proves the physical resource/window and original code's bit predicate,
NOT the electrical semantics of that bit or any safe hardware initialization.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
MODEL=(HERE.parent/"examples/n71-pcie-port1"
       /"port1_shared_status_snapshot_model.c")

def load(alias:str,name:str):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

RMW=load("n71_live_rmw","n71_s8000_port1_rmw_provenance_gate.py")
IOS=load("n71_live_reg","n71_ios_iodevicememory_order_gate.py")

EXPECTED_INDEX=9
EXPECTED_BASE=0x600000000
EXPECTED_LENGTH=0x8000
EXPECTED_OFFSET=0x2c
EXPECTED_BIT=4
MAX_MACHO=128*1024*1024
MAX_ADT=16*1024*1024
MAX_PLIST=2*1024*1024

class InvalidProvenance(ValueError):
    pass

def require(ok:bool,why:str)->None:
    if not ok:raise InvalidProvenance(why)

def verify_source_model(source:str)->None:
    allowed={
      "N71_COMMON_RESOURCE_INDEX": "9U",
      "N71_SHARED_BASE": "UINT64_C(0x600000000)",
      "N71_SHARED_LENGTH": "UINT64_C(0x8000)",
      "N71_SHARED_ID1_OFFSET": "0x2cU",
      "N71_SHARED_ID1_BIT": "4U",
      "N71_MAX_SYNTHETIC_SNAPSHOTS": "4096U",
    }
    defs={}
    for name,val in re.findall(
        r"(?m)^#define\s+(N71_[A-Z0-9_]+)\s+([^\r\n/]+?)\s*$",
        source):
        if name in defs:
            raise InvalidProvenance("Repeated model controller constant")
        defs[name]=val.strip()
    for key,val in allowed.items():
        require(defs.get(key)==val, "C model diverged from original controller proof")
    for unsafe in ("ioremap(", "readl(", "writel(", "/dev/mem",
                   "mmap(", "ioctl(", "socket(", "popen("):
        require(unsafe not in source.lower(),
                "No hardware I/O or network calls permitted in model")
    require(re.search(
        r"int\s+n71_port1_shared_snapshot_authorizes_hardware\s*\(void\)"
        r"\s*\{\s*return\s+0\s*;\s*\}",source) is not None,
        "Mandatory model hardware-denial function absent or modified")

def verify_original_sources(original_kernel:bytes,
                            private_adt:bytes,
                            live_registry:bytes,
                            source_model:str)->dict[str,int]:
    # Original disassembly provenance independently checks actual AArch64
    # vtable methods, register selector and ID1 bit4 polling instructions.
    original=RMW.audit(original_kernel,private_adt)
    require(original["shared_status_register_id"]==1 and
            original["shared_status_relative_offset"]==EXPECTED_OFFSET and
            original["shared_status_bit"]==EXPECTED_BIT and
            original["shared_status_retry_backedge"] is True and
            original["caller_level_timeout_implemented_in_original"] is False,
            "Unexpected original shared-status polling code")
    # Independently captured iOS runtime IODeviceMemory ordering is compared
    # to original ADT, not fabricated from a copied ADT reg array.
    mem=IOS.compare_private_inputs(live_registry,private_adt)
    require(isinstance(mem,tuple) and len(mem)==11,
            "Unqualified real iOS PCIe resource count")
    base,size=mem[EXPECTED_INDEX]
    require(type(base) is int and type(size) is int and
            base==EXPECTED_BASE and size==EXPECTED_LENGTH and
            0<=EXPECTED_OFFSET<=size-4,
            "Original S8000 COMMON resource or offset changed")
    verify_source_model(source_model)
    return {
       "provider_index":EXPECTED_INDEX,
       "base":base,
       "size":size,
       "offset":EXPECTED_OFFSET,
       "bit":EXPECTED_BIT,
       "address":base+EXPECTED_OFFSET,
       "resource_count":len(mem)
    }

def private_file(path:Path,limit:int)->bytes:
    require(path.is_file() and not path.is_symlink(),
            "Required private original input unavailable")
    size=path.stat().st_size
    require(0<size<=limit,"Original input size outside bounded limit")
    return path.read_bytes()

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_original_n71_kernelcache_macho",type=Path)
    parser.add_argument("private_original_n71_adt",type=Path)
    parser.add_argument("private_ios15_live_ioregentry_apcie",type=Path)
    x=parser.parse_args()
    try:
        data=verify_original_sources(
          private_file(x.private_original_n71_kernelcache_macho,MAX_MACHO),
          private_file(x.private_original_n71_adt,MAX_ADT),
          private_file(x.private_ios15_live_ioregentry_apcie,MAX_PLIST),
          MODEL.read_text(encoding="utf-8"))
    except Exception:
        # Never leak input content, file paths, keys, unique IDs or traceback
        # when users give malformed private originals.
        print("N71_PORT1_ORIGINAL_LIVE_PROVENANCE_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_PORT1_ORIGINAL_CODE_AND_LIVE_IOS_PROVIDER_PASS")
    print("ALL_ORIGINAL_PROVIDER_RESOURCES_ORDER_CONFIRMED=YES")
    print("ROOT_COMMON_PROVIDER_INDEX",data["provider_index"])
    print("ORIGINAL_CODE_SHARED_ID1_OFFSET",hex(data["offset"]))
    print("ORIGINAL_CODE_SHARED_STATUS_BIT",data["bit"])
    print("ORIGINAL_CODE_POLLS_BIT_WITHOUT_FINITE_LIMIT=YES")
    print("DERIVED_PHYSICAL_SHARED_STATUS_REGISTER",hex(data["address"]))
    print("AARCH64_OFFLINE_SNAPSHOT_MODEL_MATCH=YES")
    print("RAW_PRIVATE_ORIGINAL_DATA_EXPORTED=NO")
    print("HARDWARE_INIT_AND_PCIE_LINK_PROVEN=NO")
    print("LINUX_ONBOARD_BCM4350_WIFI_WORKING=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
