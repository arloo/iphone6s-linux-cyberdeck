#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the original N71/S8000 S5L DART0 status/context register path.

Owner-supplied kernelcache stays local. Reports only aggregate boolean results;
never outputs proprietary instructions, MMIO values, physical addresses, or
firmware content. This is source auditing, NOT evidence of DMA quiescence.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

import n71_original_dart_mapper_tcr_lane_gate as DART


class RejectedDARTContext(ValueError):
    """Source does not match the audited original S8000 DART path."""


# Small selected instruction fingerprints only; not executable Apple code.
# First original path: DART register base from object +2768; error/status
# offset 0x10, then bit31 branch, then context offsets 0x1c/0x14/0x18.
# Second path: sibling base from object +2824, same status and context.
S5L_WORDS = {
    0xe44: 0xf9456a68,  # load original DART0 MMIO base
    0xe48: 0xb9401109,  # read 32-bit status at +0x10
    0xe4c: 0x37f80509,  # TBNZ status bit31: error handling path
    0xe58: 0xf9458669,  # optional second base
    0xe5c: 0xb940112a,  # sibling status at +0x10
    0xe60: 0x37f80a8a,  # TBNZ sibling bit31
    0xe64: 0xb9500108,  # additional TLB status at +0x1000
    0xef4: 0xb9401d09,  # context +0x1c
    0xefc: 0xb9401509,  # context +0x14
    0xf04: 0xb9401908,  # context +0x18
    0xfb8: 0xb9401d28,  # sibling context +0x1c
    0xfc0: 0xb9401528,  # sibling context +0x14
    0xfc8: 0xb9401928,  # sibling context +0x18
}
S5L_EXPECTED_SIZE = 17156


def verify_s5l_fault_path(code: bytes) -> None:
    if len(code) != S5L_EXPECTED_SIZE:
        raise RejectedDARTContext("Original S5L DART executable size changed")
    for offset, expected in S5L_WORDS.items():
        if struct.unpack_from("<I", code, offset)[0] != expected:
            raise RejectedDARTContext("Original S5L DART error-context path changed")


def audit(kernelcache: Path) -> None:
    data = kernelcache.read_bytes()
    DART.verify_original_code(data)
    _, modules = DART.extract_original_modules(data)
    verify_s5l_fault_path(modules[DART.S5L]["code"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_n71_kernelcache_macho", type=Path)
    args = parser.parse_args()
    try:
        audit(args.original_n71_kernelcache_macho)
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        print("N71_S8000_ORIGINAL_DART0_CONTEXT_SOURCE_GATE=REJECTED")
        return 1
    print("N71_S8000_ORIGINAL_DART0_CONTEXT_SOURCE_GATE=PASS")
    print("DART0_ORIGINAL_STATUS_REGISTER_OFFSET=0x10")
    print("DART0_ORIGINAL_CONTEXT_OFFSETS=0x14,0x18,0x1c")
    print("DART0_ORIGINAL_STATUS_BIT31_CHECK=VERIFIED")
    print("DART0_RECORDED_0x500_BIT31_SET=NO")
    print("S8000_DART0_TRANSACTION_DRAIN_PROVEN=NO")
    print("PHONE_MMIO_OR_NAND_ACCESSED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
