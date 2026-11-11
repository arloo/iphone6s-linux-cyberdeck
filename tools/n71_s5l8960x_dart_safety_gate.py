#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed offline audit of patched Apple S5L8960x DART driver.

Confirms a patched packed 4x8-bit TCR implementation and identifies the
whole-instance reset on probe, remove AND resume. It does not declare DART1
safe for physical use; real stream ID, IOVA/DMA isolation remain unverified.
No firmware, MMIO, live phone access or generated files.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import re
import struct
import sys

ADT_FILE=Path(__file__).with_name("n71_s8000_adt_window_gate.py")
SPEC=importlib.util.spec_from_file_location("n71_dart_adt_gate",ADT_FILE)
assert SPEC and SPEC.loader
ADT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADT)

class UnqualifiedDART(ValueError):
    pass

def require(ok:bool,reason:str)->None:
    if not ok:raise UnqualifiedDART(reason)

def function(source:str,name:str)->str:
    # Only match definitions, never prototypes or comments.
    pattern=r"\bstatic\s+(?:__maybe_unused\s+)?(?:int|u32|void)\s+"+re.escape(name)+r"\s*\([^;]*?\)\s*\{"
    matched=re.search(pattern,source,re.S)
    require(matched is not None, "Required Apple DART function not present: "+name)
    begin=source.index("{",matched.start())
    depth=0
    for index in range(begin,len(source)):
        if source[index]=="{":
            depth+=1
        elif source[index]=="}":
            depth-=1
            if depth==0:return source[begin+1:index]
    raise UnqualifiedDART("Unterminated original DART source function")

def classify(source:str)->dict[str,object]:
    require(0<len(source)<200_000,"Invalid Apple DART source size")
    read=function(source,"apple_dart_s5l8960x_read_tcr")
    write=function(source,"apple_dart_s5l8960x_write_tcr")
    reset=function(source,"apple_dart_hw_reset")
    calls={phase:function(source,"apple_dart_"+phase)
           for phase in ("probe","remove","resume")}
    require("#define DART_S5L8960X_TCR_BITS_PER_STREAM" in source and
            re.search(r"#define DART_S5L8960X_TCR_BITS_PER_STREAM\s+8\b",source),
            "Expected four 8-bit TCR lane layout absent")
    require(re.search(r"\.max_sid_count\s*=\s*4\b",source) is not None,
            "Unexpected S5L8960x stream count")
    require('compatible = "apple,s5l8960x-dart"' in source,
            "No S5L8960x OF match")
    require("if (WARN_ON(sid >= 4))" in read and "return 0;" in read,
            "Read of invalid SID not rejected")
    require("if (WARN_ON(sid >= 4 || val > 0xff))" in write,
            "Invalid SID or TCR byte not rejected")
    require("mask = 0xffU << shift;" in write and
            "tcr = (tcr & ~mask) | ((val << shift) & mask);" in write,
            "Packed four-lane register write corrupts other streams")
    require("spin_lock_irqsave(&dart->lock, flags);" in write and
            "spin_unlock_irqrestore(&dart->lock, flags);" in write and
            write.index("spin_lock_irqsave")<write.index("tcr = readl")<
            write.index("writel(tcr")<write.index("spin_unlock_irqrestore"),
            "Packed DART register RMW not serialized")
    require("bitmap_set(stream_map.sidmap, 0, dart->num_streams);" in reset,
            "Unknown DART reset stream-selection behavior")
    require("apple_dart_hw_disable_dma(&stream_map);" in reset and
            "apple_dart_hw_clear_all_ttbrs(&stream_map);" in reset,
            "Unknown DART reset DMA/TTBR behavior")
    require(all("apple_dart_hw_reset(dart);" in body for body in calls.values()),
            "Unknown DART probe/remove/resume reset behavior")
    require("dart->supports_bypass = 0;" in source,
            "Legacy DART must not permit direct identity DMA bypass")
    return {
      "packed_tcr_rmw_patched":True,
      "s5l8960x_max_sid_count":4,
      "whole_dart_reset_on_probe":True,
      "whole_dart_reset_on_remove":True,
      "whole_dart_reset_on_resume":True,
      "stream_id_hardware_verified":False,
      "iova_and_dma_fault_isolation_verified":False,
      "safe_to_activate_dart1":False,
    }

def is_aarch64_rel_object(path:Path)->bool:
    s=path.stat()
    require(64<=s.st_size<=50_000_000,
            "Missing/oversized ARM64 driver object")
    with path.open("rb") as f:
        header=f.read(64)
    return (header[:4]==b"\x7fELF" and header[4:6]==b"\x02\x01" and
            struct.unpack_from("<H",header,16)[0]==1 and
            struct.unpack_from("<H",header,18)[0]==183)

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patched_private_linux_apple_dart_c",type=Path)
    parser.add_argument("privately_held_original_n71_adt",type=Path)
    parser.add_argument("compiled_private_aarch64_dart_object",type=Path)
    args=parser.parse_args()
    try:
        source=args.patched_private_linux_apple_dart_c.read_text()
        state=classify(source)
        require(is_aarch64_rel_object(args.compiled_private_aarch64_dart_object),
                "Patched Apple DART object is not AArch64 ELF REL")
        size=args.privately_held_original_n71_adt.stat().st_size
        require(0<size<=ADT.ADT.MAX_FILE,"Invalid private original N71 ADT size")
        evidence=ADT.audit_bytes(args.privately_held_original_n71_adt.read_bytes())
        require("S8000_ADT_METADATA_GATE_PASS" in evidence and
                "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in evidence,
                "N71 DART1 hardware metadata incomplete")
    except (OSError,UnicodeError,UnqualifiedDART,ADT.RejectedADT,
            ValueError,struct.error) as exc:
        print("N71_S5L8960X_DART_SAFETY_AUDIT_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_DART_S5L8960X_PACKED_TCR_RMW_FIX_ARM64_STATIC_PASS")
    print("DART1_ORIGINAL_ADT_WINDOW_AND_LOGICAL_MAPPER_PASS")
    print("DART_WHOLE_INSTANCE_RESET_ON_PROBE_REMOVE_RESUME=YES")
    print("S5L8960X_STREAM_COUNT",state["s5l8960x_max_sid_count"])
    print("ACTUAL_SID_IOVA_DMA_FAULT_ISOLATION_PROVEN=NO")
    print("DART1_PHYSICAL_BRINGUP_AUTHORIZED=NO")
    print("NO_DART_HARDWARE_ACCESS_OR_REGISTER_WRITE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
