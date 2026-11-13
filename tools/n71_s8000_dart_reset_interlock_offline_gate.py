#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prove an OFFLINE, S8000-only all-stream DART reset refusal interlock.

Checks one narrowly scoped exact public unified patch, the original and new
isolated kernel sources, the actual cross-compiled AArch64 apple-dart.o, and
the lifecycle graph. No device, kernel module, MMIO or firmware is touched.
A successful audit does NOT qualify S8000 hardware isolation or native WLAN.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"experimental/patches/0016-n71-s8000-all-stream-dart-reset-interlock-offline.patch"
BEFORE_SHA="75e2808234541e1424e15ac411c512df5c9cefdab75535bdec469582bbd3e10e"
AFTER_SHA="67b33806dbb36f5fdb305d66f773af2c30db52cf69f61f076b33be0fa2edc65e"
OBJECT_SHA="de8a360959dcba30f377a62861719a5617c539631c4cd2834b7bd30901c59c3c"
DIFF="diff --git a/drivers/iommu/apple-dart.c b/drivers/iommu/apple-dart.c\n"

class UnsafeInterlock(ValueError):pass

def need(ok,why):
    if not ok:raise UnsafeInterlock(why)

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def strict_read(p:Path,limit:int)->bytes:
    need(p.is_file() and not p.is_symlink() and 1024 < p.stat().st_size < limit,
         "Missing or oversized private build evidence")
    return p.read_bytes()

def source_delta(before:str,after:str)->str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),after.splitlines(keepends=True),
        fromfile="a/drivers/iommu/apple-dart.c",
        tofile="b/drivers/iommu/apple-dart.c",n=5))

def patch_contract(patch:str)->str:
    need(patch.count("diff --git ")==1 and DIFF in patch,
         "Unexpected modified driver files")
    need("SPDX-License-Identifier: GPL-2.0-only" in patch,
         "Original GPL source attribution absent")
    body=patch.split(DIFF,1)[1]
    need(body.count("\n@@ ")==2, "Unreviewed number of reset-function hunks")
    changed=[s for s in body.splitlines()
             if s.startswith(("+","-")) and not s.startswith(("+++","---"))]
    need([s[1:] for s in changed if s.startswith("-")]==
         ["\tapple_dart_hw_reset(dart);"],
         "Patch removes more than previously unobserved teardown return value")
    added="\n".join(s[1:] for s in changed if s.startswith("+"))
    for token in ("apple_dart_s8000_unqualified_global_reset",
                  "of_machine_is_compatible(\"apple,s8000\")",
                  "of_machine_is_compatible(\"apple,n71\")",
                  "return -EOPNOTSUPP;",
                  "if (apple_dart_hw_reset(dart))"):
        need(token in added,"Reset guard lacks mandatory fail-closed element")
    for forbidden in ("writel(","ioremap(","pci_host_probe(","modprobe","insmod",
                      "iommu_map(","set_bit(","bitmap_set("):
        need(forbidden not in added,"Reset refusal patch adds hardware operations")
    return body

def slice_function(src:str,start:str,end:str)->str:
    i=src.find(start);need(i>=0,"Missing driver lifecycle function")
    j=src.find(end,i+len(start));need(j>i,"Unbounded driver lifecycle function")
    return src[i:j]

