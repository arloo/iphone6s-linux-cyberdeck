#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static vtable-return classifier for the original N71/S8000 Apple PCIe code.

This READ-ONLY auditor is pinned to the operator's already-decompressed
iOS 15.8.8 N71 arm64 kernelcache. It never executes a method, maps device
memory, prints internal pointers, or exports proprietary executable bytes.
A vtable entry found in a constructor does not prove that the constructed
object reaches a particular runtime dispatch site.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location(
    "n71_kext_map_for_vtable",HERE/"n71_kernelcache_pcie_kext_map.py")
assert spec and spec.loader
KMAP=importlib.util.module_from_spec(spec)
spec.loader.exec_module(KMAP)

SPECIAL="com.apple.driver.AppleS8000PCIe"
SHARED="com.apple.driver.AppleS800xPCIe"
CORE="com.apple.iokit.IOPCIFamily"
SLOTS=(1856,1880)
UNSUPPORTED=0xE00002C7

class VtableAuditBlocked(ValueError):
    pass

def require(ok:bool,reason:str)->None:
    if not ok: raise VtableAuditBlocked(reason)

def signed(v:int,bits:int)->int:
    return v-(1<<bits) if v & (1<<(bits-1)) else v

def calculate_vtable(pc:int,adrp:int,add:int,store:int)->int:
    """Decode generic ADRP X8; ADD X8,X8,#imm; STR X8,[X0]."""
    require(adrp&0x9f00001f==0x90000008,
            "Unexpected constructor ADRP register or instruction")
    require(add&0xffc003ff==0x91000108,
            "Unexpected constructor ADD register or instruction")
    require(store==0xf9000008,
            "Constructor does not assign selected vtable to object")
    immhi=(adrp>>5)&0x7ffff
    immlo=(adrp>>29)&3
    pages=signed((immhi<<2)|immlo,21)
    shift=(add>>22)&3
    require(shift in (0,1),"Invalid ADD displacement encoding")
    result=(pc&~4095)+(pages<<12)+(
        ((add>>10)&0xfff)<<(12 if shift else 0))
    require(result>=0 and result%8==0,"Invalid vtable pointer")
    return result

def classify_direct_return(code:bytes)->str:
    """Classify only two exact constant-return patterns; never emulate."""
    if code[:8]==struct.pack("<2I",0xd2800000,0xd65f03c0):
        return "constant_zero"
    if code[:12]==struct.pack(
        "<3I",0x528058e0,0x72bc0000,0xd65f03c0):
        return "iokit_unsupported_status"
    return "not_an_established_constant"

def inspect(macho:bytes)->dict[str,object]:
    require(1000<len(macho)<=KMAP.MAX_MACHO,"Input size rejected")
    main=KMAP.macho_segments(macho,0)
    for name in ("__PRELINK_INFO","__PRELINK_TEXT","__PLK_TEXT_EXEC",
                 "__PLK_DATA_CONST"):
        require(name in main, "Mandatory prelinked section missing")
    info=main["__PRELINK_INFO"]
    require(info["offset"]+info["filesize"]<=len(macho),
            "Prelink metadata out of bounds")
    metadata=KMAP.kext_metadata(
        macho[info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0"))
    bounds=KMAP.map_pcie_kexts(macho)
    pre=main["__PRELINK_TEXT"]
    exe=main["__PLK_TEXT_EXEC"]
    data=main["__PLK_DATA_CONST"]
    groups={}
    for mod,expected in ((SPECIAL,2928),(SHARED,18552)):
        load,sz=metadata[mod]
        require(load>=pre["vm"] and
                load-pre["vm"]+sz<=pre["filesize"],
                "Original KEXT header outside prelinked text")
        nested=KMAP.macho_segments(macho,pre["offset"]+load-pre["vm"])
        sec=nested["__TEXT_EXEC"]["sections"]["__text"]
        require(sec["size"]==expected,"Unexpected pinned original text length")
        require(sec["vm"]>=exe["vm"] and
                sec["vm"]-exe["vm"]+expected<=exe["filesize"],
                "Original KEXT body outside executable region")
        begin=exe["offset"]+sec["vm"]-exe["vm"]
        adrp,add,store=struct.unpack_from("<3I",macho,begin+0x20)
        vt=calculate_vtable(sec["vm"]+0x20,adrp,add,store)
        require(vt>=data["vm"] and vt+max(SLOTS)+8<=data["vm"]+data["filesize"],
                "Constructed vtable outside the private read-only data")
        categories={}
        for slot in SLOTS:
            ptr=struct.unpack_from("<Q",macho,
                data["offset"]+vt-data["vm"]+slot)[0]
            kind=next((name for name,lo,size in bounds
                       if lo<=ptr<lo+size),None)
            require(kind is not None,
                    "Selected virtual entry is outside allowlisted PCIe code")
            # Only decode first 12 instructions bytes via a bounded mapping;
            # never print or save pointers, native code or disassembly.
            require(exe["vm"]<=ptr and
                    ptr+12<=exe["vm"]+exe["filesize"],
                    "Selected virtual method outside executable map")
            raw=macho[exe["offset"]+ptr-exe["vm"]:
                      exe["offset"]+ptr-exe["vm"]+12]
            categories[slot]=(kind,classify_direct_return(raw))
        groups[mod]=categories
    special=groups[SPECIAL]
    shared=groups[SHARED]
    require(special[1856]==(CORE,"constant_zero"),
            "Original S8000 root slot1856 cannot be verified")
    require(special[1880]==(CORE,"iokit_unsupported_status"),
            "Original S8000 root slot1880 cannot be verified")
    require(shared[1856][1]=="not_an_established_constant",
            "Unexpected shared root slot1856 classification")
    require(shared[1880][1]!="iokit_unsupported_status",
            "Shared root slot1880 unexpectedly matches S8000 default error")
    return {
      "s8000_root_slot_1856":special[1856][1],
      "s8000_root_slot_1880":special[1880][1],
      "shared_root_slot_1856":shared[1856][1],
      "shared_root_slot_1880":shared[1880][1],
      "unsupported_status":UNSUPPORTED,
      "dispatch_site_bound_to_constructor":False,
      "root_common_mmio_indices":None,
    }

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_decompressed_macho",type=Path)
    a=p.parse_args()
    try:
        require(0<a.private_decompressed_macho.stat().st_size<=KMAP.MAX_MACHO,
                "Input too large")
        result=inspect(a.private_decompressed_macho.read_bytes())
    except (OSError,KMAP.BadKernelcache,VtableAuditBlocked,
            struct.error,KeyError,UnicodeError) as exc:
        print("S8000_VTABLE_SELECTOR_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("S8000_VTABLE_SELECTOR_STATIC_AUDIT_PASS")
    print("S8000_CTOR_SLOT_1856",result["s8000_root_slot_1856"])
    print("S8000_CTOR_SLOT_1880",result["s8000_root_slot_1880"])
    print("S800X_CTOR_SLOT_1856",result["shared_root_slot_1856"])
    print("S800X_CTOR_SLOT_1880",result["shared_root_slot_1880"])
    print("SLOT_1880_CONSTANT_EQUALS_kIOReturnUnsupported",hex(UNSUPPORTED))
    print("RUNTIME_DISPATCH_OBJECT_PROVEN=NO")
    print("COMMON_MMIO_RESOURCE_INDEX_RESOLVED=NO")
    print("HARDWARE_BLOCKED: no physical PCIe MMIO, DMA, reset or link activity")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
