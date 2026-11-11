#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed A9 PCIe PHY selector-ARGUMENT-zero mapping evidence gate.

Inspects only a locally owned decompressed iOS 15.8.8 ARM64 Mach-O and
private Apple ADT. Does NOT touch MMIO, export firmware, imply a safe common
register base or prove the actual Apple IODeviceMemory resource ordering.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent

def load(name: str, file: str):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

KMAP=load("n71_kext_map_for_phy", "n71_kernelcache_pcie_kext_map.py")
ADT_GATE=load("n71_adt_gate_for_phy", "n71_s8000_adt_window_gate.py")
SHARED="com.apple.driver.AppleS800xPCIe"
SPECIAL="com.apple.driver.AppleS8000PCIe"
EMBEDDED="com.apple.driver.AppleEmbeddedPCIE"

class MappingNotVerified(ValueError):
    pass

def require(ok:bool, reason:str)->None:
    if not ok:raise MappingNotVerified(reason)

# Relative-to-function code offsets are pinned to original iOS 15.8.8.
# Comparison validates only ordinary ARM64 instruction encodings for
# index=0, a virtual map call, and three field-storage operations.
# These bytes are NOT extracted or published by this tool.
SHARED_AT=0x268
SPECIAL_AT=0x534
EXPECTED={
    0x00:0x52800001, # MOV W1,0: VIRTUAL SELECTOR ARGUMENT, NOT resource index
    0x04:0xd63f0100, # BLR X8
    0x08:0xaa0003e1, # MOV X1,X0
    0x0c:0xf9400268, # LDR X8,[X19]
    0x10:0xf941e908, # LDR X8,[X8,#976]
    0x14:0xaa1303e0, # MOV X0,X19
    0x18:0x52800002, # MOV W2,0: mapping options
    0x1c:0xd63f0100,
    0x20:0xf900e280, # Store map at object +448
    0x28:0xf9400008,
    0x2c:0xf9403d08,
    0x30:0xd63f0100,
    0x34:0xf900e680, # Store virtual mapping at object +456
    0x38:0xf940e280,
    0x40:0xf900ea80, # Store helper-derived value at object +464
}

def validated_resource_zero_sequence(blob:bytes, at:int) -> bool:
    require(at>=0 and at+0x44<=len(blob),"Pinned ARM64 sequence truncated")
    for rel,wanted in EXPECTED.items():
        actual=struct.unpack_from("<I",blob,at+rel)[0]
        require(actual==wanted,
                "Pinned PHY resource-0 mapping instruction sequence changed")
    conditional=struct.unpack_from("<I",blob,at+0x24)[0]
    require((conditional&0xff00001f)==0xb4000000,
            "Missing map-null fail-closed check")
    call=struct.unpack_from("<I",blob,at+0x3c)[0]
    require((call&0xfc000000)==0x94000000,
            "Missing helper call after virtual mapping")
    return True

# Original AppleEmbeddedPCIE::start obtains two further memory-resource
# indices through distinct virtual methods, then maps each using the
# provider's resource-index API. Their NUMERIC VALUES ARE NOT recovered
# here: silently equating them with ADT reg[9]/reg[10] is forbidden.
DYNAMIC_COMMON_SELECTORS=(
    (0x1ed8, 0xf943a108, 0xf9005a60),  # core dynamic selector 1
    (0x1f4c, 0xf943ad08, 0xf900d260),  # core dynamic selector 2
)

def validated_dynamic_common_sequences(code:bytes)->int:
    for start, virtual_selector, store in DYNAMIC_COMMON_SELECTORS:
        require(0<=start and start+44<=len(code),
                "Truncated dynamically selected common-resource mapping")
        expected={
            0x00:0xf9400268,      # LDR X8,[X19] root object
            0x04:virtual_selector,
            0x08:0xaa1303e0,
            0x0c:0xd63f0100,      # BLR X8; X0 is dynamic resource index
            0x10:0xaa0003e1,
            0x14:0xf9400288,      # LDR X8,[X20] provider
            0x18:0xf941e908,      # LDR X8,[X8,#976] mapWithIndex
            0x1c:0xaa1403e0,
            0x20:0x52800002,      # options=0
            0x24:0xd63f0100,
            0x28:store,
        }
        for delta,insn in expected.items():
            require(struct.unpack_from("<I",code,start+delta)[0]==insn,
                    "Unexpected dynamically selected common-resource code")
    return len(DYNAMIC_COMMON_SELECTORS)

