#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Provenance-gated original N71 IONVMeFamily Read-command ARM64 audit.

Reads only the owner-held original kernelcache; never uploads or publishes
the executable, hardware addresses, device IDs, data pages, or NAND content.
The selected source checks establish READ opcode/CDW layout and conditional
request options. They DO NOT establish Apple's S8000 transport BIT(5),
NVMMU I/O descriptor acceptance, hardware queue setup, or DMA retirement.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import n71_s8000_constructor_chain_gate as GATE

BUNDLE = "com.apple.iokit.IONVMeFamily"
VERSION = "2.1.0"
EXPECTED_TEXT_SIZE = 272392
EXPECTED_TEXT_SHA256 = "c836ce15c7254b5b0d13ddbd9371b44935c180d21ae2e87e8a82f989df3a4fd0"
EXPECTED_KEXT_MACHO_SIZE = 0xF6C0

# Selected, independently inspected exact instruction locations from the
# original prelinked IONVMeFamily __TEXT_EXEC.__text (NOT __TEXT.__cstring).
# No Apple source or executable payload is distributed in this repository.
READ_WIRE_PROVENANCE = {
    0x36164: 0x79416008,  # existing command-id input
    0x36178: 0x321F0148,  # ORR READ opcode 0x02 into CDW0
    0x3617C: 0xB9011808,  # CDW0 store (request object offset +280)
    0x36180: 0xB9011C01,  # NSID store (+284)
    0x36184: 0xF900A002,  # 64-bit starting LBA store (+320 / CDW10-11)
    0x36194: 0xB9014808,  # CDW12 store (+328)
    0x361A4: 0xB9014C08,  # CDW13 store (+332)
    0x363B4: 0xA9418E82,  # source request 64-bit LBA / block fields
    0x363C4: 0x97FFFF5E,  # call the same original READ command builder
    0x363E8: 0x52808008,  # optional request-dependent CDW0 mask 0x400
    0x363EC: 0x52810009,  # optional request-dependent CDW0 mask 0x800
    0x363F0: 0x1A880128,  # select request-dependent CDW0 mask
    0x363FC: 0xB9011AA8,  # OR selected request option into CDW0
    0x3652C: 0xF0FF8557,  # diagnostic string for BuildCommandReadStruct
    0x36530: 0x913B1AF7,  # xref low offset of original method name
}


class RejectedOriginalNVMeSource(ValueError):
    pass


def verify_read_words(code: bytes) -> None:
    if len(code) != EXPECTED_TEXT_SIZE:
        raise RejectedOriginalNVMeSource("Invalid IONVMeFamily text extent")
    for offset, opcode in READ_WIRE_PROVENANCE.items():
        if struct.unpack_from("<I", code, offset)[0] != opcode:
            raise RejectedOriginalNVMeSource("Read command source instruction differs")


def verify_true_original_text(code: bytes) -> None:
    verify_read_words(code)
    if hashlib.sha256(code).hexdigest() != EXPECTED_TEXT_SHA256:
        raise RejectedOriginalNVMeSource("Original IONVMeFamily source fingerprint differs")


def extract_original_ionvme(kernelcache: bytes) -> tuple[bytes, bytes]:
    main = GATE.KMAP.macho_segments(kernelcache, 0)
    pre = main["__PRELINK_TEXT"]
    info = main["__PRELINK_INFO"]
    executable = main["__PLK_TEXT_EXEC"]
    raw = kernelcache[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0")
    if not raw.startswith(b"<dict>"):
        raise RejectedOriginalNVMeSource("Invalid kernelcache prelink metadata")
    root = ET.fromstring(b'<plist version="1.0">'+raw+b'</plist>')
    matches = []
    for node in root.iter("dict"):
        kv = GATE.KMAP.pairs(node)
        name = kv.get("CFBundleIdentifier")
        if name is None or name.text != BUNDLE:
            continue
        load = kv.get("_PrelinkExecutableLoadAddr")
        size = kv.get("_PrelinkExecutableSize")
        version = kv.get("CFBundleVersion")
        if load is not None and size is not None:
            if version is None or version.text != VERSION:
                raise RejectedOriginalNVMeSource("Unexpected original IONVMeFamily version")
            matches.append((int(load.text, 0), int(size.text, 0)))
    if len(matches) != 1:
        raise RejectedOriginalNVMeSource("Expected one original prelinked IONVMeFamily")
    load, size = matches[0]
    if size != EXPECTED_KEXT_MACHO_SIZE or not (
        pre["vm"] <= load and load - pre["vm"] + size <= pre["filesize"]
    ):
        raise RejectedOriginalNVMeSource("Unexpected IONVMeFamily prelink boundary")
    nested_file_offset = pre["offset"] + (load - pre["vm"])
    nested = GATE.KMAP.macho_segments(kernelcache, nested_file_offset)
    text = nested["__TEXT_EXEC"]["sections"]["__text"]
    cstring = nested["__TEXT"]["sections"]["__cstring"]
    if text["size"] != EXPECTED_TEXT_SIZE:
        raise RejectedOriginalNVMeSource("IONVMeFamily code section size differs")
    code_offset = executable["offset"] + text["vm"] - executable["vm"]
    cstr_offset = pre["offset"] + cstring["vm"] - pre["vm"]
    code = kernelcache[code_offset:code_offset+text["size"]]
    literals = kernelcache[cstr_offset:cstr_offset+cstring["size"]]
    if len(code) != text["size"] or len(literals) != cstring["size"]:
        raise RejectedOriginalNVMeSource("Truncated original IONVMeFamily sections")
    for marker in (b"AppleNVMeRequest::BuildCommandReadStruct",
                   b"AppleNVMeRequest::BuildCommandWriteStruct",
                   b"IONVMeController::WaitForOutstandingCommands"):
        if marker not in literals:
            raise RejectedOriginalNVMeSource("Expected IONVMeFamily method absent")
    verify_true_original_text(code)
    return code, literals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner_private_original_kernelcache", type=Path)
    args = parser.parse_args()
    try:
        extract_original_ionvme(args.owner_private_original_kernelcache.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, OverflowError,
            ET.ParseError, struct.error):
        print("N71_IONVME_ORIGINAL_READ_SOURCE_GATE=REJECTED")
        return 1
    print("N71_IONVME_ORIGINAL_READ_SOURCE_GATE=PASS")
    print("ORIGINAL_DRIVER=IONVMeFamily_2.1.0")
    print("PROVEN_READ_OPCODE=0x02")
    print("PROVEN_READ_CDW_FIELDS=0,1,10,11,12,13")
    print("ORIGINAL_OPTIONAL_REQUEST_CDW0_BITS_10_11=OBSERVED")
    print("FLATDMA_TRANSPORT_BIT5_FOR_NVM_READ=UNVERIFIED")
    print("DMA_DRAIN_OR_NAND_READ_PROVEN=NO")
    print("PRIVATE_FIRMWARE_OR_USER_DATA_PUBLISHED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
