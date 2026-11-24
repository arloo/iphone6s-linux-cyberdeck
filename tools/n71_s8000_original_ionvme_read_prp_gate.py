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
    0x12DF8: 0xF9405508,  # memory descriptor virtual slot 168
    0x12DFC: 0xAA1503E0,
    0x12E00: 0xD63F0100,
    0x12E04: 0x12001C1A,  # retain direction selector
    0x12E08: 0x51000748,
    0x12E0C: 0x7100091F,
    0x12E10: 0x540038E2,  # reject direction outside 1..2
    0x13240: 0x71000B5F,  # compare direction to WRITE selector 2
    0x13244: 0x54000061,  # READ path when direction is 1
    0x13248: 0x94008CDB,  # WRITE wrapper
    0x13250: 0x94008C50,  # READ wrapper
    0x365EC: 0x97FFFF1C,  # WRITE wrapper -> opcode builder
    0x36298: 0x32000148,  # WRITE opcode 1
    0x3629C: 0xB9011808,
    0x363C4: 0x97FFFF5E,  # READ wrapper -> opcode builder
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

# Original Apple N71 IONVMeFamily request-pool FACTORY propagation:
# top-level wrappers forward their incoming fifth argument x4 as x5;
# the pool ctor stores it as x19; a downstream gate masks w25 with
# w24 before forwarding it as a factory parameter. The value actually
# selected by the active N71 S8000 provider remains UNVERIFIED.
# Direct source proof only; a vtable/class symbol may refer to ANS2 too.
FACTORY_FLAG_PROPAGATION_WORDS = {
    0x00278: 0x94008992,  # wrapper 1 calls pool ctor +0x228C0
    0x00680: 0x94008890,  # wrapper 2 calls same pool ctor
    0x22B6C: 0x97FFFF55,  # wrapper 3 calls same pool ctor
    0x22940: 0x9400002C,  # pool ctor calls helper +0x229F0
    0x0021C: 0xAA0403F7,  # wrapper x23 = original x4
    0x0026C: 0xAA1703E5,  # wrapper outgoing x5 = x23
    0x00624: 0xAA0403F7,  # another wrapper x23 = x4
    0x00674: 0xAA1703E5,  # another outgoing x5 = x23
    0x22B10: 0xAA0403F7,  # third wrapper x23 = original x4
    0x22B60: 0xAA1703E5,  # third outgoing x5 = x23
    0x228E0: 0xAA0503F3,  # pool constructor preserves input x5 in x19
    0x2293C: 0xAA1303E3,  # x3 = x19 to first pool helper
    0x22A10: 0xAA0303F9,  # x25 = helper incoming x3
    0x22A2C: 0x2A080018,  # w24 = prior condition OR nonnull-owner condition
    0x22A30: 0x0A180339,  # w25 &= w24 before constructing queue
    0x22A34: 0x36000079,  # conditionally skip path on masked bit0
    0x22A68: 0xAA1903E3,  # x3 = filtered x25 for pool routine
    0x22A78: 0x940000DB,  # call pool routine +0x22DE4
    0x22E0C: 0xB90017E3,  # pool routine saves incoming w3 as local flag
    0x22E9C: 0xB94017E5,  # reloads that flag into outgoing w5
    0x22EA4: 0x940047F6,  # creates one request via factory +0x34E7C
    0x34EA8: 0xAA0503F5,  # factory retains incoming x5 in x21
    0x34F08: 0xAA1503E6,  # factory passes x21 as initializer x6
    0x34F10: 0x94000037,  # call initializer +0x34FEC
}

