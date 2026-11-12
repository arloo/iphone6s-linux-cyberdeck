#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed N71/S8000 PCIe port1 tunables provenance and private staging.

Checks FOUR original Apple ADT tunable OSData blobs against independently
captured iOS15.7.9 IORegistry for the real N71/S8000. Uses only original
owner-held local inputs and prints count/quality metadata, never raw
per-device PHY/calibration values, Wi-Fi IDs, source paths, or credentials.

Optionally stages an explicitly disabled data-only private manifest under a
private marked directory. No MMIO, GPIO, reset, storage, phone, network or
Linux driver access; the manifest is NOT a ready-to-apply register sequence.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import sys

HERE=Path(__file__).resolve().parent
PUBLIC_REPO=HERE.parent
SPEC=importlib.util.spec_from_file_location(
    "n71_tunables_adt", HERE/"n71_s8000_adt_window_gate.py")
assert SPEC and SPEC.loader
ADT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADT)

PROPS={
    "apcie-common-tunables":(ADT.HOST,34,0x8000),
    "apcie-phy-tunables":(ADT.HOST,41,0x4000),
    "apcie-config-tunables":(ADT.HOST+"/pci-bridge1",6,0x4000),
    "pcie-rc-tunables":(ADT.HOST+"/pci-bridge1",2,0x4000),
}
REAL_TOTAL=sum(t[1] for t in PROPS.values())
RECORD=struct.Struct("<IIQQ")  # structural 24-byte candidate
MAX_PLIST_SIZE=2*1024*1024
STAGE_MARKER=".n71-private-tunables-output-root"

# Original iOS15.8.8 AppleEmbeddedPCIE native ARM64 instruction signatures.
# The original core and per-port tunable routines consume a 24-byte tuple
# (u32 offset,u32 width,u64 mask,u64 value) and implement a 32-bit
# masked update. Hardware side effects and ordering remain unqualified.
ORIGINAL_EMBEDDED_LENGTH=46924
ORIGINAL_TUNABLE_INSTRUCTIONS={
    0x9180:0x7100635f,  # reject OSData shorter than 24 bytes
    0x91b0:0xa940cf35,  # load two u64 mask/value fields from +8
    0x91b4:0xb9400728,  # width from +4
    0x91b8:0x7100111f,  # width==4
    0x9218:0xb9400321,  # hardware-relative offset from +0
    0x9224:0x0a150009,  # old & mask
    0x9228:0x0a150268,  # new_value & mask
    0x9234:0x0a350009,  # old & ~mask
    0x9238:0x2a08013c,  # join masked value and preserved bits
    0x92a4:0x91006339,  # advance by exactly 24 bytes
    0x3404:0xb9400321,  # second independent per-port apply routine
    0x3410:0x0a140009,
    0x3414:0x0a140268,
    0x3420:0x0a340009,
    0x3424:0x2a08013c,
    0x3480:0x91006339,  # second 24-byte stride
}

class RejectedTunables(ValueError):
    pass

def must(ok:bool,reason:str)->None:
    if not ok:raise RejectedTunables(reason)

def read_private(path:Path,max_bytes:int)->bytes:
    must(path.is_file() and not path.is_symlink(),
         "Original private input missing or symlink")
    size=path.stat().st_size
    must(8<size<=max_bytes,"Original private input size not accepted")
    return path.read_bytes()

def verify_original_apple_tunable_code(private_kernel_macho:bytes)->None:
    spec=importlib.util.spec_from_file_location(
        "n71_orig_pcie_tunable_source",
        HERE/"n71_s8000_root_resource_gate.py")
    assert spec and spec.loader
    root=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root)
    _,mods=root.auditable_root_code(private_kernel_macho)
    verify_original_tunable_instruction_words(mods["embedded"]["code"])


def verify_original_tunable_instruction_words(code:bytes)->None:
    must(len(code)==ORIGINAL_EMBEDDED_LENGTH,
         "Original Apple PCIe controller executable size changed")
    for offset,expected in ORIGINAL_TUNABLE_INSTRUCTIONS.items():
        must(struct.unpack_from("<I",code,offset)[0]==expected,
             "Original Apple masked tunable field/stride semantics changed")


