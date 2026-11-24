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

# Entire original kernel executable, independently inspected alongside the KEXT.
EXPECTED_KERNEL_TEXT_SIZE = 6864896
EXPECTED_KERNEL_TEXT_SHA256 = 'cdd5be4f1b5354548bc1bd2d3a05d3bee23115efb2ca874837f47b1a8fd835fa'
KERNEL_DMA_SOURCE_WORDS = {
    # genIOVMSegments wrapper preserves x0 and tail-calls the common generator.
    0x5E7AF4: 0xAA0403E6,
    0x5E7AF8: 0xAA0303E5,
    0x5E7AFC: 0xAA0203E4,
    0x5E7B00: 0xAA0103E3,
    0x5E7B04: 0x10FF7F82,
    0x5E7B08: 0xD503201F,
    0x5E7B0C: 0x52801001,
    0x5E7B10: 0x17FFFA78,
    # The common generator retains the same command and reads its mapper.
    0x5E651C: 0xAA0003F8,  # x24 = incoming command
    0x5E659C: 0xF9402308,  # command +64
    0x5E65A0: 0xB4000248,  # null-dependent path
    # Inherited prepare also consumes the same command's mapper field.
    0x5E55F8: 0xAA0003F5,  # x21 = incoming command
    0x5E56B0: 0xF94022A9,
    0x5E56B4: 0xB40000A9,
    0x5E5750: 0xF94022A8,
    0x5E5754: 0xB40018E8,
    0x5E5824: 0xF94022A0,  # mapper becomes virtual-call receiver
    0x5E5828: 0xF9400008,
    0x5E582C: 0xF942A508,
    0x5E5830: 0xD63F0100,
}
DMA_KERNEL_SYMBOLS = {
    'constructor': (0x5E75D8, b'__ZN12IODMACommandC2EPK11OSMetaClass'),
    'generator': (0x5E7AF4, b'__ZN12IODMACommand15genIOVMSegmentsEPFbPS_NS_9Segment64EPvjEPyS2_Pj'),
    'descriptor': (0x5E52F8, b'__ZN12IODMACommand19setMemoryDescriptorEPK18IOMemoryDescriptorb'),
    'prepare': (0x5E55A8, b'__ZN12IODMACommand7prepareEyybb'),
}

