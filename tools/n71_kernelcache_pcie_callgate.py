#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, aggregate AArch64 PCIe KEXT call classification.

Analyze locally supplied, decompressed A9 kernelcache Mach-O. Do not output,
copy or write Apple executable bytes, call targets, offsets or disassembly.
This static branch graph does NOT prove a safe PCIe initialization sequence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
from pathlib import Path
import struct
import sys

MAPPER_PATH = Path(__file__).resolve().with_name("n71_kernelcache_pcie_kext_map.py")
spec = importlib.util.spec_from_file_location("n71_private_kext_map", MAPPER_PATH)
assert spec and spec.loader
KMAP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(KMAP)

A9 = "com.apple.driver.AppleS8000PCIe"
SHARED = "com.apple.driver.AppleS800xPCIe"
EMBEDDED = "com.apple.driver.AppleEmbeddedPCIE"
IOPCI = "com.apple.iokit.IOPCIFamily"
CATEGORIES = {
    A9: "a9_self",
    SHARED: "a9_s800x_shared",
    EMBEDDED: "apple_embedded_pcie",
    IOPCI: "io_pci_family",
}
EXEC_SEGMENTS = frozenset({"__TEXT_EXEC", "__PLK_TEXT_EXEC"})


class RejectedGraph(ValueError):
    pass


def guard(ok: bool, message: str) -> None:
    if not ok:
        raise RejectedGraph(message)


def signed(n: int, bits: int) -> int:
    return n - (1 << bits) if n & (1 << (bits - 1)) else n


def bl_destination(pc: int, insn: int) -> int | None:
    if insn & 0xFC000000 != 0x94000000:
        return None
    return pc + signed(insn & 0x03FFFFFF, 26) * 4


def stub_got_address(pc: int, adrp: int, ldr: int, br: int) -> int:
    """Validate AArch64 ADRP x16; LDR x16,[x16,#imm]; BR x16."""
    guard(adrp & 0x9F00001F == 0x90000010, "Unexpected stub ADRP")
    guard(ldr & 0xFFC003FF == 0xF9400210, "Unexpected stub LDR")
    guard(br == 0xD61F0200, "Unexpected stub BR")
    immlo = (adrp >> 29) & 3
    immhi = (adrp >> 5) & 0x7FFFF
    displacement = signed((immhi << 2) | immlo, 21) << 12
    base = (pc & ~4095) + displacement
    address = base + ((ldr >> 10) & 0xFFF) * 8
    guard(address >= 0 and address % 8 == 0, "Invalid stub GOT address")
    return address


def file_offset(main: dict, name: str, address: int, size: int, n: int) -> int:
    seg = main.get(name)
    guard(seg is not None, "Missing coalesced segment")
    guard(size >= 0 and address >= seg["vm"], "Segment address underflow")
    delta = address - seg["vm"]
    guard(delta + size <= seg["filesize"], "Section outside mapped segment")
    offset = seg["offset"] + delta
    guard(offset + size <= n, "Section outside file")
    return offset


def target_category(address: int, extents: list[tuple[str, int, int]],
                    main: dict) -> str:
    for name, begin, size in extents:
        if begin <= address < begin + size:
            return CATEGORIES[name]
    if any(seg in main and main[seg]["vm"] <= address <
           main[seg]["vm"] + main[seg]["filesize"]
           for seg in EXEC_SEGMENTS):
        return "other_kernel_or_kext"
    raise RejectedGraph("Resolved GOT target outside known executable segments")


