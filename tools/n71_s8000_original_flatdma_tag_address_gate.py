#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit original N71/S8000 AppleNVMeMMU FlatDMA tag addressing.

The owner's Apple kernelcache and ADT remain private. Pinned instruction
identities validate register flow: 16-bit command tag -> left shift 23 ->
bitwise OR with owner base. Independently verify the 128-tag ADT resource.
This does not prove the NVM READ command's vendor flags or DMA retirement.
"""
import argparse
from pathlib import Path
import struct

import n71_s8000_storage_fact_implementation_gate as F
import n71_s8000_nvmmu_owned_table_source_gate as NV

# Only selected instruction identities, NOT proprietary executable content.
# The actual source instruction at +0x32fc is LSL w10,w22,#23.
# The preceding load at +0x32c4 sources the owner's 32-bit virtual base.
# The following ORR and STR form and return the resulting FlatDMA address.
ORIGINAL_S800X_TAG_WORDS = {
    # Original segment callback and descriptor construction.
    0x2ef8: 0xf2402c5f,  # require 4 KiB aligned start
    0x2f00: 0xf2402c7f,  # require 4 KiB aligned length
    0x2f0c: 0xd34cfc68,  # page count from length
    0x2f14: 0xd34cfc4a,  # page number from start
    0x2f20: 0x6b0c017f,  # compare SGL index to capacity
    0x2f24: 0x54000162,  # stop at capacity
    0x2f28: 0x0b09014c,  # consecutive page number
    0x2f30: 0xb82b59ac,  # store 32-bit SGL entry
    0x2f40: 0xb900102b,  # advance entry count
    0x2f44: 0x6b09011f,  # compare generated page count
    0x2fb8: 0xf9405508,  # descriptor virtual method slot 168
    0x2fc0: 0xd63f0100,
    0x2fd4: 0xaa0003f8,  # preserve direction selector
    0x3134: 0xb9000b88,  # first page number -> TCB +8
    0x3138: 0xb9402be8,  # load generated page count
    0x313c: 0x34000068,  # no SGL pointer store if count zero
    0x3144: 0xf9000b88,  # SGL pointer -> TCB +16
    0x3148: 0x7100071f,  # selector 1
    0x314c: 0x540000a0,
    0x3150: 0x71000b1f,  # selector 2
    0x3154: 0x54001021,  # reject other selector
    0x3158: 0x52802008,  # selector 2 -> 0x100
    0x3160: 0x52804008,  # selector 1 -> 0x200
    0x3164: 0xb9000388,  # control -> TCB +0
    0x3228: 0xd5033bbf,  # DMB ISH before count publication
    0x322c: 0xb9402be8,
    0x3230: 0xb9000788,  # publish count at TCB +4
    0x30b4: 0x79009aa9,  # selected 16-bit tag index -> object +76
    0x324c: 0x8b091d08,  # TCB address += slot << 7 (128-byte TCB)
    0x3270: 0x79409aa8,  # selected 16-bit tag index for TCB
    0x3284: 0x8b0a1d2a,  # TCB status array stride 128 bytes
    0x32c4: 0xb9415294,  # owner's NVMMU virtual base at offset 336
    0x32c8: 0x79409ab6,  # actual allocated tag at object offset 76
    0x32fc: 0x530922ca,  # index << 23, exactly 8 MiB per tag
    0x3300: 0xaa14014a,  # OR with owner's NVMMU virtual base
    0x3304: 0xf900012a,  # return the formed data-tag address
}
TAG_SHIFT = 23
TAG_COUNT = 128
NVMMU_VBASE = 0x40000000


def verify_source_words(code: bytes) -> None:
    for offset, expected in ORIGINAL_S800X_TAG_WORDS.items():
        if offset % 4 or offset + 4 > len(code):
            raise ValueError("Original S800x tag method truncated")
        if struct.unpack_from("<I", code, offset)[0] != expected:
            raise ValueError("Original S800x tag-index flow changed")


def tag_base(index: int) -> int:
    if not 0 <= index < TAG_COUNT:
        raise ValueError("S8000 NVMMU tag index out of bounds")
    return NVMMU_VBASE | (index << TAG_SHIFT)


def tag_index(address: int) -> int:
    if (address < NVMMU_VBASE or
            address >= NVMMU_VBASE + (TAG_COUNT << TAG_SHIFT)):
        raise ValueError("S8000 NVMMU tag address outside owned aperture")
    offset = address - NVMMU_VBASE
    if offset % (1 << TAG_SHIFT):
        raise ValueError("S8000 FlatDMA address is an offset, not a tag base")
    index = offset >> TAG_SHIFT
    if tag_base(index) != address:
        raise ValueError("S8000 FlatDMA tag base encoding mismatch")
    return index


def audit(kernelcache: bytes, original_adt: bytes) -> None:
    NV.audit(kernelcache, original_adt)
    _, port, _ = F.STORAGE.FANOUT.original_port_vtable(kernelcache)
    verify_source_words(port["shared"]["code"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner_original_n71_kernelcache_macho", type=Path)
    parser.add_argument("owner_original_n71_adt", type=Path)
    args = parser.parse_args()
    try:
        audit(args.owner_original_n71_kernelcache_macho.read_bytes(),
              args.owner_original_n71_adt.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        print("N71_ORIGINAL_NVMMU_FLATDMA_TAG_SOURCE_GATE=REJECTED")
        return 1
    print("N71_ORIGINAL_NVMMU_FLATDMA_TAG_SOURCE_GATE=PASS")
    print("ORIGINAL_TAG_COUNT=128 ORIGINAL_TCB_STRIDE_BYTES=128")
    print("ORIGINAL_TAG_ADDRESS_SHIFT=23 TAG_STRIDE_BYTES=8388608")
    print("ORIGINAL_NVMMU_VBASE=0x40000000")
    print("IDENTIFY_TAG0_BASE=0x40000000")
    print("PREVIOUS_0x40001000_IS_TAG1=NO")
    print("NEXT_DISTINCT_TAG1_CANDIDATE=0x40800000")
    print("ORIGINAL_TCB_DIRECTION_SELECTOR_1=0x200 SELECTOR_2=0x100")
    print("ORIGINAL_SGL_PAGE_NUMBER_WIDTH=32 PAGE_SHIFT=12")
    print("ORIGINAL_TCB_PAGE_COUNT_AFTER_DMB_ISH=YES")
    print("NVM_READ_VENDOR_FLAGS_OR_SGL_QUALIFIED=NO")
    print("DEVICE_DMA_OR_NAND_ACCESSED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
