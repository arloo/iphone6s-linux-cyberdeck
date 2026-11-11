#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only pinned iPhone 6s S8000 common-register OFFSET audit.

Only reads a user's local, already decompressed ARM64 iOS 15.8.8 kernelcache.
Derived offsets are static interface metadata, NOT MMIO base, register names,
permission to touch registers, or an initialization sequence.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

MAP_PATH = Path(__file__).resolve().with_name("n71_kernelcache_pcie_kext_map.py")
spec = importlib.util.spec_from_file_location("n71_a9_kext_map", MAP_PATH)
assert spec and spec.loader
KMAP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(KMAP)

A9 = "com.apple.driver.AppleS8000PCIe"

class UnverifiedCode(ValueError):
    pass

def check(ok: bool, why: str) -> None:
    if not ok:
        raise UnverifiedCode(why)

def word(code: bytes, offset: int) -> int:
    check(offset >= 0 and offset + 4 <= len(code) and offset % 4 == 0,
          "A9 instruction out of bounds")
    return struct.unpack_from("<I", code, offset)[0]

def a64_movz_w0(imm: int) -> int:
    check(0 <= imm <= 0xffff, "MOVZ immediate out of range")
    return 0x52800000 | (imm << 5)

def a64_lsl_w8_w19_7() -> int:
    # Alias UBFM W8,W19,#25,#24.
    return 0x53000000 | (25 << 16) | (24 << 10) | (19 << 5) | 8

def a64_add_w0_w8_imm(imm: int) -> int:
    check(0 <= imm <= 4095, "ADD immediate out of range")
    return 0x11000000 | (imm << 10) | (8 << 5)

def extract_pinned_common_offset_map(code: bytes) -> tuple[tuple[int,int],...]:
    # Offsets into __text of the verified iOS 15.8.8/19H422 N71 binary.
    # No original Apple code is embedded in this source. These checks
    # validate generic AArch64 instructions and bounded jump-table data.
    check(0x8a4 <= len(code) < 0x100000,
          "Unsupported S8000 code length for pinned audit")
    # Two method arguments are copied to persistent port/reg-id registers.
    check(word(code, 0x7e8) == 0xaa0203f3 and
          word(code, 0x7ec) == 0xaa0103f4,
          "Cannot verify port and register-ID argument ownership")
    # The function calls getPortCount(), then bounds-checks the port,
    # and separately constrains register IDs to 0..5.
    check((word(code,0x7f0) & 0xfc000000) == 0x94000000,
          "Missing port-count query")
    check(word(code,0x7f4) == 0x6b13001f and
          (word(code,0x7f8) & 0xff00001f) == 0x54000009,
          "Port index bounds guard not verified")
    check(word(code,0x7fc) == 0x7100169f and
          (word(code,0x800) & 0xff00001f) == 0x54000008,
          "Register-ID bounds guard not verified")
    check(word(code,0x804) == a64_movz_w0(0x24),
          "Shared offset zero changed")
    check(word(code,0x808) == 0x2a1403e8,
          "Register switch selector not verified")
    # Bound the exact original jump-table decoding shape and base.
    for offset, ins in {
       0x80c: 0x90000009, 0x810: 0x91223129,
       0x814: 0x1000000a, 0x818: 0xb8a8792b,
       0x81c: 0x8b0b014a, 0x820: 0xd61f0140,
    }.items():
        check(word(code,offset) == ins,
              "A9 jump-table construction is not verified")
    expected_targets=(0x858,0x824,0x82c,0x838,0x844,0x850)
    jumps=struct.unpack_from("<6i",code,0x88c)
    targets=tuple(0x814 + offset for offset in jumps)
    check(targets == expected_targets,
          "A9 register-ID jump-table destinations changed")
    check(word(code,0x824) == a64_movz_w0(0x2c),
          "Shared offset one changed")
    bases=(0x100,0x114,0x124,0x12c)
    for target,base in zip(expected_targets[2:],bases):
        check(word(code,target) == a64_lsl_w8_w19_7(),
              "Port stride or index source changed")
        check(word(code,target+4) == a64_add_w0_w8_imm(base),
              "Port-relative register base changed")
        if target != 0x850:
            check((word(code,target+8) & 0xfc000000) == 0x14000000,
                  "Port-relative case does not join common return")
    check(word(code,0x864) == 0xd65f03c0,
          "Common method epilogue not verified")
    # (base, stride) for each bounded register ID, where stride 0
    # explicitly identifies shared/global offsets.
    return ((0x24,0),(0x2c,0),
            (0x100,0x80),(0x114,0x80),
            (0x124,0x80),(0x12c,0x80))

def inspect_macho(data: bytes) -> tuple[tuple[int,int],...]:
    check(0 < len(data) <= KMAP.MAX_MACHO, "Private image length rejected")
    outer=KMAP.macho_segments(data,0)
    for needed in ("__PRELINK_INFO","__PRELINK_TEXT","__PLK_TEXT_EXEC"):
        check(needed in outer, "Prelinked segment missing")
    info=outer["__PRELINK_INFO"]
    check(info["offset"]+info["filesize"]<=len(data),
          "Metadata exceeds input")
    meta=KMAP.kext_metadata(
        data[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0"))
    load,size=meta[A9]
    pre=outer["__PRELINK_TEXT"]
    check(load>=pre["vm"] and load-pre["vm"]+size<=pre["filesize"],
          "A9 KEXT header outside PRELINK_TEXT")
    nested=KMAP.macho_segments(data,pre["offset"]+load-pre["vm"])
    sections=nested.get("__TEXT_EXEC",{}).get("sections",{})
    sec=sections.get("__text")
    check(sec is not None and sec["size"] == 2928,
          "Not the pinned A9 specialized executable section")
    ex=outer["__PLK_TEXT_EXEC"]
    check(sec["vm"]>=ex["vm"] and
          sec["vm"]-ex["vm"]+sec["size"]<=ex["filesize"],
          "A9 executable outside prelinked code")
    off=ex["offset"]+sec["vm"]-ex["vm"]
    return extract_pinned_common_offset_map(data[off:off+sec["size"]])

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_macho",type=Path)
    args=p.parse_args()
    try:
        check(0 < args.private_macho.stat().st_size <= KMAP.MAX_MACHO,
              "Input file too large")
        mappings=inspect_macho(args.private_macho.read_bytes())
    except (OSError,UnverifiedCode,KMAP.BadKernelcache,
            struct.error,UnicodeError,KeyError) as exc:
        print("A9_COMMON_REG_AUDIT_BLOCKED:",str(exc),file=sys.stderr)
        return 1
    print("S8000_COMMON_REG_OFFSET_MAP_PASS: original pinned ARM64 selector verified")
    for index,(base,stride) in enumerate(mappings):
        print("REG_ID",index,"BASE_OFFSET",hex(base),
              "PORT_STRIDE",hex(stride),
              "PORT1_OFFSET",hex(base+stride))
    print("HARDWARE_BLOCKED: offsets are relative; controller MMIO base, "
          "register roles, reset/clock semantics, and DMA isolation UNVERIFIED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
