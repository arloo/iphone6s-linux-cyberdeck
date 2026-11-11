#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify original A9/S8000 ROOT PCIe resource-index formulas, offline only.

Uses an operator-owned private iOS 15.8.8 original ARM64 Mach-O and
private N71 Apple ADT. No hardware access, code export, or MMIO mapping.
The verified provider resource INDICES are not proof that AppleARMIODevice
preserves ADT reg[] ordering at runtime.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent

def import_local(module_name:str,filename:str):
    spec=importlib.util.spec_from_file_location(module_name,HERE/filename)
    assert spec and spec.loader
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

G=import_local("n71_root_ctor_util","n71_s8000_constructor_chain_gate.py")
ADT=import_local("n71_root_adt_util","n71_s8000_adt_window_gate.py")
MODS=G.MODS
ROOT_CTORS={"embedded":0x19C0,"shared":0x38,"a9":0x354}
ROOT_VPTR_AT={"embedded":0x19CC,"shared":0x44,"a9":0x360}
ROOT_START_SLOT=688
ROOT_CONFIG_SLOT=1496
MAP_CONFIG_SLOT=1856
MAP_COMMON_SLOT=1880
MAP_PHY_SLOT=1888
A9_COMMON_OFFSET_SLOT=2016

def checked_method(code:bytes,offset:int,expected:dict[int,int])->None:
    for pos,insn in expected.items():
        G.need(G.w(code,offset+pos)==insn,
               "Unexpected original ARM64 root PCIe method layout")

def ldr_from_reg(encoding:int,base_register:int,
                 target_register:int)->int:
    """Decode strictly an unsigned-offset ARM64 LDR Xd,[Xn,#imm*8]."""
    G.need(encoding & 0xFFC003FF == (
        0xF9400000 | (base_register<<5) | target_register),
        "Unrecognized register-indirect memory access")
    return ((encoding>>10)&0xFFF)*8

def root_resource_indices(num_ports:int,extra:int=0)->tuple[int,int,int]:
    G.need(num_ports==4 and 0<=extra<=1,
           "Unknown original N71 number of ports/resource index")
    # Explicit patterns verified in original linked ARM64 methods:
    # config: MOV W0,#0;RET
    # common: MOV W8,#1; BFI W8,W0,#1,#31; MOV X0,X8; RET
    # PHY: ADD W8,W19,W0,LSL#1; ADD W0,W8,#2; RET
    return (0,1+2*num_ports,2+2*num_ports+extra)

def auditable_root_code(blob:bytes)->tuple[dict,dict]:
    G.need(1000<len(blob)<=G.KMAP.MAX_MACHO,
           "Source Mach-O size not accepted")
    main=G.KMAP.macho_segments(blob,0)
    for key in ("__PRELINK_INFO","__PRELINK_TEXT","__PLK_TEXT_EXEC",
                "__PLK_DATA_CONST"):
        G.need(key in main,"Original prelinked segment missing")
    I=main["__PRELINK_INFO"]
    G.need(I["offset"]+I["filesize"]<=len(blob),
           "Original prelink metadata out of bounds")
    meta=G.KMAP.kext_metadata(
        blob[I["offset"]:I["offset"]+I["filesize"]].rstrip(b"\0"))
    P=main["__PRELINK_TEXT"]
    E=main["__PLK_TEXT_EXEC"]
    modules={}
    for label,full_name in MODS.items():
        load,length=meta[full_name]
        G.need(P["vm"]<=load and
               load-P["vm"]+length<=P["filesize"],
               "KEXT header outside trusted PRELINK_TEXT")
        nested=G.KMAP.macho_segments(blob,P["offset"]+load-P["vm"])
        sec=nested["__TEXT_EXEC"]["sections"]["__text"]
        G.need(sec["size"]==G.TEXT_LENGTHS[label] and
               E["vm"]<=sec["vm"] and
               sec["vm"]+sec["size"]<=E["vm"]+E["filesize"],
               "Unrecognized original Apple PCIe executable extent")
        code=blob[E["offset"]+sec["vm"]-E["vm"]:
                  E["offset"]+sec["vm"]-E["vm"]+sec["size"]]
        at=ROOT_VPTR_AT[label]
        vptr=G.adrp_add_str_vptr(
            sec["vm"]+at,G.w(code,at),
            G.w(code,at+4),G.w(code,at+8))
        modules[label]={"code":code,"vm":sec["vm"],
                        "nested":nested,"vptr":vptr}
    return main,modules