def summarize_kernelcache(blob: bytes) -> dict[str, object]:
    guard(0 < len(blob) <= KMAP.MAX_MACHO, "Input size outside allowed range")
    main = KMAP.macho_segments(blob, 0)
    extents = KMAP.map_pcie_kexts(blob)
    info = main["__PRELINK_INFO"]
    off = file_offset(main, "__PRELINK_INFO", info["vm"], info["filesize"], len(blob))
    metadata = KMAP.kext_metadata(blob[off:off + info["filesize"]].rstrip(b"\0"))
    prelink = main["__PRELINK_TEXT"]
    load, expected_len = metadata[A9]
    kext_off = file_offset(main, "__PRELINK_TEXT", load, expected_len, len(blob))
    kext = KMAP.macho_segments(blob, kext_off)
    guard(kext["__TEXT"]["filesize"] == expected_len, "Wrong nested KEXT length")
    code_sec = kext.get("__TEXT_EXEC", {}).get("sections", {})
    data_sec = kext.get("__DATA_CONST", {}).get("sections", {})
    code, stubs, got = (code_sec.get("__text"),
                        code_sec.get("__stubs"),
                        data_sec.get("__got"))
    guard(code is not None and stubs is not None and got is not None,
          "Specialized driver missing __text/__stubs/__got")
    guard(0 < code["size"] < 1_000_000 and code["size"] % 4 == 0,
          "Bad A9 instruction section size")
    guard(0 < stubs["size"] <= 8192 and stubs["size"] % 12 == 0,
          "Bad A9 stub section size")
    guard(0 < got["size"] <= 8192 and got["size"] % 8 == 0,
          "Bad A9 GOT section size")
    inst_base = file_offset(main, "__PLK_TEXT_EXEC",
                            code["vm"], code["size"], len(blob))
    stub_base = file_offset(main, "__PLK_TEXT_EXEC",
                            stubs["vm"], stubs["size"], len(blob))
    got_base = file_offset(main, "__PLK_DATA_CONST",
                           got["vm"], got["size"], len(blob))
    translated: dict[int, str] = {}
    for idx in range(stubs["size"] // 12):
        pc = stubs["vm"] + idx * 12
        adrp, ldr, br = struct.unpack_from("<3I", blob, stub_base + idx * 12)
        slot = stub_got_address(pc, adrp, ldr, br)
        guard(got["vm"] <= slot and slot + 8 <= got["vm"] + got["size"],
              "External call does not resolve inside this KEXT's GOT")
        pointer = struct.unpack_from("<Q", blob, got_base + slot - got["vm"])[0]
        translated[pc] = target_category(pointer, extents, main)
    counts: Counter[str] = Counter()
    used_stubs = set()
    for i in range(0, code["size"], 4):
        pc = code["vm"] + i
        insn = struct.unpack_from("<I", blob, inst_base + i)[0]
        dest = bl_destination(pc, insn)
        if dest is None:
            continue
        if code["vm"] <= dest < code["vm"] + code["size"]:
            counts["a9_self"] += 1
        elif dest in translated:
            used_stubs.add(dest)
            counts[translated[dest]] += 1
        else:
            raise RejectedGraph("BL outside private A9 code and known stubs")
    guard(sum(counts.values()) > 0, "No A9 direct BL calls found")
    return {
        "direct_branch_calls": sum(counts.values()),
        "stub_count": len(translated),
        "used_stubs": len(used_stubs),
        "calls": {name: counts[name] for name in (
            "a9_self", "a9_s800x_shared", "apple_embedded_pcie",
            "io_pci_family", "other_kernel_or_kext")},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_kernelcache_macho", type=Path)
    args = p.parse_args()
    try:
        guard(args.private_kernelcache_macho.stat().st_size <= KMAP.MAX_MACHO,
              "Input file too large")
        report = summarize_kernelcache(args.private_kernelcache_macho.read_bytes())
    except (OSError, RejectedGraph, KMAP.BadKernelcache,
            UnicodeError, ValueError, struct.error, KeyError) as exc:
        print("A9_PCIE_CALLGATE_FAIL_CLOSED:", str(exc), file=sys.stderr)
        return 1
    print("A9_PCIE_CALLGATE_PASS: static ARM64 branch/stub/GOT classification only")
    print("DIRECT_BRANCH_CALLS", report["direct_branch_calls"])
    print("TRAMPOLINES", report["stub_count"],
          "USED_TRAMPOLINES", report["used_stubs"])
    for name, count in report["calls"].items():
        print("CALL_GROUP", name, count)
    print("HARDWARE_BLOCKED: register semantics, DMA context, IRQ and link "
          "startup remain unverified; no code or addresses exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
