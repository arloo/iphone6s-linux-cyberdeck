#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authentic original N71 IONVMeFamily READ -> IOVM/PRP control-flow gate.

This only establishes the original Apple READ request construction path:
the embedded block-device handler chooses the READ builder, then requests
IOVM/PRP segments and forwards the request to a controller-level routine.
It does NOT establish that generic PRP1 or our candidate tag1 is safe on
the S8000 ANS physical interface; no device/NAND command is authorized.
"""
import argparse
from pathlib import Path
import struct

import n71_s8000_original_ionvme_read_source_gate as READ

# All offsets are relative to the genuine prelinked IONVMeFamily
# __TEXT_EXEC.__text, independently authenticated by READ's whole-section
# SHA-256. Only instruction fingerprints and control-flow *metadata*
# enter Git, never the owner-private executable.
PROVENANCE_WORDS = {
    0x13240: 0x71000B5F,  # compare selected command kind to READ selector 2
    0x13244: 0x54000061,  # non-READ alternative branch
    0x13248: 0x94008CDB,  # call READ command request builder
    0x13250: 0x94008C50,  # separate alternate builder; not a read proof
    0x132AC: 0x94008A4C,  # call GenerateIOVMSegments wrapper
    0x132C8: 0x940069B6,  # controller-level request bookkeeping
    0x35BF0: 0xA90C8801,  # hand segment offset and transfer length to request
    0x35BF4: 0x97FFFE70,  # call core IOVM/PRP generator
    0x355F0: 0x940034F8,  # delegate to source memory-mapping method
    0x355FC: 0xF140043F,  # compare byte count to 0x1000 (4 KiB)
    0x35608: 0x92402D09,  # byte offset mask 0xFFF
    0x35610: 0xF13FFD3F,  # compare segment end to 0xFFF
    0x35668: 0x940000F8,  # short/single-page PRP helper path
    0x356D4: 0x94000032,  # alternate PRP helper path
    0x35748: 0xF9009808,  # store first PRP in request at +304
    0x35818: 0xF9009A68,  # store first PRP for extended mapping
    0x359D8: 0xF834791A,  # fill PRP-list entry from page array
    0x35CA0: 0xA9137E7F,  # clear request PRP fields in completion path
}
# The original common Read command builder maps an *internal request*
# flag bit3 to NVMe command CDW0 bit13 (byte1 BIT5). This is conditional:
# it does not prove that all N71 reads turn on that request flag.
READ_FLAG_WORDS = {
    0x36168: 0xB940B809,  # read request internal flags at +184
    0x3616C: 0x5316552A,  # shift internal flag bit3 into CDW0 bit13
    0x36170: 0x1213014A,  # mask exactly 0x2000 (CDW0 BIT13)
    0x36174: 0x33103D0A,  # insert command ID independently
    0x36178: 0x321F0148,  # OR NVM READ opcode 0x02
    0x3617C: 0xB9011808,  # emit CDW0 with conditional flag
}

# The original generic request initializer at +0x34fec receives x6,
# retains it in x25 and conditionally sets internal request flags.bit3
# when that constructor argument is nonzero. Which value the active N71
# controller uses for a physical READ is NOT established by this proof.
REQUEST_FLAG_INITIALIZER_WORDS = {
    0x35008: 0xAA0603F9,  # x25 = constructor parameter x6
    0x35038: 0xB940BA68,  # internal request flags at +184
    0x3503C: 0x7100033F,  # compare x6 parameter with zero
    0x35040: 0x52800109,  # candidate mask = 0x8
    0x35044: 0x1A9F1129,  # select bit3 if x6 nonzero
    0x35048: 0x121C7908,  # clear previous internal bit3
    0x3504C: 0x2A090108,  # merge selected bit3
    0x35050: 0xB900BA68,  # write internal request flags
}

CALL_TARGETS = {
    0x13248: 0x365B4,
    0x13250: 0x36390,
    0x132AC: 0x35BDC,
    0x35BF4: 0x355B4,
    0x355F0: 0x429D0,
    0x35668: 0x35A48,
    0x356D4: 0x3579C,
}


def arm64_bl_target(at: int, insn: int) -> int:
    if (insn & 0xFC000000) != 0x94000000:
        raise ValueError("Expected an AArch64 BL call")
    imm26 = insn & 0x03FFFFFF
    if imm26 & (1 << 25):
        imm26 -= 1 << 26
    return at + (imm26 << 2)


def verify_transport_instruction_flow(code: bytes) -> None:
    if len(code) != READ.EXPECTED_TEXT_SIZE:
        raise ValueError("Original IONVMeFamily Read transport text size changed")
    for at, expected in {**PROVENANCE_WORDS, **READ_FLAG_WORDS,
                         **REQUEST_FLAG_INITIALIZER_WORDS}.items():
        if at + 4 > len(code) or struct.unpack_from("<I", code, at)[0] != expected:
            raise ValueError("Original NVMe Read-to-PRP source differs")
    for at, target in CALL_TARGETS.items():
        if arm64_bl_target(at, struct.unpack_from("<I", code, at)[0]) != target:
            raise ValueError("Original NVMe Read-to-PRP call target differs")


def verify_transport_words(code: bytes) -> None:
    READ.verify_true_original_text(code)
    verify_transport_instruction_flow(code)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("owner_private_original_kernelcache", type=Path)
    args = p.parse_args()
    try:
        code, _ = READ.extract_original_ionvme(
            args.owner_private_original_kernelcache.read_bytes())
        verify_transport_words(code)
    except (OSError, ValueError, KeyError, IndexError, OverflowError):
        print("N71_ORIGINAL_IONVME_READ_TO_PRP_GATE=REJECTED")
        return 1
    print("N71_ORIGINAL_IONVME_READ_TO_PRP_GATE=PASS")
    print("ORIGINAL_REQUEST_READ_OPCODE=0x02")
    print("ORIGINAL_REQUEST_BUILDER_THEN_IOVM_MAPPING=PROVEN")
    print("ORIGINAL_PRP_PAGE_GRANULARITY_BYTES=4096")
    print("ORIGINAL_PRP1_AND_MULTIPAGE_HELPERS=PROVEN")
    print("ORIGINAL_READ_OPTION_AND_PRP_POINTERS_DISTINCT=YES")
    print("ORIGINAL_REQUEST_FLAG_BIT3_TO_CDW0_BIT13=PROVEN_CONDITIONAL")
    print("ORIGINAL_REQUEST_INITIALIZER_X6_NONZERO_SETS_BIT3=PROVEN")
    print("ACTIVE_N71_IO_POOL_INITIALIZER_X6_VALUE=UNVERIFIED")
    print("READ_VENDOR_FLAG_BIT13_UNCONDITIONALLY_REQUIRED=UNVERIFIED")
    print("APPLE_S8000_TAG1_IO_PHYSICAL_ACCEPTANCE=UNVERIFIED")
    print("APPLE_VENDOR_TRANSPORT_BIT5_FOR_READ=UNVERIFIED")
    print("DMA_DRAIN_OR_NAND_DATA_READ=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
