#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed OFFLINE provenance / ARM64 build gate for N71 A9 DART patch 0015.

No phone shell, no bus scan, no MMIO, no register write or module load.
Requires exact old/new driver sources, the exact published 12-hunk patch
and the actual ARM64 kernel object produced by the *isolated* build.
This cannot prove the physical PCIe requester SID or DART1 isolation.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"experimental/patches/0015-n71-s5l8960x-dart-ios-order-ttbr-tlb-failclosed-offline.patch"
OLD_SHA="811c0c4b76e2a47aba9f0ad26dc252d05e61b4164d294ff79d8c0c3b6f0caaa9"
NEW_SHA="75e2808234541e1424e15ac411c512df5c9cefdab75535bdec469582bbd3e10e"
ELF_SHA="af53479fc7b4e19468e180905a0720dff469c26f1a11cb2691e8e857f064edc9"

class UnprovenSafety(ValueError):pass

def require(ok,why):
    if not ok:raise UnprovenSafety(why)

def sha(blob:bytes)->str:return hashlib.sha256(blob).hexdigest()

def exact_file(p:Path,limit:int)->bytes:
    require(p.is_file() and not p.is_symlink() and 100<p.stat().st_size<limit,
            "Missing, linked, or unexpectedly sized offline build source")
    return p.read_bytes()

def diff_body(before:str,after:str)->str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),after.splitlines(keepends=True),
        fromfile="a/drivers/iommu/apple-dart.c",
        tofile="b/drivers/iommu/apple-dart.c",n=5))

def patch_contract(patch:str):
    require("diff --git a/drivers/iommu/apple-dart.c b/drivers/iommu/apple-dart.c\n" in patch,
            "No unique intended DART file header")
    require(patch.count("diff --git ")==1,"Additional files touched")
    require("SPDX-License-Identifier: GPL-2.0-only" in patch,
            "Missing explicit upstream GPL provenance")
    body=patch.split("diff --git a/drivers/iommu/apple-dart.c b/drivers/iommu/apple-dart.c\n",1)[1]
    require(body.count("\n@@ ")==12,"Not the reviewed exact 12-region patch")
    changes=[l for l in body.splitlines()
             if (l.startswith("+") and not l.startswith("+++")) or
                (l.startswith("-") and not l.startswith("---"))]
    require(not any("apple_n71_s8000_wlan_dart1_blocked" in l for l in changes),
            "N71 pre-MMIO WLAN DART1 guard was altered")
    added="\n".join(l[1:] for l in changes if l.startswith("+"))
    for marker in (
        "apple_dart_s5l8960x_parse_config",
        "apple,error-reflector",
        "apple,fetch-config",
        "apple,diag-config",
        "apple_dart_s5l8960x_set_reflector",
        "apple_dart_s5l8960x_set_configs",
        "apple_dart_s5l8960x_setup_translation",
        "apple_dart_streams_tcr_is",
        "apple_dart_streams_ttbrs_are",
        "apple_dart_domain_block",
        "flush_error",
        "ret = -EIO;",
        "ret = dart->hw->invalidate_tlb(stream_map);",
        "if (ret)",
        "return apple_dart_domain_flush_tlb(to_dart_domain(domain));",
        "if (READ_ONCE(dart_domain->flush_error))",
    ):
        require(marker in added,"Required fail-closed guard missing from patch")
    return body

def function(src:str,start:str,end:str)->str:
    i=src.find(start);require(i>=0,"Missing driver function")
    j=src.find(end,i+len(start));require(j>i,"Unbounded driver function")
    return src[i:j]