def module_text(macho:bytes, module:str)->tuple[bytes,bytes]:
    main=KMAP.macho_segments(macho,0)
    for seg in ("__PRELINK_INFO","__PRELINK_TEXT","__PLK_TEXT_EXEC"):
        require(seg in main,"Missing private Mach-O prelink segment")
    inf,pre,exe=(main[x] for x in
                 ("__PRELINK_INFO","__PRELINK_TEXT","__PLK_TEXT_EXEC"))
    require(inf["offset"]+inf["filesize"]<=len(macho),
            "Prelink metadata beyond end")
    meta=KMAP.kext_metadata(
        macho[inf["offset"]:inf["offset"]+inf["filesize"]].rstrip(b"\0"))
    load,extent=meta[module]
    require(pre["vm"]<=load and
            load-pre["vm"]+extent<=pre["filesize"],
            "KEXT Mach-O outside PRELINK_TEXT")
    kext=KMAP.macho_segments(macho,pre["offset"]+load-pre["vm"])
    sec=kext.get("__TEXT_EXEC",{}).get("sections",{}).get("__text")
    label=kext.get("__TEXT",{}).get("sections",{}).get("__cstring")
    require(sec is not None and label is not None,
            "Missing bounded code/string sections")
    require(sec["size"] in (18552,2928,46924),
            "Unexpected original Apple PCIe module size")
    require(exe["vm"]<=sec["vm"] and
            sec["vm"]-exe["vm"]+sec["size"]<=exe["filesize"],
            "PCIe KEXT text outside coalesced code")
    require(pre["vm"]<=label["vm"] and
            label["vm"]-pre["vm"]+label["size"]<=pre["filesize"],
            "KEXT strings outside PRELINK_TEXT")
    codeoff=exe["offset"]+sec["vm"]-exe["vm"]
    labeloff=pre["offset"]+label["vm"]-pre["vm"]
    return (macho[codeoff:codeoff+sec["size"]],
            macho[labeloff:labeloff+label["size"]])

def audit(macho:bytes, private_adt:bytes)->dict[str,object]:
    require(1000<len(macho)<=KMAP.MAX_MACHO,"Mach-O input not bounded")
    adt_check=ADT_GATE.audit_bytes(private_adt)
    require("S8000_ADT_METADATA_GATE_PASS" in adt_check and
            "HARDWARE_BLOCKED" in adt_check,
            "S8000 private ADT did not pass strict safety audit")
    common,slabels=module_text(macho,SHARED)
    a9,alabels=module_text(macho,SPECIAL)
    embedded,_=module_text(macho,EMBEDDED)
    require(len(common)==18552 and len(a9)==2928 and len(embedded)==46924,
            "Expected original PCIe KEXT size mismatch")
    require(b"apcie-phy-tunables\0" in slabels and
            b"_phyRegistersMemoryMap" in slabels and
            b"PCIe PHY\0" in alabels,
            "Original A9 PHY resource labels are missing")
    validated_resource_zero_sequence(common,SHARED_AT)
    validated_resource_zero_sequence(a9,SPECIAL_AT)
    dynamic_count=validated_dynamic_common_sequences(embedded)
    first=ADT_GATE.HOST_LAYOUT[0]
    require(first==(0x610000000,0x1000000),
            "Unexpected ADT first PCIe physical window")
    # The discovered resource index is not a proof that the driver's
    # IODeviceMemory array has the *same order* as the raw ADT reg array.
    return {"mapped_index":0,
            "source_modules":3,
            "common_dynamic_selectors":dynamic_count,
            "adt_first_base":first[0],
            "adt_first_length":first[1],
            "common_base_proven":False,
            "provider_index_order_proven":False}

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_macho",type=Path)
    parser.add_argument("private_adt",type=Path)
    a=parser.parse_args()
    try:
        require(0<a.private_macho.stat().st_size<=KMAP.MAX_MACHO,
                "Image too large")
        require(0<a.private_adt.stat().st_size<=ADT_GATE.ADT.MAX_FILE,
                "ADT too large")
        report=audit(a.private_macho.read_bytes(),a.private_adt.read_bytes())
    except (MappingNotVerified,KMAP.BadKernelcache,ADT_GATE.RejectedADT,
            OSError,KeyError,UnicodeError,struct.error) as exc:
        print("A9_PHY_RESOURCE_GATE_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("A9_PHY_RESOURCE0_MAPPING_INSTRUCTIONS_PASS: both original A9 PCIe modules")
    print("VIRTUAL_SELECTOR_ARGUMENT",report["mapped_index"])
    print("MAPPED_PROVIDER_RESOURCE_INDEX_NOT_DERIVED_BY_THIS_TOOL")
    print("SEE_N71_S8000_ROOT_RESOURCE_GATE_FOR_VERIFIED_INDEX_10")
    print("ADT_REG0_ECAM_WINDOW_NOT_PHY",hex(report["adt_first_base"]),
          "size",hex(report["adt_first_length"]))
    print("OTHER_COMMON_MMIO_RESOURCE_SELECTORS_DYNAMIC",
          report["common_dynamic_selectors"])
    print("PROVIDER_RESOURCE_ORDER_CONFIRMED=NO")
    print("COMMON_REGISTER_BASE_CONFIRMED=NO")
    print("HARDWARE_BLOCKED: no live MMIO, PCIe reset, DMA, firmware or radio action")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
