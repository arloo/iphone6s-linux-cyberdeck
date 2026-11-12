#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify original N71 Apple IODARTFamily mapper index -> S5L8960x TCR lane.

OFFLINE, fail-closed, private-input only. This static original ARM64 audit
combines version-pinned iOS15.8.8 original prelinked Mach-O DART KEXT code
with independently validated original N71/S8000 Apple Device Tree.
Only fixed public SoC metadata and high-level proof status are printed.

Proves Apple's ORIGINAL SOFTWARE routes mapper reg=0 into logical DART
stream index 0 and TCR byte lane 0. Does NOT prove PCIe requester->SID
mapping, live register state, DMA safety, TTBR/IOVA or Linux functionality.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent

def local(alias,name):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

G=local("dart_n71_ctor","n71_s8000_constructor_chain_gate.py")
ADT=local("dart_n71_adt","n71_s8000_adt_window_gate.py")
CENSUS=local("dart_n71_consumers","n71_dart1_consumer_census_gate.py")

FAMILY="com.apple.driver.IODARTFamily"
S5L="com.apple.driver.AppleS5L8960XDART"
EXPECTED_LENGTHS={FAMILY:64836,S5L:17156}
MAX_KERNEL=G.KMAP.MAX_MACHO
S5L_VPTR_SITE=0x44

# Original instruction word signatures, NOT original binary payload.
# The signatures pin a specific audited original version and fail closed
# when any relevant original control-flow/register operation changes.
FAMILY_WORDS={
    0x3b60:0xF9406800,  # get original mapper provider
    0x3b68:0xF9408D08,  # original getProperty virtual slot
    0x3b74:0xD63F0100,
    0x3bb8:0xB9400002,  # 32-bit property data
    0x3bbc:0xB9011262,  # store mapper reg into object field +272
    0x8ed4:0xF9407400,
    0x8ed8:0xB9411261,  # read same logical mapper index
    0x8ee0:0xF942C108,  # call controller virtual slot 1408
    0x8ee8:0x52800022,  # enable=1
    0x8eec:0xD63F0100,
    0x9b74:0xB9411261,  # same index on disable path
    0x9b7c:0xF942C108,
    0x9b80:0x52800002,  # enable=0
    0x9b84:0xD63F0100,
}
S5L_WORDS={
    0x1a20:0xAA0203F5,  # save flag
    0x1a24:0xAA0103F4,  # retain logical stream index
    0x1a34:0x34000175,  # conditional path
    0x1a38:0xF9436508,  # virtual slot 1736
    0x1a40:0xAA1403E1,  # pass unchanged stream index
    0x1a44:0xD63F0100,
    0x1c14:0x7100103F,  # CMP W1, #4
    0x1c18:0x54000302,  # reject >=4
    0x1c1c:0xAA0103F4,  # retain stream index
    0x1c30:0xF9456A68,  # DART register mapping field
    0x1c34:0xB9400D09,  # read packed TCR register at +0xC
    0x1c3c:0x910063E9,  # stack-based packed four-byte TCR copy
    0x1c40:0x3874492A,  # choose byte at offset logical stream
    0x1c44:0x3219014A,  # set bit7 of selected byte
    0x1c48:0x3834492A,  # write same selected byte to copy
    0x1c54:0xB9000D0A,  # write packed TCR at +0xC
    0x1c58:0xB9400D08,  # readback
}

class RejectedDARTProvenance(ValueError):
    pass

def must(ok:bool,reason:str)->None:
    if not ok:raise RejectedDARTProvenance(reason)

def word(code:bytes,offset:int)->int:
    must(0<=offset<=len(code)-4 and offset%4==0,
         "Original DART executable instruction outside region")
    return struct.unpack_from("<I",code,offset)[0]

def check_pinned_instructions(family:bytes,s5l:bytes)->None:
    must(len(family)==EXPECTED_LENGTHS[FAMILY] and
         len(s5l)==EXPECTED_LENGTHS[S5L],
         "Original Apple DART KEXT executable lengths differ")
    for at,expected in FAMILY_WORDS.items():
        must(word(family,at)==expected,
             "Original IODARTFamily mapper field/control path changed")
    for at,expected in S5L_WORDS.items():
        must(word(s5l,at)==expected,
             "Original S5L DART per-stream TCR path changed")