def decode_record_block(raw:bytes,expected_count:int,
                        region_size:int)->list[dict[str,int]]:
    must(type(raw) is bytes and len(raw)==expected_count*RECORD.size,
         "S8000 Apple tunable length or record count mismatch")
    output=[]
    for offset,width,mask,value in RECORD.iter_unpack(raw):
        must(width==4 and offset%4==0 and
             offset+width<=region_size,
             "Unrecognized original S8000 tunable width/range")
        must(mask<=0xffffffff and value<=0xffffffff and
             not(value & ~mask),
             "Unknown S8000 tunable 32-bit mask/value relation")
        output.append({"offset":offset,"width":width,
                       "candidate_mask":mask,"candidate_value":value})
    return output

def adt_tunable_blobs(original_adt:bytes)->dict[str,bytes]:
    must(8<len(original_adt)<=ADT.ADT.MAX_FILE,
         "Unsupported original N71 ADT size")
    strict=ADT.audit_bytes(original_adt)
    must("S8000_ADT_METADATA_GATE_PASS" in strict and
         "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in strict,
         "Original N71/S8000 hardware identity not proven")
    found:dict[str,dict[str,bytes]]={}
    paths={path for path,_,_ in PROPS.values()}
    def visitor(path:str,props:dict[str,bytes])->None:
        if path in paths:
            must(path not in found,
                 "Original Apple ADT target path duplicated")
            found[path]={key:props[key] for key in PROPS if key in props}
    try:
        ADT.ADT.parse_node(original_adt,0,"",visitor=visitor,
                           visit_all=True,extra_props=frozenset(PROPS))
    except (ADT.ADT.InvalidADT,struct.error) as exc:
        raise RejectedTunables("Original Apple ADT tunable scan failed") from exc
    must(set(found)==paths,
         "Original Apple ADT S8000 PCIe root/port1 not found")
    blobs={}
    for key,(path,_,_) in PROPS.items():
        must(key in found[path],"Original PCIe tunable missing")
        blobs[key]=found[path][key]
    return blobs

def captured_ios_tunable_blobs(root_plist:bytes,
                               port1_plist:bytes)->dict[str,bytes]:
    try:
        root=plistlib.loads(root_plist)["IORegistry"]
        port=plistlib.loads(port1_plist)["IORegistry"]
    except (ValueError,KeyError,TypeError,plistlib.InvalidFileException) as exc:
        raise RejectedTunables("Original iOS IORegistry input invalid") from exc
    must(type(root) is dict and type(port) is dict,
         "Original iOS IORegistry root/port1 types invalid")
    must(root.get("IOPCIConfigured") is True and
         port.get("IOPCIConfigured") is True and
         port.get("IOPCIResourced") is True,
         "Original iOS PCIe devices not configured/resourced")
    result={}
    for key,(path,_,_) in PROPS.items():
        entry=root if path==ADT.HOST else port
        value=entry.get(key)
        must(type(value) is bytes,
             "Original iOS runtime tunable data unavailable")
        result[key]=value
    return result

def corroborate(original_adt:bytes,root_plist:bytes,
                port1_plist:bytes)->dict[str,list[dict[str,int]]]:
    originals=adt_tunable_blobs(original_adt)
    runtime=captured_ios_tunable_blobs(root_plist,port1_plist)
    results={}
    for key,(_,count,region_size) in PROPS.items():
        must(originals[key]==runtime[key],
             "Original Apple ADT and real iOS tunables differ")
        results[key]=decode_record_block(originals[key],count,region_size)
    must(sum(len(v) for v in results.values())==REAL_TOTAL,
         "Original total N71 S8000 record count changed")
    # Original root shared status bit4 is at COMMON offset 0x2C.
    # This proves only NO *DIRECT* array write to offset 0x2C:
    # adjacent writes/side effects are NOT cleared for Linux.
    must(not any(r["offset"]==0x2c
                 for r in results["apcie-common-tunables"]),
         "Common PCIe array unexpectedly directly touches status offset 0x2C")
    return results

