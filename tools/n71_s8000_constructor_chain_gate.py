#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline AppleS8000PCIePort -> S800xPCIePort -> EmbeddedPCIePort constructor audit.

A read-only, version-pinned study of a locally obtained original A9 N71
ARM64 prelinked Mach-O. Does not export Apple code, private addresses,
firmware, memory-register values, credentials, or interact with hardware.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "a9_ctor_kexts", HERE / "n71_kernelcache_pcie_kext_map.py")
assert spec and spec.loader
KMAP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(KMAP)

MODS = {
    "embedded": "com.apple.driver.AppleEmbeddedPCIE",
    "shared": "com.apple.driver.AppleS800xPCIe",
    "a9": "com.apple.driver.AppleS8000PCIe",
}
TEXT_LENGTHS = {"embedded": 46924, "shared": 18552, "a9": 2928}
CTOR = {"embedded": 0x4880, "shared": 0x8D0, "a9": 0x38}
CTOR_VPTR_ADRP = {"embedded": 0x488C, "shared": 0x8DC, "a9": 0x44}
EXPECTED_CHANGED = (0, 8, 56, 1816)
VIRTUAL_CHECK_BYTES = 2048

class UnqualifiedHardware(ValueError):
    pass

def need(ok: bool, reason: str) -> None:
    if not ok:
        raise UnqualifiedHardware(reason)

