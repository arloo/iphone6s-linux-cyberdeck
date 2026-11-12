#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-check original Apple N71 S8000 DART1 TTBR 4x4 MMIO layout vs Linux.

Read-only: authentic owner-held original iOS ARM64 N71 kernelcache +
original Apple Device Tree + locally retained Linux apple-dart.c text.
This proves ONLY per-logical-stream TTBR register address layout:
  offset = 0x40 + (logical_stream * 4 + table_index) * 4
No physical PCIe requester SID, valid page tables, DMA or Wi-Fi is proven.
Never exports original Apple executable, live IORegistry or private paths.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent

def load(alias,name):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

ORIGINAL=load("n71_ttbr_original","n71_original_dart_mapper_tcr_lane_gate.py")
CENSUS=load("n71_ttbr_census","n71_dart1_consumer_census_gate.py")
DART1_BASE=0x602008000
DART1_SIZE=0x4000
TTBR_BASE=0x40
STREAMS=4
TTBRS_PER_STREAM=4
ORIGINAL_INSTANCE_VTABLE_SLOT=1728
ORIGINAL_CLEAR_CODE_OFFSET=0x1b6c

# ARM64 literal instruction words from original privately held Apple
# AppleS5L8960XDART on owner S8000, iOS 15.8.8. No executable payload.
CLEAR_WORDS={
    0x1b80:0x7100103f, # CMP w1,#4
    0x1b84:0x54000262, # rejects logical stream >=4
    0x1b88:0xaa0103f4, # preserve stream index in w20
    0x1b9c:0xd2800008, # initial four-slot loop offset=0
    0x1ba0:0xf9456a69, # DART hardware registers pointer from object
    0x1ba4:0x531e768a, # LSL w10,w20,#2; x4
    0x1ba8:0x8b2a4929, # ADD x9,x9,w10,UXTW #2; x4 -> sid*16
    0x1bac:0x91010129, # ADD x9,x9,#0x40
    0x1bb0:0xb828693f, # STR wzr,[x9,x8]; clear EXACT 32-bit TTBR
    0x1bb4:0x91001108, # ADD x8,x8,#4; next TTBR
    0x1bb8:0xf100411f, # CMP x8,#0x10; four slots
    0x1bbc:0x54ffffa1, # B.NE back to 0x1bb0
}

class TTBRLayoutNotProven(ValueError):
    pass

def must(condition,reason):
    if not condition:raise TTBRLayoutNotProven(reason)

def original_s5l_clear_valid(code,instance_clear_vtable_method):
    must(len(code)==ORIGINAL.EXPECTED_LENGTHS[ORIGINAL.S5L],
         "Not expected original Apple S5L8960x ARM64 executable")
    must(instance_clear_vtable_method==ORIGINAL_CLEAR_CODE_OFFSET,
         "Original S5L DART instance clear-method vtable differs")
    for offset,word in CLEAR_WORDS.items():
        must(ORIGINAL.word(code,offset)==word,
             "Original Apple TTBR clear loop or stream index changed")
    return True

def original_ttbr_layout(kernel,adt):
    # Reuse the earlier strict genuine original 2-KEXT mapper/TCR
    # provenance and full Apple ADT unique-consumer audit.
    check=ORIGINAL.verify_original(kernel,adt)
    must(check["mapper_index"]==0 and
         check["hardware_stream_count_upper_bound"]==STREAMS,
         "Not original N71 WLAN DART1 stream0 topology")
    census=CENSUS.audit_bytes(adt)
    must(census["dart1_mapper_declared_consumers"]==1 and
         census["dart1_child_nodes"]==1,
         "Original N71 DART1 mapper not solely WLAN")
    main,modules=ORIGINAL.extract_original_modules(kernel)
    m=modules[ORIGINAL.S5L]
    code=m["code"]
    vm=m["vm"]
    base=ORIGINAL.G.adrp_add_str_vptr(
        vm+ORIGINAL.S5L_VPTR_SITE,
        ORIGINAL.word(code,ORIGINAL.S5L_VPTR_SITE),
        ORIGINAL.word(code,ORIGINAL.S5L_VPTR_SITE+4),
        ORIGINAL.word(code,ORIGINAL.S5L_VPTR_SITE+8))
    target=ORIGINAL.G.read_data_pointer(
        kernel,main,base+ORIGINAL_INSTANCE_VTABLE_SLOT)
    original_s5l_clear_valid(code,target-vm)
    return True

