#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Owner-original N71 IONVMeFamily constructor/vtable return-value alternatives.

Authenticated original firmware only; never conclude which class is
instantiated on a live N71 from prelinked class presence alone. No phone IO.
"""
import argparse
from pathlib import Path
import struct

import n71_s8000_constructor_chain_gate as CTOR
import n71_s8000_original_ionvme_read_source_gate as READ

# Constructor-derived static alternatives for the virtual pool method at
# byte offset 1440, independently of any active controller binding.
BASE_VPTR_SETTER = 0x246D8
DERIVED_VPTR_SETTER = 0x31164
DERIVED_PARENT_BL = 0x31160
DERIVED_PARENT_TARGET = 0x246AC
METHOD_OFFSET = 1440
CHOICE_OFFSET = 1448
# Private source-derived code offsets relative to IONVMeFamily __text.
BASE_METHOD_OFFSET = 0x26F08
BASE_CHOICE_OFFSET = 0x26F00
DERIVED_METHOD_OFFSET = 0x31384
DERIVED_CHOICE_OFFSET = 0x3137C
RET0 = (0x52800000, 0xD65F03C0)
RET1 = (0x52800020, 0xD65F03C0)
ORIGINAL_VTABLE_SOURCE_WORDS = {
    0x246D8: 0x900033E8,
    0x246DC: 0x91162108,
    0x246E0: 0xF9000008,
    0x31160: 0x97FFCD53,
    0x31164: 0x90003388,
    0x31168: 0x9104E108,
    0x3116C: 0xF9000008,
    0x26F00: 0x52800000,
    0x26F04: 0xD65F03C0,
    0x26F08: 0x52800000,
    0x26F0C: 0xD65F03C0,
    0x3137C: 0x52800020,
    0x31380: 0xD65F03C0,
    0x31384: 0x52800020,
    0x31388: 0xD65F03C0,
}


def verify_original_vptr_instruction_words(code: bytes) -> None:
    if len(code) != READ.EXPECTED_TEXT_SIZE:
        raise ValueError("Unexpected original IONVMe executable extent")
    for at, word in ORIGINAL_VTABLE_SOURCE_WORDS.items():
        if struct.unpack_from("<I", code, at)[0] != word:
            raise ValueError("Original controller-vtable source instruction differs")


def verify_original_vtable_choices(kernelcache: bytes) -> dict[str, int]:
    code, _ = READ.extract_original_ionvme(kernelcache)
    verify_original_vptr_instruction_words(code)
    main = CTOR.KMAP.macho_segments(kernelcache, 0)
    pre = main["__PRELINK_TEXT"]
    info = main["__PRELINK_INFO"]
    raw = kernelcache[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0")
    root = READ.ET.fromstring(b'<plist version="1.0">' + raw + b'</plist>')
    loads = []
    for node in root.iter("dict"):
        kv = CTOR.KMAP.pairs(node)
        bundle = kv.get("CFBundleIdentifier")
        load_node = kv.get("_PrelinkExecutableLoadAddr")
        if bundle is not None and bundle.text == READ.BUNDLE and load_node is not None:
            loads.append(int(load_node.text, 0))
    if len(loads) != 1:
        raise ValueError("Exactly one original IONVMeFamily preload required")
    load = loads[0]
    nested = CTOR.KMAP.macho_segments(
        kernelcache, pre["offset"] + load - pre["vm"])
    code_base = nested["__TEXT_EXEC"]["sections"]["__text"]["vm"]
    const = nested["__DATA_CONST"]["sections"]["__const"]

    if CTOR.bl_destination(
        code_base + DERIVED_PARENT_BL,
        struct.unpack_from("<I", code, DERIVED_PARENT_BL)[0]
    ) != code_base + DERIVED_PARENT_TARGET:
        raise ValueError("Derived constructor parent link not verified")

    table = {}
    for name, at, expected_method, expected_choice, ret in (
        ("base", BASE_VPTR_SETTER, BASE_METHOD_OFFSET, BASE_CHOICE_OFFSET, RET0),
        ("derived", DERIVED_VPTR_SETTER, DERIVED_METHOD_OFFSET,
         DERIVED_CHOICE_OFFSET, RET1),
    ):
        vptr = CTOR.adrp_add_str_vptr(
            code_base + at,
            *struct.unpack_from("<3I", code, at)
        )
        if not (
            const["vm"] <= vptr and
            vptr + CHOICE_OFFSET + 8 <= const["vm"] + const["size"]
        ):
            raise ValueError("Original class vtable outside owning constant range")
        method = CTOR.read_data_pointer(kernelcache, main, vptr + METHOD_OFFSET)
        choice = CTOR.read_data_pointer(kernelcache, main, vptr + CHOICE_OFFSET)
        if method != code_base + expected_method or choice != code_base + expected_choice:
            raise ValueError("Original controller vtable slot differs")
        for code_offset in (expected_method, expected_choice):
            if tuple(struct.unpack_from("<2I", code, code_offset)) != ret:
                raise ValueError("Original controller return-code pattern changed")
        table[name] = ret[0] >> 5 & 1
    if table != {"base": 0, "derived": 1}:
        raise ValueError("Unexpected original vtable behavior")
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner_private_original_n71_kernelcache", type=Path)
    args = parser.parse_args()
    try:
        choices = verify_original_vtable_choices(
            args.owner_private_original_n71_kernelcache.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        print("N71_ORIGINAL_IONVME_VTABLE1440_ALTERNATIVES=REJECTED")
        return 1
    print("N71_ORIGINAL_IONVME_VTABLE1440_ALTERNATIVES=PASS")
    print(f"ORIGINAL_BASE_CLASS_METHOD1440_RETURN={choices['base']}")
    print(f"ORIGINAL_DERIVED_CLASS_METHOD1440_RETURN={choices['derived']}")
    print("ORIGINAL_DERIVED_CONSTRUCTOR_PARENT_LINK=PROVEN")
    print("ACTIVE_N71_CONTROLLER_DYNAMIC_CLASS=UNVERIFIED")
    print("ACTIVE_N71_CONTROLLER_VTABLE1440_RETURN=UNVERIFIED")
    print("NAND_IO_OR_DMA_QUALIFIED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