def sign(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value

def w(code: bytes, at: int) -> int:
    need(0 <= at <= len(code) - 4 and at % 4 == 0,
         "ARM64 code out of bounds")
    return struct.unpack_from("<I", code, at)[0]

def bl_destination(pc: int, insn: int) -> int:
    need(insn & 0xFC000000 == 0x94000000,
         "Constructor parent call is not BL")
    return pc + sign(insn & 0x3FFFFFF, 26) * 4

def adrp_target(pc: int, insn: int, reg: int) -> int:
    need(insn & 0x9F00001F == (0x90000000 | reg),
         "Unexpected ADRP opcode or destination register")
    bits = (((insn >> 5) & 0x7FFFF) << 2) | ((insn >> 29) & 3)
    return (pc & ~4095) + sign(bits, 21) * 4096

def adrp_add_str_vptr(pc: int, adrp: int, add: int,
                     store: int) -> int:
    # Generic AArch64 ADRP x8; ADD x8,x8,#imm; STR x8,[x0].
    base = adrp_target(pc, adrp, 8)
    need(add & 0xFFC003FF == 0x91000108 and
         store == 0xF9000008,
         "Expected instance vtable assignment not present")
    need((add >> 22) & 3 in (0, 1), "Unexpected ADD shift")
    shift = 12 if (add >> 22) & 3 else 0
    addr = base + (((add >> 10) & 0xFFF) << shift)
    need(addr > 0 and addr % 8 == 0, "Malformed instance vtable")
    return addr

def read_data_pointer(blob: bytes, main: dict, addr: int) -> int:
    d = main.get("__PLK_DATA_CONST")
    need(d is not None and d["vm"] <= addr and
         addr + 8 <= d["vm"] + d["filesize"],
         "Pointer outside original read-only constant segment")
    at = d["offset"] + addr - d["vm"]
    need(at + 8 <= len(blob), "Original data pointer truncated")
    return struct.unpack_from("<Q", blob, at)[0]

def ctor_stub_callee(blob: bytes, main: dict, nested: dict,
                     caller_pc: int, caller_word: int) -> int:
    target = bl_destination(caller_pc, caller_word)
    stubs = nested["__TEXT_EXEC"]["sections"]["__stubs"]
    got = nested["__DATA_CONST"]["sections"]["__got"]
    need(stubs["vm"] <= target <= stubs["vm"] + stubs["size"] - 12,
         "Parent constructor BL does not target a bounded KEXT stub")
    ex = main["__PLK_TEXT_EXEC"]
    need(ex["vm"] <= target and
         target + 12 <= ex["vm"] + ex["filesize"],
         "Trampoline outside main prelinked executable")
    at = ex["offset"] + target - ex["vm"]
    adrp, ldr, br = struct.unpack_from("<3I", blob, at)
    need(ldr & 0xFFC003FF == 0xF9400210 and
         br == 0xD61F0200,
         "Unexpected ARM64 indirect-call stub")
    base = adrp_target(target, adrp, 16)
    slot = base + (((ldr >> 10) & 0xFFF) * 8)
    need(got["vm"] <= slot and slot + 8 <= got["vm"] + got["size"],
         "Constructor trampoline GOT outside owning module")
    result = read_data_pointer(blob, main, slot)
    return result

def vtable_differences(blob: bytes, main: dict, old: int,
                       new: int, length: int = VIRTUAL_CHECK_BYTES) -> list[int]:
    need(length > 0 and length <= 4096 and length % 8 == 0,
         "Unsafe vtable comparison length")
    changed = []
    for slot in range(0, length, 8):
        if read_data_pointer(blob, main, old + slot) != (
                read_data_pointer(blob, main, new + slot)):
            changed.append(slot)
    return changed

def port3_check(code: bytes, off: int = 0x27C) -> None:
    """Check original A9 special path is gated on two comparisons with 3."""
    expected = {
        0x288: 0xAA0003F3,   # retain controller object
        0x29C: 0x71000C1F,   # CMP W0,#3
        0x2A0: 0x54000081,   # B.NE to common fallback
        0x2A4: 0xB940AA68,   # controller port index
        0x2A8: 0x71000D1F,   # CMP W8,#3
        0x2AC: 0x54000100,   # B.EQ to special path
        0x2B8: 0xF9439501,   # inherited target from parent table
        0x2BC: 0xAA1303E0,   # pass controller/self
        0x2C8: 0xD61F0020,   # tail-branch to inherited target
    }
    need(off == 0x27C, "Unexpected specialized method entry")
    for at, value in expected.items():
        need(w(code, at) == value,
             "A9 port3-gated shared-method fallback changed")

def static_inherited_fallback(blob: bytes, main: dict,
                              code: bytes, code_vm: int,
                              parent_vptr: int) -> bool:
    """Validate indirect fallback resolves to SAME parent virtual method."""
    port3_check(code)
    adrp = w(code, 0x2B0)
    ldr = w(code, 0x2B4)
    need(ldr & 0xFFC003FF == 0xF9400108,
         "Unexpected parent-table reference LDR")
    indirect_data_addr = adrp_target(code_vm + 0x2B0, adrp, 8)
    indirect_data_addr += ((ldr >> 10) & 0xFFF) * 8
    parent_table_header = read_data_pointer(blob, main, indirect_data_addr)
    need(parent_table_header + 16 == parent_vptr,
         "A9 fallback is not based on original inherited class vtable")
    target = read_data_pointer(blob, main, parent_table_header + 1832)
    need(target == read_data_pointer(blob, main, parent_vptr + 1816),
         "A9 fallback does not resolve original inherited method")
    return True

def audit(blob: bytes) -> dict:
    need(1000 < len(blob) <= KMAP.MAX_MACHO,
         "Original prelinked Mach-O size outside bounds")
    main = KMAP.macho_segments(blob, 0)
    for name in ("__PRELINK_TEXT", "__PRELINK_INFO",
                 "__PLK_TEXT_EXEC", "__PLK_DATA_CONST"):
        need(name in main, "Missing original prelinked region")
    info = main["__PRELINK_INFO"]
    need(info["offset"] + info["filesize"] <= len(blob),
         "Prelink XML truncated")
    meta = KMAP.kext_metadata(
        blob[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0"))
    pre = main["__PRELINK_TEXT"]
    exe = main["__PLK_TEXT_EXEC"]
    modules = {}
    for label, ident in MODS.items():
        va, size = meta[ident]
        need(pre["vm"] <= va and va - pre["vm"] + size <= pre["filesize"],
             "Original KEXT Mach-O header outside prelink text")
        nested = KMAP.macho_segments(blob, pre["offset"] + va - pre["vm"])
        sec = nested["__TEXT_EXEC"]["sections"]["__text"]
        need(sec["size"] == TEXT_LENGTHS[label] and
             exe["vm"] <= sec["vm"] and
             sec["vm"] + sec["size"] <= exe["vm"] + exe["filesize"],
             "Unexpected original A9 code extent")
        codeoff = exe["offset"] + sec["vm"] - exe["vm"]
        code = blob[codeoff:codeoff+sec["size"]]
        at = CTOR_VPTR_ADRP[label]
        addr = adrp_add_str_vptr(
            sec["vm"] + at, w(code, at),
            w(code, at+4), w(code, at+8))
        need(main["__PLK_DATA_CONST"]["vm"] <= addr,
             "Constructor vtable pointer outside prelinked constant data")
        modules[label] = {
            "nested": nested, "code": code,
            "code_vm": sec["vm"], "vptr": addr}
    a9, shared, base = (modules[x] for x in ("a9", "shared", "embedded"))
    a9_ctor_parent = ctor_stub_callee(
        blob, main, a9["nested"], a9["code_vm"]+0x40,
        w(a9["code"],0x40))
    shared_ctor_parent = ctor_stub_callee(
        blob, main, shared["nested"], shared["code_vm"]+0x8D8,
        w(shared["code"],0x8D8))
    need(a9_ctor_parent == shared["code_vm"] + CTOR["shared"],
         "A9 constructor does not delegate to reviewed S800x constructor")
    need(shared_ctor_parent == base["code_vm"] + CTOR["embedded"],
         "S800x constructor does not delegate to reviewed embedded constructor")
    diff_a9 = vtable_differences(
        blob, main, shared["vptr"], a9["vptr"])
    need(tuple(diff_a9) == EXPECTED_CHANGED,
         "A9 derived-instance vtable change set is not verified")
    parent_method = read_data_pointer(blob, main, shared["vptr"]+1816)
    override_method = read_data_pointer(blob, main, a9["vptr"]+1816)
    need(parent_method == shared["code_vm"]+0x121C,
         "S800x inherited method virtual target changed")
    need(override_method == a9["code_vm"]+0x27C,
         "S8000 only board-specific method virtual target changed")
    need(static_inherited_fallback(
        blob, main, a9["code"], a9["code_vm"], shared["vptr"]),
        "Port-3 branch not proven to delegate to shared method")
    # The old inherited-start method belongs to a DIFFERENT constructor
    # vtable, not to the verified three-constructor chain.
    other_entry = base["code_vm"] + 0x1A58
    need(other_entry not in (
         read_data_pointer(blob, main, a9["vptr"]+688),
         read_data_pointer(blob, main, shared["vptr"]+688)),
         "Unexpected inherited-start target in derived vtable")
    return {
        "constructor_chain": ("embedded", "shared", "a9"),
        "a9_changed_vtable_slots": tuple(diff_a9),
        "a9_static_port3_branch": True,
        "non_port3_parent_method_fallback": True,
        "runtime_execution_proven": False,
        "mmio_or_dart_validated": False,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_decompressed_macho", type=Path)
    args = parser.parse_args()
    try:
        need(0 < args.private_decompressed_macho.stat().st_size <= (
            KMAP.MAX_MACHO), "Input too large")
        result = audit(args.private_decompressed_macho.read_bytes())
    except (OSError, UnqualifiedHardware, KMAP.BadKernelcache,
            struct.error, UnicodeError, KeyError) as exc:
        print("N71_CONSTRUCTOR_CHAIN_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_S8000_CONSTRUCTOR_CHAIN_STATIC_PASS")
    print("PORT_CLASS_CONSTRUCTOR_CHAIN",
          "AppleEmbeddedPCIEPort > AppleS800xPCIePort > AppleS8000PCIePort")
    print("A9_PORT_VTABLE_CHANGED_SLOTS", ",".join(
        str(v) for v in result["a9_changed_vtable_slots"]))
    print("A9_NON_PORT3_SHARED_METHOD_FALLBACK=VERIFIED_STATIC")
    print("THIS_IS_PORT_CLASS_NOT_ROOT_CONTROLLER=YES")
    print("EMBEDDED_ROOT_START_NOT_IN_PORT_CLASS_CHAIN")
    print("RUNTIME_PCIE_INIT_AND_WLAN_ASSOCIATION_PROVEN=NO")
    print("HARDWARE_BLOCKED: MMIO physical base, port1 reset, DART SID/DMA")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