# Source byte offsets are relative to genuine original __TEXT_EXEC.__text.
# These are source instruction fingerprints, not the original executable.
MASK_SOURCE_WORDS = {
    # Owner initialization: x2 -> byte +496 after successful virtual init;
    # provider x1 -> safeMetaCast result -> pointer +464.
    0x12B78: 0xAA0403F6,
    0x12B7C: 0xAA0303F5,
    0x12B80: 0xAA0203F4,
    0x12B84: 0xAA0003F7,
    0x12B88: 0xF9400008,
    0x12B8C: 0xF9430108,
    0x12B90: 0xD63F0100,
    0x12B94: 0xAA0003F3,
    0x12B98: 0x36000140,
    0x12B9C: 0x390762F6,
    0x12BA0: 0x3907CAF5,
    0x12BA4: 0x3907C2F4,
    0x12C08: 0xAA0103F3,
    0x12C0C: 0xAA0003F4,
    0x12C38: 0xB0003428,
    0x12C3C: 0x913E4108,
    0x12C40: 0xF9400101,
    0x12C44: 0xAA1303E0,
    0x12C48: 0x9400BFA4,
    0x12C4C: 0xF900E680,
    0x12C50: 0xB40004E0,
    0x12C54: 0xF0003428,
    0x12C58: 0x913C6108,
    0x12C5C: 0xF9400101,
    0x12C60: 0xAA1303E0,
    0x12C64: 0x9400BF9D,
    0x12C68: 0xF900EA80,
    # Shared Read/Write handler: selectors start at 0 or 4; set bit3
    # only when owner byte +496 == 1 and owner pointer +464 is null.
    # Then acquire the request and invoke inherited descriptor/prepare.
    0x12DB4: 0xAA0003F3,
    0x13014: 0x52800098,
    0x13040: 0x52800018,
    0x130F8: 0x3947C268,
    0x130FC: 0x7100051F,
    0x13100: 0x540000A1,
    0x13104: 0xF940EA68,
    0x13108: 0x321D0309,
    0x1310C: 0xF100011F,
    0x13110: 0x1A980138,
    0x13114: 0xF9404A60,
    0x13118: 0xF9400008,
    0x1311C: 0xF942C108,
    0x13120: 0xAA1803E1,
    0x13124: 0xAA1403E2,
    0x13128: 0xD63F0100,
    0x1312C: 0xB40021A0,
    0x13130: 0xAA0003F8,
    0x13134: 0x39073014,
    0x13254: 0xF9400308,
    0x13258: 0xF9404508,
    0x1325C: 0xAA1803E0,
    0x13260: 0xAA1503E1,
    0x13264: 0x52800002,
    0x13268: 0xD63F0100,
    0x1326C: 0x35000040,
    0x13270: 0xF9006315,
    0x1327C: 0xF9400308,
    0x13280: 0xF9405108,
    0x13284: 0xAA1803E0,
    0x13288: 0xD2800001,
    0x1328C: 0x52800023,
    0x13290: 0x52800024,
    0x13294: 0xD63F0100,
    0x13298: 0x35001840,
    # Both original request constructors invoke the IODMACommand parent,
    # then install the same owned request vtable.
    0x34E00: 0xAA0003F3,
    0x34E0C: 0xAA1403E1,
    0x34E10: 0x940036F6,
    0x34E14: 0xB0003368,
    0x34E18: 0x9133A108,
    0x34E1C: 0xF9000008,
    0x34E44: 0xAA0003F3,
    0x34E50: 0xAA1403E1,
    0x34E54: 0x940036E5,
    0x34E58: 0xB0003368,
    0x34E5C: 0x9133A108,
    0x34E60: 0xF9000008,
    0x3554C: 0xAA0003F3,
    # Complete entry-to-call block: the request stays in x0 while the
    # genIOVMSegments arguments are assembled. No separate command is loaded.
    0x355B4: 0xD10103FF,
    0x355B8: 0xA9024FF4,
    0x355BC: 0xA9037BFD,
    0x355C0: 0x9100C3FD,
    0x355C4: 0xAA0003F3,
    0x355C8: 0xA9017FFF,
    0x355CC: 0x52800028,
    0x355D0: 0xB9000FE8,
    0x355D4: 0xF9406408,
    0x355D8: 0xF90003E8,
    0x355DC: 0xD0003301,
    0x355E0: 0xF9422821,
    0x355E4: 0x910003E2,
    0x355E8: 0x910043E3,
    0x355EC: 0x910033E4,
    0x355F0: 0x940034F8,
    0x355F4: 0x35000880,
    # Original embedded controller: acquire three indexed mappers.
    0x12B8: 0xF9408400,
    0x12BC: 0x52800001,
    0x12C0: 0x9401066F,
    0x12C4: 0xF903FA60,  # index 0 -> controller +2032
    0x12C8: 0xB40001E0,
    0x12CC: 0xF9408660,
    0x12D0: 0x52800021,
    0x12D4: 0x9401066A,
    0x12D8: 0xF9040260,  # index 1 -> controller +2048
    0x12DC: 0xB40002A0,
    0x12E0: 0xF9408660,
    0x12E4: 0x52800041,
    0x12E8: 0x94010665,
    0x12EC: 0xF903FE60,  # index 2 -> controller +2040
    0x12F0: 0xB4000360,
    # The input argument bit3 below is NOT yet proven identical to
    # the internal request flag bit3 used by the PRP helper.
    0x67E0: 0xAA0103F4,  # save incoming request selector
    0x6914: 0x371800B4,
    0x6918: 0xF943FA61,  # select index 0 mapper
    0x691C: 0xAA1603E0,
    0x6920: 0x52800002,
    0x6924: 0x14000004,
    0x6928: 0xF943FE61,  # select index 2 mapper
    0x692C: 0xAA1603E0,
    0x6930: 0x52800022,
    0x6934: 0x9400BB01,
    0x35550: 0xF9402008,
    0x35584: 0xF9002275,  # request +64 mapper storage
    0x35588: 0xB940BA68,
    0x3558C: 0x7100029F,
    0x35590: 0x52800209,  # separate flag bit4
    0x35594: 0x1A9F1129,
    0x35598: 0x121B7908,
    0x3559C: 0x2A090108,
    0x355A0: 0xB900BA68,
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
                         (0x27284, 0x1F0), (0x26B0C, 0x42C7C),
                         (0x12C0, 0x42C7C), (0x12D4, 0x42C7C),
                         (0x12E8, 0x42C7C), (0x6934, 0x35538)):
        if FLOW.arm64_bl_target(call, struct.unpack_from('<I', code, call)[0]) != target:
            raise ValueError('Original Apple request pool branch differs')


def verify_kernel_dma_words(code: bytes) -> None:
    if len(code) != EXPECTED_KERNEL_TEXT_SIZE:
        raise ValueError('Original kernel executable extent differs')
    for at, expected in KERNEL_DMA_SOURCE_WORDS.items():
        if struct.unpack_from('<I', code, at)[0] != expected:
            raise ValueError('Original kernel command/mapper flow differs')