def verify_root_inheritance(blob:bytes,main:dict,
                            modules:dict)->None:
    a9=modules["a9"]
    common=modules["shared"]
    base=modules["embedded"]
    # A9 root constructor -> S800x root ctor via authenticated stub+GOT.
    a9_at=0x35C
    dst=G.ctor_stub_callee(
        blob,main,a9["nested"],a9["vm"]+a9_at,
        G.w(a9["code"],a9_at))
    G.need(dst==common["vm"]+ROOT_CTORS["shared"],
           "A9 root constructor does not call common S800x root ctor")
    shared_at=0x40
    dst=G.ctor_stub_callee(
        blob,main,common["nested"],common["vm"]+shared_at,
        G.w(common["code"],shared_at))
    G.need(dst==base["vm"]+ROOT_CTORS["embedded"],
           "S800x root constructor does not call Embedded root ctor")

def checked_root_start(blob:bytes,main:dict,modules:dict)->None:
    a9,shared,base=(modules[n] for n in ("a9","shared","embedded"))
    p=lambda mod,slot:G.read_data_pointer(blob,main,
                                          mod["vptr"]+slot)
    # Real A9 root has inherited S800x start, NOT the Port subclass start.
    G.need(p(a9,ROOT_START_SLOT)==shared["vm"]+0x130,
           "A9 ROOT virtual start no longer inherited from S800x")
    G.need(p(shared,ROOT_START_SLOT)==shared["vm"]+0x130,
           "S800x ROOT start method changed")
    G.need(p(base,ROOT_START_SLOT)==base["vm"]+0x1A58,
           "Embedded root start entry changed")
    # S800x original start has a class/super vtable reference, selected
    # at an offset measured from the *header*, not the instance vptr.
    t=shared["code"]
    adr=G.adrp_target(shared["vm"]+0x1EC,G.w(t,0x1EC),8)
    global_offset=ldr_from_reg(G.w(t,0x1F0),8,8)
    header=G.read_data_pointer(blob,main,adr+global_offset)
    G.need(header+16==base["vptr"],
           "Original S800x super header is not Embedded root vtable")
    target=G.read_data_pointer(blob,main,
                               header+ldr_from_reg(G.w(t,0x1F4),8,8))
    G.need(target==base["vm"]+0x1A58,
           "Original S800x start fails to dispatch to Embedded root start")
    checked_method(t,0x1F8,{
        0:0xAA1403E0, 4:0xAA1303E1, 8:0xD63F0100,
    })
    G.need(p(shared,ROOT_CONFIG_SLOT)==shared["vm"]+0x218 and
           p(a9,ROOT_CONFIG_SLOT)==a9["vm"]+0x510,
           "A9 specialized root configuration not verified")
    G.need(p(a9,A9_COMMON_OFFSET_SLOT)==a9["vm"]+0x7D8,
           "A9 six-register selector is not a real ROOT virtual method")

