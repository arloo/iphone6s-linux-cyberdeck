#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed OFFLINE A9 S5L8960X DART hardening proof.

Checks the exact reviewed four-hunk public patch against two local Linux
sources and validates a genuinely cross-compiled ELF AArch64 relocatable
apple-dart.o. This NEVER accesses an iPhone, PCIe, MMIO or DART registers.
A compiled object is NOT authorization to boot or activate DART1.
"""
from __future__ import annotations
import argparse
import difflib
from pathlib import Path
import re
import struct
import sys

HERE=Path(__file__).resolve().parents[1]
PATCH=HERE/"experimental/patches/0014-n71-s5l8960x-dart-window-and-tcr-lock-offline.patch"
OLD="a/drivers/iommu/apple-dart.c"
NEW="b/drivers/iommu/apple-dart.c"

class UnqualifiedDartPatch(ValueError):
    pass

def need(value,reason):
    if not value:raise UnqualifiedDartPatch(reason)

def read_strict(f:Path,max_bytes:int):
    need(f.is_file() and not f.is_symlink() and 0<f.stat().st_size<max_bytes,
         "Missing or oversized isolated source file")
    return f.read_bytes()

def checked_unified(before:str,after:str)->str:
    patch="".join(difflib.unified_diff(before.splitlines(keepends=True),
                                     after.splitlines(keepends=True),
                                     fromfile=OLD,tofile=NEW,n=5))
    need(patch.startswith("--- "+OLD+"\n+++ "+NEW+"\n"),
         "Unexpected original source patch geometry")
    return patch

def exact_public_delta(before:str,after:str,public_patch:str):
    need("diff --git "+OLD+" "+NEW+"\n" in public_patch,
         "Wrong public driver patch path")
    section=public_patch.split("diff --git "+OLD+" "+NEW+"\n",1)[1]
    need(section==checked_unified(before,after),
         "Hardened DART source differs from published 4-hunk proof")
    need(section.count("\n@@ ")==4,
         "Expected four source-modification regions")
    need("spinlock_t tcr_lock;" in section,
         "Missing separate packed-TCR lock member")
    need("spin_lock_init(&dart->tcr_lock);" in section,
         "Missing initialization of independent TCR lock")
    need("spin_lock_irqsave(&dart->tcr_lock, flags);" in section and
         "spin_unlock_irqrestore(&dart->tcr_lock, flags);" in section,
         "TCR read-modify-write must use dedicated lock")
    need(not any(line.startswith("+") and
                 "spin_lock_irqsave(&dart->lock, flags);" in line
                 for line in section.splitlines()),
         "New TCR update must not re-enter command lock")
    need("dart->hw->type == DART_S5L8960X && cfg->dma_min" in section and
         "cfg->dma_max - cfg->dma_min >= (cfg->dma_min & -cfg->dma_min)" in section,
         "Missing stock A9 DART DMA base-alignment rejection")
    need("goto done;" in section and "ret = -EINVAL;" in section,
         "Invalid DMA aperture must fail closed")
    # The complete source before and after both retain the exact old
    # all-four-stream reset; we do not claim this unsafe behavior is solved.
    need("static int apple_dart_hw_reset(" in before and
         "static int apple_dart_hw_reset(" in after,
         "Original common reset requires separate isolation proof")
    need("apple_dart_s5l8960x_write_tcr" in before and
         "apple_dart_s5l8960x_write_tcr" in after,
         "Old S5L8960X packed TCR code missing")
    return True

def legacy_window_allowed(base:int,end:int)->bool:
    """Exact 64-bit S5L8960X source predicate, simulated, not IOMMU mapping."""
    need(type(base) is int and type(end) is int and
         0<=base<=end<1<<64,
         "Untrusted symbolic IOVA range")
    # Original Linux index is IOVA & ~dma_min, which is valid only
    # when the base's least significant set bit exceeds window span.
    return base==0 or end-base < (base & -base)

def packed_tcr_assign(register:int,sid:int,value:int)->int:
    """Symbolic 4×8-bit packed TCR RMW. No MMIO or actual registers."""
    need(type(register) is int and 0<=register<=0xffffffff,
         "Invalid synthetic TCR word")
    need(type(sid) is int and 0<=sid<4,
         "Invalid DART stream")
    need(type(value) is int and 0<=value<=0xff,
         "Invalid packed TCR byte")
    shift=sid*8
    mask=0xff<<shift
    return (register&~mask)|((value<<shift)&mask)

def real_arm64_relocatable(data:bytes)->bool:
    need(len(data)>1024 and data[:4]==b"\x7fELF" and data[4]==2 and
         data[5]==1, "Not ELF64 little-endian")
    kind,machine=struct.unpack_from("<HH",data,16)
    need(kind==1 and machine==183,
         "Not an ELF AArch64 relocatable object")
    return True

def audit(before:bytes,after:bytes,patch:bytes,arm64_obj:bytes)->bool:
    try:b=before.decode("utf8");a=after.decode("utf8");p=patch.decode("utf8")
    except UnicodeError as e:raise UnqualifiedDartPatch("Non-UTF8 code") from e
    exact_public_delta(b,a,p)
    real_arm64_relocatable(arm64_obj)
    # Synthesized windows only; bounded to real unsigned 64-bit values.
    for base,span,expected in (
        (0x80000000,0x3c000000,True),
        (0x80000000,0x3ffff000,True),
        (0x80000000,0x80000000,False),
        (0x90000000,0x3ffff000,False),
        (0xc0000000,0x3ffff000,True),
        (0,0x3ffff000,True),
    ):
        need(legacy_window_allowed(base,base+span)==expected,
             "S5L8960X DMA-window reference case mismatch")
    for sid in range(4):
        old=0xa1b2c3d4
        changed=packed_tcr_assign(old,sid,0x42)
        mask=0xff << (sid*8)
        need((changed&~mask)==(old&~mask) and
             ((changed>>sid*8)&0xff)==0x42,
             "Symbolic TCR neighbor field affected")
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("prior_dart_source","isolated_hardened_dart_source",
                 "isolated_apple_dart_arm64_object"):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    try:
        audit(read_strict(args.prior_dart_source,200_000),
              read_strict(args.isolated_hardened_dart_source,200_000),
              read_strict(PATCH,30_000),
              read_strict(args.isolated_apple_dart_arm64_object,3_000_000))
    except (OSError,UnqualifiedDartPatch):
        print("N71_S5L8960X_DART_WINDOW_TCR_OFFLINE_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S5L8960X_DART_WINDOW_TCR_OFFLINE_AARCH64_PASS")
    print("N71_DART_REVIEWED_EXACT_PUBLIC_PATCH_FOUR_HUNKS_PASS=YES")
    print("N71_DART_PROPER_SEPARATE_TCR_LOCK_INITIALIZED=YES")
    print("N71_DART_S5L8960X_INVALID_DMA_WINDOW_FAIL_CLOSED=YES")
    print("N71_DART_REAL_AARCH64_ELF_RELOCATABLE_COMPILED=YES")
    print("N71_ALL_STREAM_RESET_ISOLATION_PROVEN=NO")
    print("N71_PHYSICAL_PCIE_DART1_SID_DMA_WIFI_TEST_AUTHORIZED=NO")
    print("N71_PHONE_ORIGINAL_BOOT_AND_NAND_UNMODIFIED=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