def verify_true_original_kernel_text(code: bytes) -> None:
    verify_kernel_dma_words(code)
    if hashlib.sha256(code).hexdigest() != EXPECTED_KERNEL_TEXT_SHA256:
        raise ValueError('Original kernel executable fingerprint differs')


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
                         stroff: int, strsize: int, *,
                         expected: bytes = b'__ZN8IOMapper28copyMapperForDeviceWithIndexEP9IOServicej') -> None:
    if not (0 < count <= 100000 and 0 <= symoff <= len(blob)-16*count
            and 0 < strsize <= len(blob) and 0 <= stroff <= len(blob)-strsize):
        raise ValueError('Invalid kernel symbol table extent')
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
    for call in (0x12C0, 0x12D4, 0x12E8):
        if ctor.ctor_stub_callee(blob, main, nested, base+call,
                                struct.unpack_from('<I', code, call)[0]) != target:
            raise ValueError('Indexed mapper import target differs')
    vp = ctor.adrp_add_str_vptr(base+0xaa8, *struct.unpack_from('<3I', code, 0xaa8))
    cconst = nested['__DATA_CONST']['sections']['__const']
    if not cconst['vm'] <= vp <= cconst['vm']+cconst['size']-1872:
        raise ValueError('Embedded mapper vtable outside own const section')
    for slot, method in ((1408, 0x67c0), (1864, 0x12a8)):
        if ctor.read_data_pointer(blob, main, vp+slot) != base+method:
            raise ValueError('Embedded mapper virtual method differs')
    kernel = main['__TEXT_EXEC']
    verify_true_original_kernel_text(blob[kernel['offset']:kernel['offset']+kernel['filesize']])
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
    for call in (0x12C48, 0x12C64):
        actual = ctor.ctor_stub_callee(blob, main, nested, base+call,
                                       struct.unpack_from('<I', code, call)[0])
        if actual != kernel['vm']+0x557600:
            raise ValueError('Owner provider cast import target differs')
        verify_mapper_symbol(blob, actual, *tables[0],
                             expected=b'__ZN15OSMetaClassBase12safeMetaCastEPKS_PK11OSMetaClass')
    # The request itself is the original kernel IODMACommand receiver.
    for call, method in ((0x34E10, 'constructor'), (0x34E54, 'constructor'),
                         (0x355F0, 'generator')):
        relative, symbol = DMA_KERNEL_SYMBOLS[method]
        actual = ctor.ctor_stub_callee(blob, main, nested, base+call,
                                       struct.unpack_from('<I', code, call)[0])
        if actual != kernel['vm'] + relative:
            raise ValueError('Request DMA import target differs')
        verify_mapper_symbol(blob, actual, *tables[0], expected=symbol)
    request_vp = ctor.adrp_add_str_vptr(base+0x34E14,
                                      *struct.unpack_from('<3I', code, 0x34E14))
    other_vp = ctor.adrp_add_str_vptr(base+0x34E58,
                                    *struct.unpack_from('<3I', code, 0x34E58))
    if request_vp != other_vp or not (
        cconst['vm'] <= request_vp <= cconst['vm']+cconst['size']-168
    ):
        raise ValueError('Request DMA vtable outside own const section')
    for slot, method in ((136, 'descriptor'), (160, 'prepare')):
        relative, symbol = DMA_KERNEL_SYMBOLS[method]
        actual = ctor.read_data_pointer(blob, main, request_vp+slot)
        if actual != kernel['vm']+relative:
            raise ValueError('Inherited request DMA virtual method differs')
        verify_mapper_symbol(blob, actual, *tables[0], expected=symbol)


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
    print('EMBEDDED_INDEXED_MAPPERS=0_1_2')
    print('EMBEDDED_INPUT_BIT3_SELECTS_MAPPER_INDEX_2_OTHERWISE_0')
    print('READ_WRITE_SELECTOR_BIT3_SOURCE=OWNER_BYTE496_EQ_1_AND_OWNER_FIELD464_NULL')
    print('OWNER_BYTE496_WRITER=INITIALIZER_X2_AFTER_VIRTUAL_INIT_SUCCESS')
    print('OWNER_FIELD464_WRITER=SAFE_METACAST_OF_PROVIDER_ARGUMENT')
    print('OWNER_FIELD464_CAST_TYPE_AND_LIVE_RESULT=UNVERIFIED')
    print('READ_WRITE_OWNER_FIELDS_RUNTIME_VALUES=UNVERIFIED')
    print('EMBEDDED_INPUT_BIT3_EQUALS_INTERNAL_PRP_BIT3=UNVERIFIED')
    print('REQUEST_PARENT=ORIGINAL_KERNEL_IODMACommand')
    print('GEN_IOVM_RECEIVER=SAME_REQUEST_OBJECT')
    print('SELECTED_MAPPER_FIELD_64_CONSUMED_BY_ORIGINAL_DMA_CODE=SOURCE_VERIFIED')
    print('INHERITED_DMA_PREPARE_AND_DESCRIPTOR_METHODS=SOURCE_VERIFIED')
    print('PHYSICAL_PRP_ADDRESS_AND_MAPPER_BINDING=UNVERIFIED')
    print('LOOKUP_AND_AUXILIARY_RUNTIME_VALUES=UNVERIFIED')
    print('ACTIVE_N71_CONTROLLER_BINDING=UNVERIFIED')
    print('COMMAND_BIT13_AFTER_FILTER=CONDITIONAL')
    print('FIRST_NAND_READ_OR_DMA_ACCESS=NOT_AUTHORIZED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