# In the original controller request-pool initializer, a common
# virtual controller method at vtable offset 1440 returns x0. The return
# is saved as x22 and forwarded as the x4 argument by ALL three wrapper
# branches. The actual runtime method return and controller class are
# NOT established for the physical N71 by these source identities.
CONTROLLER_POOL_ARGUMENT_WORDS = {
    0x27180: 0xF942D508,  # controller virtual method at offset 1448 for branch choice
    0x27184: 0xD63F0100,  # invoke choice method
    0x271A0: 0xF9400268,  # controller vtable pointer
    0x271A4: 0xF942D108,  # vtable method at offset 1440
    0x271A8: 0xAA1303E0,  # pass controller this in x0
    0x271AC: 0xD63F0100,  # invoke common method
    0x271B0: 0xAA0003F6,  # save return value in x22
    0x271D4: 0x37600499,  # feature-dependent wrapper selection
    0x271E8: 0x52800023,  # wrapper parameter x3=1, NOT the conditional x4
    0x271EC: 0xAA1603E4,  # route1 x4 = common method result x22
    0x271F8: 0x97FF6500,  # route1 wrapper +0x5F8
    0x27208: 0xF9400268,  # route2 controller vtable pointer
    0x2720C: 0xF942D108,  # same method at offset 1440
    0x27210: 0xAA1303E0,  # same controller this
    0x27214: 0xD63F0100,  # same virtual method
    0x27218: 0xAA0003F6,  # route2 x22 = returned x0
    0x2724C: 0x52800023,  # route2 unrelated x3=1
    0x27250: 0xAA1603E4,  # route2 x4 = returned x22
    0x2725C: 0x97FFEE22,  # route2 wrapper +0x22AE4
    0x27270: 0xAA1403E2,  # route3 other argument x2
    0x27274: 0x52800023,  # route3 unrelated x3=1
    0x27278: 0xAA1603E4,  # route3 x4 = returned x22
    0x27284: 0x97FF63DB,  # route3 wrapper +0x1F0
}

CALL_TARGETS = {
    0x13248: 0x365B4,
    0x13250: 0x36390,
    0x365EC: 0x3625C,
    0x363C4: 0x3613C,
    0x132AC: 0x35BDC,
    0x35BF4: 0x355B4,
    0x355F0: 0x429D0,
    0x35668: 0x35A48,
    0x356D4: 0x3579C,
    0x00278: 0x228C0,  # wrapper 1 -> original request-pool ctor
    0x00680: 0x228C0,  # wrapper 2 -> same request-pool ctor
    0x22B6C: 0x228C0,  # wrapper 3 -> same request-pool ctor
    0x22940: 0x229F0,  # pool ctor -> pool allocation helper
    0x22A78: 0x22DE4,  # pool helper -> per-request allocation loop
    0x22EA4: 0x34E7C,  # per-request allocation -> request factory
    0x34F10: 0x34FEC,  # request factory -> original flag initializer
    0x271F8: 0x005F8,  # controller first route to wrapper
    0x2725C: 0x22AE4,  # controller second route to wrapper
    0x27284: 0x001F0,  # controller third route to wrapper
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
                         **REQUEST_FLAG_INITIALIZER_WORDS,
                         **FACTORY_FLAG_PROPAGATION_WORDS,
                         **CONTROLLER_POOL_ARGUMENT_WORDS}.items():
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
    print("ORIGINAL_DIRECTION_1_READ_2_WRITE=VERIFIED")
    print("ORIGINAL_REQUEST_BUILDER_THEN_IOVM_MAPPING=PROVEN")
    print("ORIGINAL_PRP_PAGE_GRANULARITY_BYTES=4096")
    print("ORIGINAL_PRP1_AND_MULTIPAGE_HELPERS=PROVEN")
    print("ORIGINAL_READ_OPTION_AND_PRP_POINTERS_DISTINCT=YES")
    print("ORIGINAL_REQUEST_FLAG_BIT3_TO_CDW0_BIT13=PROVEN_CONDITIONAL")
    print("ORIGINAL_REQUEST_INITIALIZER_X6_NONZERO_SETS_BIT3=PROVEN")
    print("ORIGINAL_REQUEST_POOL_X4_TO_FACTORY_X6=PROVEN_WITH_CONDITIONAL_MASK")
    print("ORIGINAL_POOL_CONSTRUCTOR_FILTER_22A30=PROVEN")
    print("ORIGINAL_THREE_POOL_WRAPPERS_SHARE_CONTROLLER_VMETHOD_OFFSET_1440=PROVEN")
    print("N71_ACTIVE_CONTROLLER_VMETHOD_RETURN=UNVERIFIED")
    print("ACTIVE_N71_REQUEST_POOL_WRAPPER_AND_X4_VALUE=UNVERIFIED")
    print("ACTIVE_N71_IO_POOL_INITIALIZER_X6_VALUE=UNVERIFIED")
    print("READ_VENDOR_FLAG_BIT13_UNCONDITIONALLY_REQUIRED=UNVERIFIED")
    print("APPLE_S8000_TAG1_IO_PHYSICAL_ACCEPTANCE=UNVERIFIED")
    print("APPLE_VENDOR_TRANSPORT_BIT5_FOR_READ=UNVERIFIED")
    print("DMA_DRAIN_OR_NAND_DATA_READ=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