def source_contract(src:str)->bool:
    guard=slice_function(src,
        "static bool apple_dart_s8000_unqualified_global_reset(",
        "static int apple_dart_hw_reset(")
    need("dart->hw->type == DART_S5L8960X" in guard and
         "of_machine_is_compatible(\"apple,s8000\")" in guard and
         "of_machine_is_compatible(\"apple,n71\")" in guard and
         "of_machine_is_compatible(\"apple,iphone8,1\")" in guard,
         "A9 family or N71 reset policy weakened")
    reset=slice_function(src,"static int apple_dart_hw_reset(",
                         "static void apple_dart_domain_block(")
    at=reset.find("if (apple_dart_s8000_unqualified_global_reset(dart))")
    rejection=reset.find("return -EOPNOTSUPP;",at)
    mmio=reset.find("readl(dart->regs + dart->hw->lock)")
    any_ttbr=reset.find("apple_dart_hw_clear_all_ttbrs(&stream_map);")
    need(0<=at<rejection<mmio<any_ttbr,
         "S8000 reset must abort before the FIRST MMIO access")
    need("bitmap_set(stream_map.sidmap, 0, dart->num_streams);" in reset,
         "Existing original all-stream hazard silently omitted")
    need("apple_dart_hw_disable_dma(&stream_map);" in reset,
         "Original global reset behavior not acknowledged")
    probe=slice_function(src,"static int apple_dart_probe(",
                         "static void apple_dart_remove(")
    i=probe.find("if (apple_n71_s8000_wlan_dart1_blocked(pdev))")
    j=probe.find("devm_platform_get_and_ioremap_resource(pdev")
    need(0<=i<j and "return -EOPNOTSUPP;" in probe[i:j],
         "Existing N71 DART1 *probe* pre-MMIO block missing")
    need("ret = apple_dart_hw_reset(dart);" in probe and
         "if (ret)" in probe, "Probe did not propagate reset refusal")
    remove=slice_function(src,"static void apple_dart_remove(",
                          "static const struct apple_dart_hw apple_dart_hw_s5l8960x")
    need("if (apple_dart_hw_reset(dart))" in remove and
         "dev_warn(" in remove,"Remove path hides reset refusal")
    resume=slice_function(src,"static __maybe_unused int apple_dart_resume(",
                          "static DEFINE_SIMPLE_DEV_PM_OPS(")
    need("ret = apple_dart_hw_reset(dart);" in resume and
         "if (ret)" in resume and "return ret;" in resume,
         "Resume must propagate refusal before restoring any TTBR")
    for bad in ("allow_unsafe_reset","module_param(","ignore_reset_error",
                "skip_reset_guard","force_dart_reset"):
        need(bad not in reset and bad not in guard,
             "User-toggleable hardware guard override detected")
    return True

def symbolic_reset_allowed(soc:str,board:str,legacy:bool)->bool:
    """One pure policy model: deny S8000/N71 and legacy DART regardless SID."""
    need(type(soc) is str and type(board) is str and
         type(legacy) is bool,"Unsafe test input")
    return not(legacy and
               (soc=="apple,s8000" or
                board in ("apple,n71","apple,iphone8,1")))

def object_contract(blob:bytes):
    need(len(blob)>100_000 and blob[:6]==b"\x7fELF\x02\x01",
         "Not a real AArch64 ELF64 object")
    typ,machine=struct.unpack_from("<HH",blob,16)
    need(typ==1 and machine==183,
         "Not an ARM64 relocatable kernel object")
    return True

def audit(before:bytes,after:bytes,patch:bytes,obj:bytes)->bool:
    need(sha(before)==BEFORE_SHA and sha(after)==AFTER_SHA,
         "Unpinned source or modified reset interlock")
    need(sha(obj)==OBJECT_SHA,"Real compiled A9 DART object hash mismatch")
    try:b=before.decode();a=after.decode();p=patch.decode()
    except UnicodeError as e:raise UnsafeInterlock("Non-UTF8 C source") from e
    need(source_delta(b,a)==patch_contract(p),
         "Public source change differs from the compiled A9 C source")
    source_contract(a)
    object_contract(obj)
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ("previous_isolated_dart_source",
              "new_isolated_dart_source","new_arm64_dart_object"):
        parser.add_argument(n,type=Path)
    args=parser.parse_args()
    try:
        audit(strict_read(args.previous_isolated_dart_source,150_000),
              strict_read(args.new_isolated_dart_source,150_000),
              strict_read(PATCH,20_000),
              strict_read(args.new_arm64_dart_object,3_000_000))
    except (UnsafeInterlock,OSError):
        print("N71_S8000_ALL_STREAM_DART_RESET_INTERLOCK_OFFLINE_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S8000_ALL_STREAM_DART_RESET_INTERLOCK_ARM64_SOURCE_PASS")
    print("N71_CENTRAL_RESET_REFUSED_BEFORE_FIRST_RESET_MMIO=YES")
    print("N71_DART1_PROBE_PRE_MMIO_GUARD_UNMODIFIED=YES")
    print("N71_PROBE_REMOVE_RESUME_RESET_LIFECYCLE_AUDITED=YES")
    print("N71_S8000_RESET_CANNOT_BE_ENABLED_BY_RUNTIME_OPTION=YES")
    print("N71_SOURCE_PATCH_AND_REAL_AARCH64_ELF_PIN_MATCH=YES")
    print("N71_PHYSICAL_DART1_SID_OR_SHARED_ROOT_ISOLATION_PROVEN=NO")
    print("N71_BCM4350_PCIE_OR_NATIVE_WIFI_ENUMERATED=NO")
    print("N71_NO_PHONE_REBOOT_DART_MMIO_NAND_OR_DMA=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