def extract_original_modules(blob:bytes):
    must(1000<len(blob)<=MAX_KERNEL,"Original kernelcache size unsupported")
    main=G.KMAP.macho_segments(blob,0)
    for required in ("__PRELINK_TEXT","__PRELINK_INFO",
                     "__PLK_TEXT_EXEC","__PLK_DATA_CONST"):
        must(required in main,"Original prelinked kernel segment missing")
    pre=main["__PRELINK_TEXT"]
    ex=main["__PLK_TEXT_EXEC"]
    info=main["__PRELINK_INFO"]
    must(info["offset"]+info["filesize"]<=len(blob),
         "Prelink info is truncated")
    raw=blob[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0")
    must(0<len(raw)<=G.KMAP.MAX_PRELINK_XML and raw.startswith(b"<dict>"),
         "Original kernelcache prelink metadata format unsupported")
    try:
        root=ET.fromstring(b'<plist version="1.0">'+raw+b'</plist>')
    except ET.ParseError as exc:
        raise RejectedDARTProvenance("Malformed original prelink metadata") from exc
    out={}
    for entry in root.iter("dict"):
        fields=G.KMAP.pairs(entry)
        tag=fields.get("CFBundleIdentifier")
        if tag is None or tag.tag!="string" or tag.text not in EXPECTED_LENGTHS:
            continue
        name=tag.text
        must(name not in out,"Duplicate original DART KEXT")
        load_tag=fields.get("_PrelinkExecutableLoadAddr")
        size_tag=fields.get("_PrelinkExecutableSize")
        must(load_tag is not None and size_tag is not None,
             "Original Apple DART metadata incomplete")
        try:
            load=int(load_tag.text or "",0)
            size=int(size_tag.text or "",0)
        except (ValueError,TypeError) as exc:
            raise RejectedDARTProvenance("Malformed Apple KEXT extent") from exc
        must(pre["vm"]<=load and load-pre["vm"]+size<=pre["filesize"],
             "Original DART header outside original prelink bounds")
        base=pre["offset"]+load-pre["vm"]
        nested=G.KMAP.macho_segments(blob,base)
        must(nested["__TEXT"]["vm"]==load and
             nested["__TEXT"]["filesize"]==size,
             "Original DART Mach-O metadata mismatch")
        sec=nested["__TEXT_EXEC"]["sections"]["__text"]
        must(sec["size"]==EXPECTED_LENGTHS[name] and sec["size"]%4==0 and
             ex["vm"]<=sec["vm"] and
             sec["vm"]+sec["size"]<=ex["vm"]+ex["filesize"],
             "Original Apple DART native text unqualified")
        file_offset=ex["offset"]+sec["vm"]-ex["vm"]
        code=blob[file_offset:file_offset+sec["size"]]
        must(len(code)==sec["size"],"Original DART ARM64 bytes incomplete")
        out[name]={"code":code,"vm":sec["vm"],"nested":nested,
                   "base":base}
    must(set(out)==set(EXPECTED_LENGTHS),"Expected original DART KEXT pair absent")
    return main,out

def verify_original_code(blob:bytes)->None:
    main,mods=extract_original_modules(blob)
    i=mods[FAMILY];h=mods[S5L]
    check_pinned_instructions(i["code"],h["code"])
    # Explicitly check that 'reg' is the original Apple property
    # referenced by the pinned IODARTFamily getter, not an arbitrary
    # 32-bit value or guessed child mapper SID.
    cs=i["nested"]["__TEXT"]["sections"]["__cstring"]
    reg_va=G.adrp_target(i["vm"]+0x3b6c,word(i["code"],0x3b6c),1)
    add=word(i["code"],0x3b70)
    must((add&0xFFC003FF)==0x91000021,
         "Original Apple mapper property literal not loaded")
    reg_va+=((add>>10)&0xfff)
    must(cs["vm"]<=reg_va and reg_va+4<=cs["vm"]+cs["size"],
         "Original mapper field getter is not cstring-backed")
    offset=i["base"]+cs["offset"]+reg_va-cs["vm"]
    must(blob[offset:offset+4]==b"reg\0",
         "Original field key differs from Apple ADT 'reg'")
    # Actual AppleS5L8960XDART object constructor sets the
    # constructed vtable, not a MetaClass vtable.
    vp=G.adrp_add_str_vptr(
        h["vm"]+S5L_VPTR_SITE,word(h["code"],S5L_VPTR_SITE),
        word(h["code"],S5L_VPTR_SITE+4),
        word(h["code"],S5L_VPTR_SITE+8))
    for slot,local in ((1408,0x1a10),(1736,0x1c00)):
        fn=G.read_data_pointer(blob,main,vp+slot)
        must(fn==h["vm"]+local,
             "Actual constructed S5L DART vtable stream route changed")

def verify_original(arm64_macho:bytes,original_adt:bytes)->dict[str,int]:
    # Existing complete ADT gate verifies unique WLAN-DART1 mapper
    # and no direct/secondary declared DART1 consumers.
    count=CENSUS.audit_bytes(original_adt)
    must(count["dart1_mapper_declared_consumers"]==1 and
         count["dart1_child_nodes"]==1 and
         count["dart1_direct_controller_consumers"]==0,
         "Original N71 DART1 topology unqualified")
    # This property is an Apple mapper logical index, not a complete
    # Linux IOMMU/RID/SID hardware routing guarantee.
    mapping=[]
    ADT.ADT.parse_node(original_adt,0,"",
        visitor=lambda path,props: mapping.append(props.get("reg"))
        if path==ADT.MAPPER else None,visit_all=True)
    must(len(mapping)==1 and mapping[0] is not None and
         len(mapping[0])==4 and
         struct.unpack("<I",mapping[0])[0]==0,
         "Unexpected original N71 DART1 mapper logical index")
    verify_original_code(arm64_macho)
    return {"mapper_index":0,"tcr_byte_lane":0,"tcr_register_offset":0xc,
            "hardware_stream_count_upper_bound":4}

def private_bytes(path:Path,max_size:int)->bytes:
    must(path.is_file() and not path.is_symlink(),
         "Private input missing or symlink")
    size=path.stat().st_size
    must(8<size<=max_size,"Original input size rejected")
    return path.read_bytes()

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_original_n71_kernelcache_macho",type=Path)
    p.add_argument("private_original_n71_apple_adt",type=Path)
    args=p.parse_args()
    try:
        result=verify_original(
            private_bytes(args.private_original_n71_kernelcache_macho,
                          MAX_KERNEL),
            private_bytes(args.private_original_n71_apple_adt,
                          ADT.ADT.MAX_FILE))
    except Exception:
        print("N71_ORIGINAL_DART_MAPPER_TCR_LANE_FAIL_CLOSED",file=sys.stderr)
        return 1
    print("N71_ORIGINAL_APPLE_DART_MAPPER_TO_TCR_LANE_STATIC_PASS")
    print("ORIGINAL_IODARTFAMILY_MAPPER_REG_TO_FIELD_AND_DISPATCH=VERIFIED")
    print("ORIGINAL_S5L_DART_VTABLE_DISPATCH_TO_TCR_BYTE_LANE=VERIFIED")
    print("WLAN_DART1_APPLE_LOGICAL_MAPPER_INDEX",result["mapper_index"])
    print("ORIGINAL_S5L_TCR_BYTE_LANE",result["tcr_byte_lane"])
    print("ORIGINAL_S5L_TCR_RELATIVE_OFFSET",hex(result["tcr_register_offset"]))
    print("ORIGINAL_S5L_HARDWARE_STREAM_INDICES",0,1,2,3)
    print("ACTUAL_PCIE_REQUESTER_TO_SID_ROUTING_PROVEN=NO")
    print("DART1_LIVE_TTBR_IOVA_DMA_ISOLATION_PROVEN=NO")
    print("HARDWARE_MMIO_GPIO_RESET_AND_LINUX_WIFI_AUTHORIZED=NO")
    print("PROPRIETARY_OR_PRIVATE_ORIGINAL_PAYLOAD_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