def check_linux_source(source):
    must(type(source) is str and 15000<=len(source)<=300000,
         "Original Linux apple-dart.c source size not accepted")
    required=[
        r"(?m)^#define\s+DART_S5L8960X_TTBR\s+0x40\s*$",
        r"(?m)^#define\s+DART_S5L8960X_TCR\s+0xc\s*$",
        r"(?m)^#define\s+DART_TTBR\(dart, sid, idx\)\s+",
        r"\(\(\(dart\)->hw->ttbr_count\s*\*\s*\(sid\)\)\s*<<\s*2\)",
        r"\(\(idx\)\s*<<\s*2\)",
        r"(?s)static const struct apple_dart_hw apple_dart_hw_s5l8960x =\s*\{.*?\.type\s*=\s*DART_S5L8960X",
        r"(?s)static const struct apple_dart_hw apple_dart_hw_s5l8960x =\s*\{.*?\.max_sid_count\s*=\s*4\s*,",
        r"(?s)static const struct apple_dart_hw apple_dart_hw_s5l8960x =\s*\{.*?\.ttbr\s*=\s*DART_S5L8960X_TTBR\s*,",
        r"(?s)static const struct apple_dart_hw apple_dart_hw_s5l8960x =\s*\{.*?\.ttbr_count\s*=\s*4\s*,",
        r"(?s)static void apple_dart_hw_clear_ttbr\(.*?DART_TTBR\(dart, sid, idx\)",
        r"(?s)static void apple_dart_hw_set_ttbr\(.*?DART_TTBR\(dart, sid, idx\)",
        r"(?s)static bool apple_n71_s8000_wlan_dart1_blocked\(.*?0x602008000ULL",
        r"(?s)static int apple_dart_probe\(.*?apple_n71_s8000_wlan_dart1_blocked\(pdev\).*?return -EOPNOTSUPP;.*?devm_platform_get_and_ioremap_resource",
    ]
    for signature in required:
        must(re.search(signature,source) is not None,
             "Linux S5L TTBR register layout or DART1 fail-closed guard changed")
    # Restrict source regexes to the S5L definition, not later SoC instances.
    match=re.search(
        r"static const struct apple_dart_hw apple_dart_hw_s5l8960x\s*=\s*\{(.*?)\n\};",
        source,re.S)
    must(match is not None,"Original Linux S5L hardware structure missing")
    body=match.group(1)
    for key,value in (
        ("type","DART_S5L8960X"),
        ("max_sid_count","4"),
        ("ttbr","DART_S5L8960X_TTBR"),
        ("ttbr_count","4"),
    ):
        must(re.search(r"\."+key+r"\s*=\s*"+value+r"\s*,",body) is not None,
             "S5L-only Linux TTBR hardware descriptor differs")
    return True

def offset_for(stream,slot):
    must(type(stream) is int and type(slot) is int and
         0<=stream<STREAMS and 0<=slot<TTBRS_PER_STREAM,
         "TTBR stream/table slot out of physical register layout")
    return TTBR_BASE+stream*TTBRS_PER_STREAM*4+slot*4

def validate_disjoint_registers():
    offsets=[offset_for(s,i) for s in range(STREAMS)
             for i in range(TTBRS_PER_STREAM)]
    must(len(set(offsets))==STREAMS*TTBRS_PER_STREAM,
         "Stream register ranges alias each other")
    must(all(n%4==0 and n+4<=DART1_SIZE for n in offsets),
         "TTBR layout extends outside original DART1 controller region")
    must([offset_for(0,i) for i in range(4)]==
         [0x40,0x44,0x48,0x4c],
         "Apple WLAN mapper0 TTBR register offsets changed")
    return offsets

def private_read(path,limit):
    must(path.is_file() and not path.is_symlink(),
         "Original owner source not available or symlink")
    size=path.stat().st_size
    must(8<size<=limit,"Original owner source size not accepted")
    return path.read_bytes()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("owner_private_n71_kernelcache",type=Path)
    p.add_argument("owner_private_original_n71_adt",type=Path)
    p.add_argument("locally_owned_linux_apple_dart_c",type=Path)
    args=p.parse_args()
    try:
        original_ttbr_layout(
            private_read(args.owner_private_n71_kernelcache,
                         ORIGINAL.MAX_KERNEL),
            private_read(args.owner_private_original_n71_adt,
                         ORIGINAL.ADT.ADT.MAX_FILE))
        check_linux_source(
            private_read(args.locally_owned_linux_apple_dart_c,300000)
            .decode("utf-8"))
        validate_disjoint_registers()
    except Exception:
        print("N71_ORIGINAL_S5L_DART1_TTBR_REGISTER_LAYOUT_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_ORIGINAL_S5L_DART1_TTBR_4X4_REGISTER_LAYOUT_STATIC_PASS")
    print("ORIGINAL_S5L_INSTANCE_VTABLE_TTBR_CLEAR_SLOT",1728)
    print("ORIGINAL_APPLE_TTBR_BASE_RELATIVE_OFFSET",hex(TTBR_BASE))
    print("ORIGINAL_APPLE_TTBR_LOGICAL_STREAMS",STREAMS)
    print("ORIGINAL_APPLE_TTBR_TABLES_PER_STREAM",TTBRS_PER_STREAM)
    print("WLAN_MAPPER_LOGICAL0_TTBR_RELATIVE_OFFSETS",
          "0x40 0x44 0x48 0x4c")
    print("LINUX_S5L_TTBR_REGISTER_LAYOUT_CORROBORATED=YES")
    print("PHYSICAL_PCIE_WLAN_REQUESTER_TO_DART1_HARDWARE_SID_PROVEN=NO")
    print("DART1_TTBR_PAGE_TABLE_IOVA_AND_FAULT_ISOLATION_PROVEN=NO")
    print("DART1_LINUX_KERNEL_PROBE_REMAINS_BLOCKED_BEFORE_MMIO=YES")
    print("PRIVATE_APPLE_ORIGINAL_BINARY_OR_LIVE_CONTENT_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