def verify_index_methods(blob:bytes,main:dict,modules:dict)->None:
    a9,common,base=(modules[x] for x in ("a9","shared","embedded"))
    p=lambda mod,slot:G.read_data_pointer(blob,main,
                                          mod["vptr"]+slot)
    G.need(p(a9,MAP_CONFIG_SLOT)==base["vm"]+0x2CC4,
           "PCI config resource-index-zero method changed")
    checked_method(base["code"],0x2CC4,{
        0:0x52800000,4:0xD65F03C0
    })
    G.need(p(a9,MAP_COMMON_SLOT)==common["vm"]+0xE8 and
           p(a9,MAP_PHY_SLOT)==common["vm"]+0x108,
           "Original root common/PHY index methods not inherited")
    c=common["code"]
    checked_method(c,0xE8,{
        0x00:0xA9BF7BFD,
        0x08:0x94001287,
        0x0C:0x52800028,
        0x10:0x331F7808,
        0x14:0xAA0803E0,
        0x1C:0xD65F03C0,
    })
    checked_method(c,0x108,{
        0x0C:0xAA0103F3,
        0x10:0x9400127D,
        0x14:0x0B000668,
        0x18:0x11000900,
        0x24:0xD65F03C0,
    })
    # Each calls same original port-count routine.
    a=G.bl_destination(common["vm"]+0xF0,G.w(c,0xF0))
    b=G.bl_destination(common["vm"]+0x118,G.w(c,0x118))
    G.need(a==b,"Original index formulas call different port-count methods")
    # The real A9-specialized root config first calls selector slot 1888
    # with argument 0, then maps that index through the provider's slot976.
    d=a9["code"]
    checked_method(d,0x52C,{
        0x00:0xF9400008, 0x08:0x52800001,
        0x0C:0xD63F0100, 0x10:0xAA0003E1,
        0x14:0xF9400268, 0x1C:0xAA1303E0,
        0x20:0x52800002, 0x24:0xD63F0100,
        0x28:0xF900E280,
    })
    G.need(ldr_from_reg(G.w(d,0x530),8,8)==MAP_PHY_SLOT and
           ldr_from_reg(G.w(d,0x544),8,8)==976,
           "A9 specialized PHY resource index map virtual slots changed")

def audit(kernelcache:bytes,adt:bytes)->dict:
    msg=ADT.audit_bytes(adt)
    G.need("S8000_ADT_METADATA_GATE_PASS" in msg and
           "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in msg,
           "Private N71 S8000 Apple ADT failed strict gate")
    main,modules=auditable_root_code(kernelcache)
    verify_root_inheritance(kernelcache,main,modules)
    checked_root_start(kernelcache,main,modules)
    verify_index_methods(kernelcache,main,modules)
    N=4  # independently validated by strict private ADT parser
    indices=root_resource_indices(N)
    G.need(indices==(0,9,10) and
           len(ADT.HOST_LAYOUT)==11,
           "A9 physical root resource ordering is unrecognized")
    return {"num_ports":N,"indices":indices,
            "physical_candidates":tuple(ADT.HOST_LAYOUT[i] for i in indices),
            "runtime_provider_range_order_proven":False,
            "register_semantics_verified":False,
            "dart1_dma_verified":False}

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_arm64_macho",type=Path)
    parser.add_argument("private_n71_adt",type=Path)
    args=parser.parse_args()
    try:
        G.need(0<args.private_arm64_macho.stat().st_size<=G.KMAP.MAX_MACHO,
               "Kernelcache input is too large")
        G.need(0<args.private_n71_adt.stat().st_size<=ADT.ADT.MAX_FILE,
               "ADT input is too large")
        result=audit(args.private_arm64_macho.read_bytes(),
                     args.private_n71_adt.read_bytes())
    except (OSError,G.UnqualifiedHardware,G.KMAP.BadKernelcache,
            ADT.RejectedADT,KeyError,UnicodeError,struct.error) as exc:
        print("N71_S8000_ROOT_RESOURCE_GATE_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_S8000_ROOT_START_AND_RESOURCE_FORMULAS_STATIC_PASS")
    print("ROOT_CONSTRUCTOR_CHAIN=AppleEmbeddedPCIE>AppleS800xPCIe>AppleS8000PCIe")
    print("ROOT_START_INHERITED_FROM_S800X_AND_CALLS_EMBEDDED_PARENT=YES_STATIC")
    for name,index,win in zip(("CONFIG","COMMON","PHY"),
                              result["indices"],result["physical_candidates"]):
        print("RESOURCE",name,"INDEX",index,"ADT_CANDIDATE_BASE",
              hex(win[0]),"SIZE",hex(win[1]))
    print("ADT_RESOURCE_ORDER_EQUALS_PROVIDER_ORDER_PROVEN=NO")
    print("S8000_PORT1_CLOCK_RESET_DART1_DMA_VERIFIED=NO")
    print("HARDWARE_BLOCKED: no live PCIe MMIO or native Wi-Fi association")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
