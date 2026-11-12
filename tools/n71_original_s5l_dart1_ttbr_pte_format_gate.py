#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline Apple N71/S8000 original TTBR encoding and DART1 PTE format gate.

Real owner-private Apple S5L8960x ARM64 executable versus actual
Hoolock-derived Linux apple-dart.c + io-pgtable-dart.c.
Proof scope: software field encoding ONLY, never physical PCIe requester
to stream SID, DMA validity or safe on-phone hardware initialization.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location(
    "n71_nativettbr_addr",HERE/"n71_original_s5l_dart1_ttbr_register_layout_gate.py")
assert spec and spec.loader
BASE=importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)

# Original Apple S5L8960x TTBR programming method:
# X0 is page-table root address, W20 <- X0>>12; hardware register word is
# bit31 | (root_addr>>12 & 0x00ffffff), stored to indexed +0x40.
ORIGINAL_TTBR_PROGRAM_WORDS={
    0x17a8:0xd34cfc14,  # LSR X20, X0, #12
    0x17c4:0x52b00008,  # MOV W8, 0x80000000 (TTBR valid)
    0x17c8:0x33005e88,  # BFXIL W8, W20, #0, #24 (24-bit page number)
    0x17d0:0xf9456ac9,  # original controller register pointer
    0x17d8:0x8b2a4929,  # ADD register address, W10 index *4
    0x17dc:0xb9004128,  # STR W8, [X9,#64] (TTBR register)
}
# Original software page-table-map builder + helper. The 24-bit source
# page number is inserted into PTE bits 12..35. The caller supplies
# entry bit0 and the builder ORs bit1.
ORIGINAL_PTE_BUILDER_WORDS={
    0x21c0:0x12000268,  # AND W8, W19, #1 (caller valid/flags bit0)
    0x21d4:0x12005e89,  # AND W9, W20, #0xffffff
    0x21d8:0xb3745d28,  # BFI X8, X9, #12, #24
    0x21dc:0xb27f0103,  # ORR X3, X8, #2
    0x21ec:0x97ffff6c,  # BL local method 0x1f9c
    0x1fec:0x12002049,  # AND W9, W2, #0x1ff (indexed PTE)
    0x1ff4:0xf8295903,  # STR X3, [X8,W9,UXTW #3] (64-bit PTE)
}

class FormatNotQualified(ValueError):
    pass

def must(value,reason):
    if not value:raise FormatNotQualified(reason)

def verify_native_instruction_format(code):
    must(len(code)==BASE.ORIGINAL.EXPECTED_LENGTHS[BASE.ORIGINAL.S5L],
         "Wrong original Apple S5L private executable length")
    for at,w in {**ORIGINAL_TTBR_PROGRAM_WORDS,
                 **ORIGINAL_PTE_BUILDER_WORDS}.items():
        must(BASE.ORIGINAL.word(code,at)==w,
             "Original Apple TTBR/PTE map field layout changed")
    return True

def verify_linux_format(ttbr_source,pte_source):
    # Only source-level field semantics; no attempt to claim real DMA.
    required_ttbr=[
        r"#define\s+DART_T8020_TTBR_VALID\s+BIT\(31\)",
        r"#define\s+DART_T8020_TTBR_SHIFT\s+12",
        r"#define\s+DART_T8020_TTBR_ADDR_FIELD_SHIFT\s+0",
        r"\.ttbr_valid\s*=\s*DART_T8020_TTBR_VALID",
        r"\.ttbr_addr_field_shift\s*=\s*DART_T8020_TTBR_ADDR_FIELD_SHIFT",
        r"\.ttbr_shift\s*=\s*DART_T8020_TTBR_SHIFT",
    ]
    required_pte=[
        r"#define\s+APPLE_DART1_PADDR_MASK\s+GENMASK_ULL\(35,\s*12\)",
        r"#define\s+APPLE_DART_PTE_VALID\s+BIT\(0\)",
        r"#define\s+APPLE_DART1_PTE_PROT_SP_DIS\s+BIT\(1\)",
        r"typedef\s+u64\s+dart_iopte",
        r"pte\s*\|=\s*APPLE_DART_PTE_VALID",
        r"pte\s*\|=\s*APPLE_DART1_PTE_PROT_SP_DIS",
        r"if\s*\(data->iop.fmt\s*==\s*APPLE_DART\)",
    ]
    for regex in required_ttbr:
        must(re.search(regex,ttbr_source) is not None,
             "Linux TTBR S5L source field encoding unverified")
    for regex in required_pte:
        must(re.search(regex,pte_source) is not None,
             "Linux DART1 page table format unverified")
    return True

