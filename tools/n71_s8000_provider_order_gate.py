#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed A9/N71 AppleARMIODevice IODeviceMemory-order verifier.

Offline-only. Without an independently captured ORIGINAL iOS registry
snapshot, this tool explicitly refuses to claim ADT reg tuple ordering.
It never connects to hardware, maps registers, or writes a file. No Apple
firmware, raw IOKit registry, private ADT or per-device data is published.

The accepted JSON is a *sanitized* snapshot of only the eleven ordered
IODeviceMemory address/length pairs of the AppleARMIODevice /arm-io/apcie
provider in original iOS (not a copy of ADT reg[]). Claims of provenance
are supplied by the operator and are NOT independently authenticated
by this tool.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "n71_original_adt_provider_order",
    ROOT / "n71_s8000_adt_window_gate.py")
assert spec and spec.loader
ADT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ADT)

MAX_JSON_BYTES = 16384
EXPECTED_SCHEMA = "n71-s8000-ios-provider-ordered-memory-v1"
EXPECTED_CLASS = "AppleARMIODevice"
EXPECTED_COMPAT = "apcie,s8000"
ENTRY_FIELDS = frozenset(("address", "length"))
SNAPSHOT_FIELDS = frozenset(
    ("schema", "source", "provider_class", "compatible",
     "node_path", "IODeviceMemory"))
SOURCE = "operator-captured-original-ios-ioreg"
NODE_PATH = "/arm-io/apcie"

class UnverifiedResourceOrder(ValueError):
    """Deliberate rejection of untrusted or incompatible resource data."""

def need(ok:bool,reason:str)->None:
    if not ok:
        raise UnverifiedResourceOrder(reason)

def no_duplicate_keys(pairs:list[tuple[str,object]])->dict:
    result={}
    for key,value in pairs:
        need(key not in result,"Duplicate JSON keys rejected")
        result[key]=value
    return result

def parse_address(value:object)->int:
    # Only canonical unsigned 64-bit '0x...' strings, not floats,
    # booleans, signed ints or arbitrary Python converted values.
    need(isinstance(value,str) and
         re.fullmatch(r"0x(?:0|[1-9a-f][0-9a-f]{0,15})",value) is not None,
         "Unrecognized numeric address/length encoding")
    result=int(value,16)
    need(0<=result<(1<<64),"Physical value exceeds u64")
    return result

def inspect_snapshot(snapshot:object,expected:list[tuple[int,int]])->dict:
    need(type(snapshot) is dict and set(snapshot)==SNAPSHOT_FIELDS,
         "Sanitized original iOS registry schema is incomplete or has extra fields")
    for key,wanted in (
        ("schema",EXPECTED_SCHEMA),("source",SOURCE),
        ("provider_class",EXPECTED_CLASS),("compatible",EXPECTED_COMPAT),
        ("node_path",NODE_PATH)):
        need(snapshot.get(key)==wanted,
             "Original iOS S8000 provider identity not established")
    rows=snapshot["IODeviceMemory"]
    need(type(rows) is list and len(rows)==11 and len(expected)==11,
         "Expected exactly eleven original N71 provider mappings")
    got=[]
    for row in rows:
        need(type(row) is dict and set(row)==ENTRY_FIELDS,
             "Unexpected private IOKit data or missing address/length")
        addr,length=parse_address(row["address"]),parse_address(row["length"])
        need(addr%4096==0 and length>0 and length%4096==0 and
             length<=0x10000000 and addr+length < (1<<64),
             "Malformed or overflowed provider IODeviceMemory range")
        got.append((addr,length))
    ADT.disjoint([(str(i),addr,length) for i,(addr,length) in enumerate(got)])
    # Fail closed for any swap, addition, subtraction or removed range.
    need(got==expected,"PROVIDER_MEMORY_ORDER_MISMATCH_ADT: do not map MMIO")
    return {
        "range_count":len(got),
        "matches":True,
        "indices":(0,9,10),
        "capture_provenance_independently_verified":False,
    }

def verified_adt(blob:bytes)->list[tuple[int,int]]:
    msg=ADT.audit_bytes(blob)
    need("S8000_ADT_METADATA_GATE_PASS" in msg and
         "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in msg,
         "Private original A9 ADT hardware gate not passed")
    # Use a validated fixed layout; the gate above has already
    # checked all 11 host ranges in the actual private ADT.
    return list(ADT.HOST_LAYOUT)

def parse_snapshot(payload:bytes)->dict:
    need(0<len(payload)<=MAX_JSON_BYTES,
         "Private sanitized JSON exceeds the strict file size limit")
    try:
        txt=payload.decode("utf-8",errors="strict")
        result=json.loads(txt,object_pairs_hook=no_duplicate_keys,
                          parse_constant=lambda x:need(False,"JSON nonfinite invalid"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise UnverifiedResourceOrder("Invalid original registry JSON") from exc
    need(type(result) is dict,"Sanitized runtime snapshot must be object")
    return result

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_n71_adt",type=Path)
    p.add_argument("--ios-provider-snapshot",type=Path,default=None)
    args=p.parse_args()
    try:
        need(0<args.private_n71_adt.stat().st_size<=ADT.ADT.MAX_FILE,
             "Original private N71 ADT size rejected")
        expected=verified_adt(args.private_n71_adt.read_bytes())
        if args.ios_provider_snapshot is None:
            print("N71_S8000_PROVIDER_ADT_ONLY_PASS")
            print("EXPECTED_HOST_RANGES",len(expected))
            print("ROOT_SELECTOR_INDICES_CONFIG_COMMON_PHY=0,9,10")
            print("PROVIDER_IODEVICE_MEMORY_ORDER_PROVEN=NO")
            print("RUNTIME_IOS_PROVIDER_CAPTURE_MISSING=YES")
            print("HARDWARE_BLOCKED: no MMIO mapping, DMA, clocks or WLAN")
            return 0
        need(0<args.ios_provider_snapshot.stat().st_size<=MAX_JSON_BYTES,
             "Private iOS provider snapshot rejected by size")
        snap=parse_snapshot(args.ios_provider_snapshot.read_bytes())
        outcome=inspect_snapshot(snap,expected)
    except (UnverifiedResourceOrder,ADT.RejectedADT, OSError,
            KeyError, TypeError, ValueError) as exc:
        print("N71_S8000_PROVIDER_MEMORY_ORDER_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_S8000_PROVIDER_IODEVICE_MEMORY_ARRAY_MATCHES_ADT_PASS")
    print("MATCHED_HOST_RANGES",outcome["range_count"])
    print("RESOURCE_INDICES_CONFIG_COMMON_PHY",",".join(
        str(v) for v in outcome["indices"]))
    print("CAPTURE_PROVENANCE_INDEPENDENTLY_AUTHENTICATED=NO")
    print("PROVIDER_RUNTIME_ORDER_PROVEN_FROM_TOOL_ALONE=NO")
    print("HARDWARE_BLOCKED: register semantics, cross-port effects and DART1 DMA")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