def private_stage(target:Path,
                  records:dict[str,list[dict[str,int]]])->None:
    # Only an explicitly marked private research folder outside our repo.
    must(target.is_absolute() and target.suffix==".json",
         "Private stage requires absolute .json path")
    must(not target.is_symlink() and not target.exists(),
         "Never overwrite or follow a private staging file")
    parent=target.parent.resolve(strict=True)
    must(not parent.is_relative_to(PUBLIC_REPO.resolve()),
         "Refusing to place confidential calibration inside public Git")
    must((parent/STAGE_MARKER).is_file() and
         not (parent/STAGE_MARKER).is_symlink(),
         "Private destination directory is not marked")
    must(stat.S_IMODE(parent.stat().st_mode)&0o077==0,
         "Private destination directory permissions too permissive")
    payload={
        "board":"N71 S8000 (Samsung A9), onboard BCM4350 PCIe port1",
        "source_proof":"original Apple ADT = original iOS15.7.9 IORegistry bytewise",
        "original_record_layout":"verified <u32 offset,u32 width,u64 mask,u64 value>",
        "original_software_masked_rmw_statically_verified":True,
        "original_masked_formula":"(old & ~mask) | (new_value & mask)",
        "actual_register_semantics_verified":False,
        "calibrated_records_owner_private":True,
        "enable_register_writes":False,
        "enable_dart1_dma":False,
        "enable_pcie_port1_link":False,
        "cross_port_effects_qualified":False,
        "disposition":"SOURCE DATA ONLY, DO NOT BOOT OR APPLY",
        "groups":records,
    }
    raw=(json.dumps(payload,sort_keys=True,indent=2)+"\n").encode("utf-8")
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(target,flags,0o600)
    try:
        with os.fdopen(fd,"wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise

def main()->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("original_n71_apple_adt",type=Path)
    a.add_argument("original_ios_apcie_plist",type=Path)
    a.add_argument("original_ios_pci_bridge1_plist",type=Path)
    a.add_argument("--original-kernelcache",type=Path,required=True,
                   help="Private original N71/S8000 ARM64 Mach-O (format evidence)")
    a.add_argument("--stage-private",type=Path)
    args=a.parse_args()
    try:
        verify_original_apple_tunable_code(
            read_private(args.original_kernelcache,150_000_000))
        records=corroborate(
            read_private(args.original_n71_apple_adt,ADT.ADT.MAX_FILE),
            read_private(args.original_ios_apcie_plist,MAX_PLIST_SIZE),
            read_private(args.original_ios_pci_bridge1_plist,MAX_PLIST_SIZE))
        if args.stage_private is not None:
            private_stage(args.stage_private,records)
    except Exception:
        # Never disclose raw original values, input paths or unique hardware.
        print("N71_PCIE_TUNABLES_ORIGINAL_LIVE_FAIL_CLOSED",file=sys.stderr)
        return 1
    print("N71_PCIE_S8000_ORIGINAL_ADT_LIVE_IOS_TUNABLES_PASS")
    for key,(_,count,_) in PROPS.items():
        print("MATCHED_TUNABLE_BLOCK",key,"RECORDS",count)
    print("TOTAL_MATCHED_24_BYTE_TUNABLES",REAL_TOTAL)
    print("ORIGINAL_APPLE_PCIE_MASKED_RMW_AND_24_BYTE_STRIDE_STATIC_PASS")
    print("ALL_TUNABLES_32_BIT_ALIGNED_AND_BOUNDED=YES")
    print("DIRECT_ORIGINAL_COMMON_ARRAY_WRITE_TO_STATUS_0X2C=NO")
    print("PRIVATE_DATA_ONLY_MANIFEST_CREATED",
          "YES" if args.stage_private is not None else "NO")
    print("TUNABLE_ACTUAL_HARDWARE_SEMANTICS_PROVEN=NO")
    print("PCIE_AND_DART_HARDWARE_INITIALIZATION_ALLOWED=NO")
    print("PER_DEVICE_CALIBRATION_VALUES_EXPORTED_PUBLICLY=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
