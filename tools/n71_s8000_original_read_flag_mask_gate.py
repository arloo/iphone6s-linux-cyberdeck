#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authenticate Apple IONVMeFamily request-pool flag mask against N71 original.

Static source-level boolean model only. It never claims the lookup, the
auxiliary argument, dynamic class, final PRP wiring or DMA are proven live.
"""
import argparse
from pathlib import Path
import struct
import hashlib
import xml.etree.ElementTree as ET
import n71_s8000_original_ionvme_read_source_gate as READ
import n71_s8000_original_ionvme_read_prp_gate as FLOW

# Source byte offsets are relative to genuine original __TEXT_EXEC.__text.
# These are source instruction fingerprints, not the original executable.
MASK_SOURCE_WORDS = {
    # Explicit lifecycle stores of the auxiliary object and its input.
    0x257F8: 0xAA0103F4, # preserve incoming object
    0x257FC: 0xAA0003F3, # preserve controller
    0x2582C: 0xB4000DF4, # branch on null incoming object
    0x25830: 0xF9008674, # controller +264 = incoming object
    0x26B00: 0xAA0003F3,
    0x26B04: 0xF9408400, # load controller +264
    0x26B08: 0x52800001, # second call parameter = 0
    0x26B0C: 0x9400705C, # external stub, semantics not established here
    0x26B10: 0xF9015660, # store return at controller +680
    0x26B14: 0x52800020, # returns success independently of object value
    0x26B20: 0xD65F03C0,
    0x2DDB0: 0xF9415660, # cleanup loads auxiliary object
    0x2DDB4: 0xB4000080, # skip virtual cleanup when null
    0x2DDB8: 0xF9400008,
    0x2DDBC: 0xF9401508, # virtual cleanup slot +40
    0x2DDC0: 0xD63F0100,
    0x2DDC4: 0xF901567F, # clear +680
    0x2DDC8: 0xF9408660, # cleanup input object
    0x2DDCC: 0xB40000A0,
    0x2DDD0: 0xF9400008,
    0x2DDD4: 0xF9401508,
    0x2DDD8: 0xD63F0100,
    0x2DDDC: 0xF900867F, # clear +264
    # All three wrappers preserve the incoming stack argument and forward
    # it through the constructor's second outgoing stack slot to helper x5.
    0x20C: 0x9101C3FD, # wrapper 1 frame base
    0x24C: 0xF9400BA8, # load incoming stack argument
    0x250: 0xF90007E8, # forward to constructor stack slot +8
    0x278: 0x94008992,
    0x614: 0x9101C3FD, # wrapper 2 frame base
    0x654: 0xF9400BA8,
    0x658: 0xF90007E8,
    0x680: 0x94008890,
    0x22B00: 0x9101C3FD, # wrapper 3 frame base
    0x22B40: 0xF9400BA8,
    0x22B44: 0xF90007E8,
    0x22B6C: 0x97FFFF55,
    0x228D4: 0x910103FD, # constructor frame base
    0x22904: 0xF9400FA5, # constructor loads forwarded stack arg into x5
    0x22940: 0x9400002C, # invokes pool helper
    0x27168: 0xAA0003F3, # controller this saved in x19
    0x271D0: 0xF9415668, # controller field +680 loaded into x8
    0x271D8: 0xF90003E8, # route 1 passes field on stack
    0x271F8: 0x97FF6500,
    0x27238: 0xF9415668, # route 2 loads same field
    0x2723C: 0xF90003E8,
    0x2725C: 0x97FFEE22,
    0x27264: 0xF90003E8, # route 3 passes same x8 on stack
    0x27284: 0x97FF63DB,
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
    for call, target in ((0x22A20, 0x3031C), (0x22A78, 0x22DE4),
                         (0x278, 0x228C0), (0x680, 0x228C0),
                         (0x22B6C, 0x228C0), (0x22940, 0x229F0),
                         (0x271F8, 0x5F8), (0x2725C, 0x22AE4),
                         (0x27284, 0x1F0), (0x26B0C, 0x42C7C)):
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


def verify_mapper_symbol(blob: bytes, target: int, symoff: int, count: int,
                         stroff: int, strsize: int) -> None:
    if not (0 < count <= 100000 and 0 <= symoff <= len(blob)-16*count
            and 0 < strsize <= len(blob) and 0 <= stroff <= len(blob)-strsize):
        raise ValueError('Invalid kernel symbol table extent')
    expected = b'__ZN8IOMapper28copyMapperForDeviceWithIndexEP9IOServicej'
    names = []
    for i in range(count):
        idx, typ, sec, desc, value = struct.unpack_from('<IBBHQ', blob, symoff+16*i)
        if value != target:
            continue
        if not 0 <= idx < strsize:
            raise ValueError('Invalid symbol string index')
        end = blob.find(b'\0', stroff+idx, stroff+strsize)
        if end < 0:
            raise ValueError('Unterminated symbol name')
        names.append(blob[stroff+idx:end])
    if expected not in names:
        raise ValueError('Mapper symbol not found at resolved stub destination')


def verify_mapper_import(blob: bytes, code: bytes) -> None:
    ctor = READ.GATE
    main = ctor.KMAP.macho_segments(blob, 0)
    pre, info = main['__PRELINK_TEXT'], main['__PRELINK_INFO']
    raw = blob[info['offset']:info['offset']+info['filesize']].rstrip(b'\0')
    root = ET.fromstring(b'<plist>'+raw+b'</plist>')
    entries = [ctor.KMAP.pairs(n) for n in root.iter('dict')]
    entries = [e for e in entries if e.get('CFBundleIdentifier') is not None
               and e['CFBundleIdentifier'].text == READ.BUNDLE
               and e.get('_PrelinkExecutableLoadAddr') is not None]
    if len(entries) != 1:
        raise ValueError('Mapper import KEXT not unique')
    load = int(entries[0]['_PrelinkExecutableLoadAddr'].text, 0)
    nested = ctor.KMAP.macho_segments(blob, pre['offset']+load-pre['vm'])
    base = nested['__TEXT_EXEC']['sections']['__text']['vm']
    target = ctor.ctor_stub_callee(blob, main, nested, base+0x26B0C,
                                  struct.unpack_from('<I', code, 0x26B0C)[0])
    kernel = main['__TEXT_EXEC']
    if target != kernel['vm']+0x5E8E90 or target+320 > kernel['vm']+kernel['filesize']:
        raise ValueError('Mapper target differs from original kernel')
    off = kernel['offset']+target-kernel['vm']
    if hashlib.sha256(blob[off:off+320]).hexdigest() != 'e7b2e0ff45cb4b5e2b3ed1e82ec197cad0548a00449d67755ddc683b149ff3e2':
        raise ValueError('Mapper target fingerprint differs')
    # Pin the entire original function, not just its initial 320 bytes.
    if off+820 > len(blob) or target+820 > kernel['vm']+kernel['filesize']:
        raise ValueError('Truncated mapper selection function')
    if hashlib.sha256(blob[off:off+820]).hexdigest() != '3043a7035e5f045762649c27fbf71556b2c116661c8eea456c256463eb2f0962':
        raise ValueError('Mapper selection function fingerprint differs')
    # Resolve the original ADRP/ADD property-name reference.
    pc = target+0x3c
    adrp, add = struct.unpack_from('<2I', blob, off+0x3c)
    if (adrp, add) != (0xf0ffcae1, 0x9132bc21):
        raise ValueError('Mapper property address instructions differ')
    imm = ((adrp >> 29) & 3) | (((adrp >> 5) & 0x7ffff) << 2)
    if imm & (1 << 20):
        imm -= 1 << 21
    addr = (pc & ~0xfff) + (imm << 12) + ((add >> 10) & 0xfff)
    text = main['__TEXT']
    if not text['vm'] <= addr <= text['vm']+text['filesize']-13:
        raise ValueError('Mapper property literal outside kernel text')
    literal = text['offset']+addr-text['vm']
    if blob[literal:literal+13] != b'iommu-parent\0':
        raise ValueError('Mapper property name differs')
    count, size = struct.unpack_from('<II', blob, 16)
    pos, end = 32, 32+size
    tables = []
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', blob, pos)
        if length < 8 or pos+length > end:
            raise ValueError('Invalid kernel load command')
        if cmd == 2:
            if length != 24:
                raise ValueError('Invalid LC_SYMTAB')
            tables.append(struct.unpack_from('<4I', blob, pos+8))
        pos += length
    if len(tables) != 1 or pos != end:
        raise ValueError('Kernel symbol table not unique')
    verify_mapper_symbol(blob, target, *tables[0])


def verify_original(kernelcache: bytes) -> None:
    code, _ = READ.extract_original_ionvme(kernelcache)
    FLOW.verify_transport_instruction_flow(code)
    verify_instructions(code)
    verify_mapper_import(kernelcache, code)


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
    print('AUXILIARY_SOURCE=CONTROLLER_FIELD_680_VIA_ALL_THREE_STACK_ROUTES')
    print('AUXILIARY_INITIALIZATION=EXTERNAL_CALL_RESULT_FROM_CONTROLLER_FIELD_264')
    print('AUXILIARY_IMPORT=IOMapper_copyMapperForDeviceWithIndex_INDEX_0')
    print('AUXILIARY_CLEANUP=NULL_CHECK_VIRTUAL_CALL_AND_ZERO')
    print('MAPPER_SELECTION_PROPERTY=iommu-parent')
    print('MAPPER_INDEXED_DATA_CELL_WIDTH=4')
    print('LOOKUP_AND_AUXILIARY_RUNTIME_VALUES=UNVERIFIED')
    print('ACTIVE_N71_CONTROLLER_BINDING=UNVERIFIED')
    print('COMMAND_BIT13_AFTER_FILTER=CONDITIONAL')
    print('FIRST_NAND_READ_OR_DMA_ACCESS=NOT_AUTHORIZED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
