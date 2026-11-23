#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authenticate Apple IONVMeFamily request-pool flag mask against N71 original.

Static source-level boolean model only. It never claims the lookup, the
auxiliary argument, dynamic class, final PRP wiring or DMA are proven live.
"""
import argparse
from pathlib import Path
import struct
import n71_s8000_original_ionvme_read_source_gate as READ
import n71_s8000_original_ionvme_read_prp_gate as FLOW

# Source byte offsets are relative to genuine original __TEXT_EXEC.__text.
# These are source instruction fingerprints, not the original executable.
MASK_SOURCE_WORDS = {
    0x22A08: 0xAA0503F4, # incoming helper x5 saved in x20
    0x22A10: 0xAA0303F9, # incoming controller-derived flag x3 saved in x25
    0x22A20: 0x9400363F, # predicate helper 0x3031c
    0x22A24: 0xF100029F, # compare x20 with zero
    0x22A28: 0x1A9F07E8, # w8 := x20 != 0
    0x22A2C: 0x2A080018, # w24 := predicate result OR w8
    0x22A30: 0x0A180339, # w25 := request flag AND w24
    0x22A34: 0x36000079, # optional-resource branch on masked bit0
    0x22A68: 0xAA1903E3, # propagate masked flag to request allocator
    0x22A78: 0x940000DB, # allocation loop 0x22DE4
    0x3031C: 0xA9BE4FF4, # predicate helper entry
    0x30328: 0x90FF8580, # lookup operand source (do not infer runtime)
    0x30330: 0xD2800001, # null secondary lookup argument
    0x30334: 0x94004A76, # lookup call
    0x30338: 0xB40001C0, # if no object return zero
    0x30340: 0x94004A7F, # further lookup call
    0x30344: 0xF100001F, # compare returned object with zero
    0x30348: 0x1A9F07F4, # predicate = nonzero
    0x3034C: 0xB4000080, # conditional release path
    0x3035C: 0xF9400268, # release via vtable
    0x30370: 0x52800014, # missing lookup -> predicate zero
    0x30374: 0xAA1403E0, # helper returns predicate as w0
    0x35008: 0xAA0603F9, # per-request initializer retains x6
    0x3503C: 0x7100033F, # test x6 nonzero
    0x35044: 0x1A9F1129, # map to internal bit3 conditionally
    0x3504C: 0x2A090108, # or with other request flags
    0x35050: 0xB900BA68, # store request flags
    0x3616C: 0x5316552A, # source flags bit3 -> CDW0 bit13
    0x36170: 0x1213014A, # mask 0x2000 in CDW0
}


def verify_instructions(code: bytes) -> None:
    if len(code) != READ.EXPECTED_TEXT_SIZE:
        raise ValueError('Original code extent is different')
    for at, expected in MASK_SOURCE_WORDS.items():
        if struct.unpack_from('<I', code, at)[0] != expected:
            raise ValueError('Original Apple I/O flag masking flow differs')
    for call, target in ((0x22A20, 0x3031C), (0x22A78, 0x22DE4)):
        if FLOW.arm64_bl_target(call, struct.unpack_from('<I', code, call)[0]) != target:
            raise ValueError('Original Apple request pool branch differs')


def effective_request_bit0(controller_bit: int, lookup_predicate: int,
                           auxiliary_nonzero: int) -> int:
    """CPU-only model of bit0 of w25 after the original w24 mask.

    Inputs are hypothetical runtime booleans, NOT read from the iPhone.
    """
    if any(v not in (0, 1) for v in
           (controller_bit, lookup_predicate, auxiliary_nonzero)):
        raise ValueError('Only booleans are allowed as modeled inputs')
    return controller_bit & (lookup_predicate | auxiliary_nonzero)


def verify_original(kernelcache: bytes) -> None:
    code, _ = READ.extract_original_ionvme(kernelcache)
    FLOW.verify_transport_instruction_flow(code)
    verify_instructions(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_original_n71_kernelcache', type=Path)
    args = parser.parse_args()
    try:
        verify_original(args.private_original_n71_kernelcache.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        print('N71_ORIGINAL_READ_FLAG_MASK_GATE=REJECTED')
        return 1
    print('N71_ORIGINAL_READ_FLAG_MASK_GATE=PASS')
    print(f'PINNED_SOURCE_INSTRUCTION_WORDS={len(MASK_SOURCE_WORDS)}')
    print('PROVEN_BOOLEAN_BIT0=controller_bit AND (lookup_predicate OR auxiliary_nonzero)')
    print('LOOKUP_AND_AUXILIARY_RUNTIME_VALUES=UNVERIFIED')
    print('ACTIVE_N71_CONTROLLER_BINDING=UNVERIFIED')
    print('COMMAND_BIT13_AFTER_FILTER=CONDITIONAL')
    print('FIRST_NAND_READ_OR_DMA_ACCESS=NOT_AUTHORIZED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