def source_contract(src:str):
    require(src.count("static int\napple_dart_setup_translation(")==1,
            "Expected single int-returning translation setup")
    probe=function(src,"static int apple_dart_probe(","static void apple_dart_remove(")
    i_guard=probe.find("if (apple_n71_s8000_wlan_dart1_blocked(pdev))")
    i_mmio=probe.find("devm_platform_get_and_ioremap_resource(")
    require(0<=i_guard<i_mmio,"N71 DART1 must refuse BEFORE MMIO mapping")
    require("return -EOPNOTSUPP;" in probe[i_guard:i_mmio],
            "N71 DART1 fail-closed return absent")
    parse=src.find("apple_dart_s5l8960x_parse_config(dart);")
    require(parse>=0 and probe.find("apple_dart_s5l8960x_parse_config(dart);")>=0,
            "A9 optional DT property parse absent")
    setup=function(src,"static int\napple_dart_s5l8960x_setup_translation(","static int\napple_dart_setup_translation(")
    expected_order=(
        "apple_dart_hw_disable_dma(stream_map);",
        "apple_dart_streams_tcr_is(stream_map, dart->hw->tcr_disabled)",
        "apple_dart_s5l8960x_set_reflector(dart);",
        "apple_dart_hw_set_ttbr(stream_map, i,",
        "apple_dart_hw_enable_translation(stream_map,",
        "apple_dart_streams_tcr_is(stream_map, dart->hw->tcr_enabled)",
        "apple_dart_s5l8960x_set_configs(dart);",
        "ret = dart->hw->invalidate_tlb(stream_map);",
        "apple_dart_streams_ttbrs_are(stream_map, pgtbl_cfg)",
        "apple_dart_domain_block(domain, stream_map, ret);",
    )
    at=-1
    for phrase in expected_order:
        n=setup.find(phrase,at+1)
        require(n>at,"A9 ordered TTBR/TCR/fail-closed readback stage missing or reordered")
        at=n
    flush=function(src,"static int apple_dart_domain_flush_tlb(","static void apple_dart_flush_iotlb_all(")
    require("ret = stream_map.dart->hw->invalidate_tlb(&stream_map);" in flush and
            "apple_dart_domain_block(domain, &stream_map, ret);" in flush and
            "return err ?: READ_ONCE(domain->flush_error);" in flush,
            "TLB timeout not propagated and owned streams not blocked")
    require("return apple_dart_domain_flush_tlb(to_dart_domain(domain));" in src,
            "IOTLB mapping synchronization error must propagate")
    block=function(src,"static void apple_dart_domain_block(","static int apple_dart_domain_flush_tlb(")
    require("if (stream_map->dart->hw->type != DART_S5L8960X)" in block and
            "apple_dart_hw_disable_dma(stream_map);" in block and
            "WRITE_ONCE(domain->flush_error, error);" in block,
            "Legacy stream isolation / sticky fault missing")
    require("apple_dart_hw_reset(" not in block,
            "Unsafe all-stream reset must not be used for a recoverable error")
    maps=function(src,"static int apple_dart_map_pages(","static size_t apple_dart_unmap_pages(")
    require("if (READ_ONCE(dart_domain->flush_error))" in maps and
            "return READ_ONCE(dart_domain->flush_error);" in maps,
            "Future DMA mappings not refused after a failed invalidation")
    attach=function(src,"static int apple_dart_attach_dev_paging(","static int apple_dart_attach_dev_identity(")
    require("ret = apple_dart_setup_translation(dart_domain, stream_map);" in attach and
            "if (ret)" in attach and "return ret;" in attach,
            "Device attachment must fail when translation setup fails")
    # Important: the unsafe legacy all-stream reset is still present, so
    # this candidate MUST remain OFFLINE and may not claim DMA isolation.
    reset=function(src,"static int apple_dart_hw_reset(","static int apple_dart_domain_flush_tlb(")
    require("bitmap_set(stream_map.sidmap, 0, dart->num_streams);" in reset and
            "apple_dart_hw_clear_all_ttbrs(&stream_map);" in reset,
            "Potential all-stream reset hazard must be explicitly acknowledged")
    return True

def elf_contract(data:bytes):
    require(len(data)>100_000 and data[:6]==b"\x7fELF\x02\x01",
            "Not valid ELF64 little-endian")
    kind,machine=struct.unpack_from("<HH",data,16)
    require(kind==1 and machine==183,
            "Not AArch64 relocatable kernel object")
    return True

def model_fail_closed(*, disabled_ok=True, enabled_ok=True,
                      tlb_ok=True, ttbr_ok=True):
    """Synthetic expected stage result; not an executable kernel simulator."""
    for stage in (disabled_ok,enabled_ok,tlb_ok,ttbr_ok):
        require(type(stage) is bool,"Invalid symbolic stage outcome")
        if not stage:return False,True
    return True,False

def audit(before:bytes,after:bytes,patch:bytes,elf:bytes):
    require(sha(before)==OLD_SHA and sha(after)==NEW_SHA,
            "Source is not the precisely reviewed private isolated build")
    require(sha(elf)==ELF_SHA,"Compiler object differs from verified AArch64 build")
    try:b=before.decode();a=after.decode();p=patch.decode()
    except UnicodeError as e:raise UnprovenSafety("Non-text source") from e
    contract=patch_contract(p)
    require(contract==diff_body(b,a),"Published patch does not exactly equal source delta")
    source_contract(a)
    elf_contract(elf)
    return True

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("prior_isolated_dart_source","new_isolated_dart_source",
                "compiled_aarch64_dart_object"):
        ap.add_argument(key,type=Path)
    args=ap.parse_args()
    try:
        audit(exact_file(args.prior_isolated_dart_source,150_000),
              exact_file(args.new_isolated_dart_source,150_000),
              exact_file(PATCH,50_000),
              exact_file(args.compiled_aarch64_dart_object,3_000_000))
    except (OSError,UnprovenSafety):
        print("N71_DART_S5L_TTBR_TLB_FAIL_CLOSED_OFFLINE_PROOF_NOT_ESTABLISHED",
              file=sys.stderr)
        return 2
    print("N71_DART_S5L_TTBR_TLB_FAIL_CLOSED_OFFLINE_AARCH64_SOURCE_PASS")
    print("N71_REPRODUCED_EXACT_REVIEWED_12_HUNK_SOURCE_DELTA_PASS=YES")
    print("N71_S5L_TTBR_TCR_READBACK_AND_TLB_ERRORS_FAIL_CLOSED=YES")
    print("N71_A9_DART1_PRE_MMIO_BLOCK_STILL_ENFORCED=YES")
    print("N71_REAL_ARM64_DART_ELF_RELOCATABLE_COMPILED=YES")
    print("N71_PHYSICAL_ALL_STREAM_RESET_AND_SID_ISOLATION_PROVEN=NO")
    print("N71_NATIVE_PCIE_WIFI_OR_IOMMU_LINK_PROVEN=NO")
    print("N71_NO_PHONE_MMIO_DMA_NAND_OR_REBOOT=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
