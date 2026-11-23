#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source-verify N71 storage PCI ID to original Apple embedded NVMe vtable.

Only uses owner's private original kernelcache. Personality matching is a
static candidate, never proof which iOS object was dynamically bound.
"""
from pathlib import Path
import argparse
import struct
import xml.etree.ElementTree as ET

import n71_s8000_original_ionvme_read_source_gate as READ
import n71_s8000_constructor_chain_gate as CTOR

EXPECTED_IOCLASS = 'AppleEmbeddedNVMeController'
EXPECTED_VENDOR_DEVICE_MATCH = '0x2002106b'
EXPECTED_PCI_CLASS_MATCH = '0x01800200&0xffffff00'
PHYSICAL_PCI_VENDOR_DEVICE = 0x2002106b  # previously documented physical test
MODEL_CLASS_REVISION = 0x01800201         # host test fixture; not physical proof
EMBEDDED_PARENT_CALL = 0xAA4
EMBEDDED_PARENT_CTOR = 0x31158
EMBEDDED_VPTR_SETTER = 0xAA8
VIRTUAL_METHOD_SLOT = 1440
VIRTUAL_CHOICE_SLOT = 1448
EXPECTED_EMBEDDED_VMETHOD = 0x31384
EXPECTED_EMBEDDED_CHOICE = 0x3137C
PINNED_WORDS = {
    0xAA4: 0x9400C1AD,  # AppleEmbedded constructor -> AppleNVMeController ctor
    0xAA8: 0xF00034A8,  # load embedded class vtable address
    0xAAC: 0x913EC108,
    0xAB0: 0xF9000008,  # assign embedded vtable to object
    0x31160: 0x97FFCD53, # AppleNVMeController constructor -> base ctor
    0x3137C: 0x52800020, # alternate slot1448 = true
    0x31380: 0xD65F03C0,
    0x31384: 0x52800020, # slot1440 = true
    0x31388: 0xD65F03C0,
}


def verify_words(code: bytes) -> None:
    if len(code) != READ.EXPECTED_TEXT_SIZE:
        raise ValueError('Original embedded controller code extent changed')
    for off, word in PINNED_WORDS.items():
        if struct.unpack_from('<I', code, off)[0] != word:
            raise ValueError('Original embedded controller instruction differs')


def verify_static_matching(kernelcache: bytes) -> dict:
    code, _ = READ.extract_original_ionvme(kernelcache)
    verify_words(code)
    main = CTOR.KMAP.macho_segments(kernelcache, 0)
    info = main['__PRELINK_INFO']
    raw = kernelcache[info['offset']:info['offset']+info['filesize']].rstrip(b'\0')
    root = ET.fromstring(b'<plist version="1.0">' + raw + b'</plist>')
    prelink_entries = []
    for item in root.iter('dict'):
        props = CTOR.KMAP.pairs(item)
        bundle = props.get('CFBundleIdentifier')
        if (bundle is not None and bundle.text == READ.BUNDLE and
                props.get('_PrelinkExecutableLoadAddr') is not None):
            prelink_entries.append(props)
    if len(prelink_entries) != 1:
        raise ValueError('Original IONVMeFamily personality not unique')
    personalities = prelink_entries[0].get('IOKitPersonalities')
    if personalities is None:
        raise ValueError('No original IONVMe personalities')
    matches = []
    for item in personalities.findall('dict'):
        props = CTOR.KMAP.pairs(item)
        io_class = props.get('IOClass')
        if io_class is not None and io_class.text == EXPECTED_IOCLASS:
            matches.append(props)
    if len(matches) != 1:
        raise ValueError('Original AppleEmbeddedNVMe personality not unique')
    personality = matches[0]
    if (personality.get('IOPCIMatch') is None or
            personality['IOPCIMatch'].text != EXPECTED_VENDOR_DEVICE_MATCH or
            personality.get('IOPCIClassMatch') is None or
            personality['IOPCIClassMatch'].text != EXPECTED_PCI_CLASS_MATCH):
        raise ValueError('Original embedded storage PCI matching differs')
    dev = int(EXPECTED_VENDOR_DEVICE_MATCH, 16)
    class_match, class_mask = EXPECTED_PCI_CLASS_MATCH.split('&')
    if (PHYSICAL_PCI_VENDOR_DEVICE != dev or
        (MODEL_CLASS_REVISION & int(class_mask,16)) != int(class_match,16)):
        raise ValueError('N71 observed PCI ID or class matching fixture rejected')
    load = int(prelink_entries[0]['_PrelinkExecutableLoadAddr'].text, 0)
    pre = main['__PRELINK_TEXT']
    nested = CTOR.KMAP.macho_segments(kernelcache, pre['offset'] + load-pre['vm'])
    csection = nested['__TEXT_EXEC']['sections']['__text']
    cconst = nested['__DATA_CONST']['sections']['__const']
    code_vm = csection['vm']
    call = struct.unpack_from('<I', code, EMBEDDED_PARENT_CALL)[0]
    if CTOR.bl_destination(code_vm + EMBEDDED_PARENT_CALL, call) != (code_vm+EMBEDDED_PARENT_CTOR):
        raise ValueError('Original embedded parent call target differs')
    vtable = CTOR.adrp_add_str_vptr(
        code_vm+EMBEDDED_VPTR_SETTER,
        *struct.unpack_from('<3I', code, EMBEDDED_VPTR_SETTER))
    if not (cconst['vm'] <= vtable and
            vtable + VIRTUAL_CHOICE_SLOT + 8 <= cconst['vm'] + cconst['size']):
        raise ValueError('Original embedded vtable not in own read-only data')
    method = CTOR.read_data_pointer(kernelcache, main, vtable+VIRTUAL_METHOD_SLOT)
    choice = CTOR.read_data_pointer(kernelcache, main, vtable+VIRTUAL_CHOICE_SLOT)
    if method != code_vm+EXPECTED_EMBEDDED_VMETHOD or choice != code_vm+EXPECTED_EMBEDDED_CHOICE:
        raise ValueError('Original embedded vtable method changed')
    return {'matches_original_pci_personality': True,
            'embedded_method1440_source_return': 1,
            'runtime_ios_binding_verified': False}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('private_original_kernelcache',type=Path)
    args = ap.parse_args()
    try:
        result = verify_static_matching(args.private_original_kernelcache.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error, ET.ParseError):
        print('N71_ORIGINAL_EMBEDDED_NVME_PCI_MATCH=REJECTED')
        return 1
    print('N71_ORIGINAL_EMBEDDED_NVME_PCI_MATCH=PASS')
    print('ORIGINAL_IOCLASS=AppleEmbeddedNVMeController')
    print('PHYSICAL_PCI_VENDOR_DEVICE_MATCH=106b:2002')
    print('CLASS_MATCH=ORIGINAL_MATCHED_AGAINST_HOST_FIXTURE_NOT_REMEASURED')
    print('ORIGINAL_EMBEDDED_METHOD1440_SOURCE_RETURNS=1')
    print('IOS_RUNTIME_DRIVER_BINDING_PROVEN=NO')
    print('FIRST_NAND_READ_AUTHORIZED=NO')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