def encode_ttbr(root_physical):
    must(type(root_physical) is int and root_physical>=0 and
         root_physical<(1<<36) and root_physical%4096==0,
         "TTBR physical page base cannot be encoded on S5L8960x")
    return 0x80000000|((root_physical>>12)&0xffffff)

def encode_dart_pte(page_physical,valid):
    must(type(valid) is bool and type(page_physical) is int and
         0<=page_physical<(1<<36) and page_physical%4096==0,
         "DART1 64-bit PTE physical frame not eligible")
    return (page_physical&0xffffff000)|(int(valid))|2

def check_all(kernel,adt,linux_dart,linux_pgtable):
    must(BASE.original_ttbr_layout(kernel,adt) is True,
         "Original Apple DART1 identity or TTBR register layout changed")
    must(BASE.check_linux_source(linux_dart),
         "Original S5L Linux TTBR layout invalid")
    _,modules=BASE.ORIGINAL.extract_original_modules(kernel)
    code=modules[BASE.ORIGINAL.S5L]["code"]
    verify_native_instruction_format(code)
    verify_linux_format(linux_dart,linux_pgtable)
    must(encode_ttbr(0x12345000)==0x80012345 and
         encode_dart_pte(0x12345000,True)==0x12345003 and
         encode_dart_pte(0x12345000,False)==0x12345002,
         "TTBR/PTE synthetic software format self-test failed")
    return True

def source_bytes(path,limit):
    return BASE.private_read(path,limit)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("original_n71_macho",type=Path)
    ap.add_argument("original_n71_apple_adt",type=Path)
    ap.add_argument("linux_apple_dart_driver_c",type=Path)
    ap.add_argument("linux_io_pgtable_dart_c",type=Path)
    a=ap.parse_args()
    try:
        # Use read-only owner-held sources; never log private source paths.
        kernel=source_bytes(a.original_n71_macho,BASE.ORIGINAL.MAX_KERNEL)
        adt=source_bytes(a.original_n71_apple_adt,BASE.ORIGINAL.ADT.ADT.MAX_FILE)
        ls=source_bytes(a.linux_apple_dart_driver_c,300000).decode("utf-8")
        ps=source_bytes(a.linux_io_pgtable_dart_c,300000).decode("utf-8")
        check_all(kernel,adt,ls,ps)
    except Exception:
        print("N71_ORIGINAL_APPLE_S5L_DART1_TTBR_PTE_FORMAT_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_ORIGINAL_APPLE_S5L_DART1_TTBR_PTE_FORMAT_STATIC_PASS")
    print("ORIGINAL_APPLE_TTBR_VALID_BIT",31)
    print("ORIGINAL_APPLE_TTBR_PHYSICAL_PAGE_SHIFT",12)
    print("ORIGINAL_APPLE_TTBR_PHYSICAL_PAGE_NUMBER_BITS",24)
    print("ORIGINAL_APPLE_DART_PTE_ADDRESS_BITS", "12..35")
    print("ORIGINAL_APPLE_DART_PTE_CALLER_VALID_BIT",0)
    print("ORIGINAL_APPLE_DART_PTE_FIXED_FLAG_BIT",1)
    print("ORIGINAL_APPLE_DART_PTE_WRITE_WIDTH_BITS",64)
    print("LINUX_APPLE_DART1_SOFTWARE_ENCODING_MATCH=YES")
    print("PHYSICAL_WLAN_PCIE_REQUESTER_TO_DART_SID_PROVEN=NO")
    print("LIVE_DART1_DMA_TRANSLATION_SAFETY_OR_FAULT_RECOVERY_PROVEN=NO")
    print("AUTHORIZATION_TO_WRITE_DART1_MMIO_OR_TTBR=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
