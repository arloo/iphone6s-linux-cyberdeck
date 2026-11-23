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
    print("NVM_READ_VENDOR_FLAGS_OR_SGL_QUALIFIED=NO")
    print("DEVICE_DMA_OR_NAND_ACCESSED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
