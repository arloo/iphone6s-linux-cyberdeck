#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline N71 A9 PCIe port1 controller-status bit provenance.

Statically traces a verified original Apple N71 ARM64 port1 inherited loop
through S800x root vtable 2008, the A9-specific vtable 2016 register
selector ID5, embedded root vtable 1808 32-bit read, and the AND #1
status result. It proves a relative 0x1AC offset on the original mapped
root register pointer only. The physical IODeviceMemory provider-array
ordering, actual MMIO mapping base and bit meaning remain UNKNOWN.

Never extracts/displays private original instructions, raw pointer values,
device identifiers, calibration, firmware or Apple executable content.
No device access, MMIO, DMA, clock, reset, module load or network I/O.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
def load(name:str,file:str):
    sp=importlib.util.spec_from_file_location(name,HERE/file)
    assert sp and sp.loader
    module=importlib.util.module_from_spec(sp)
    sp.loader.exec_module(module)
    return module

ROOT=load("n71_stat_root","n71_s8000_root_resource_gate.py")
PORT=load("n71_stat_port","n71_s8000_port1_inherited_sequence_gate.py")
COMMON=load("n71_stat_common","n71_s8000_common_reg_audit.py")
CTOR=load("n71_stat_ctor","n71_s8000_constructor_chain_gate.py")

class UnqualifiedStatusBit(ValueError):
    pass

def need(ok:bool,reason:str):
    if not ok:raise UnqualifiedStatusBit(reason)

def word(code:bytes,offset:int)->int:
    need(offset>=0 and offset%4==0 and offset+4<=len(code),
         "Original code register-access instruction out of bounds")
    return struct.unpack_from("<I",code,offset)[0]

def ldr_x(code:bytes,at:int,rd:int,rn:int,byte_offset:int):
    need(byte_offset%8==0 and 0<=byte_offset<32768,
         "Unexpected original root pointer field")
    insn=word(code,at)
    need(insn&0xFFC003FF==0xF9400000|(rn<<5)|rd and
         ((insn>>10)&4095)*8==byte_offset,
         "Unexpected 64-bit root PCIe pointer load")

def store_x(code:bytes,at:int,src:int,base:int,offset:int):
    need(offset%8==0 and 0<=offset<32768,
         "Unexpected A9 register-map storage field")
    insn=word(code,at)
    need(insn&0xFFC003FF==0xF9000000|(base<<5)|src and
         ((insn>>10)&4095)*8==offset,
         "Original root provider memory-map storage changed")

def verify_original_common_resource_mapping(embedded:bytes):
    """Proof: root vslot1880 -> provider vslot976 -> virtual vslot120.

    The original resource index for vslot1880 on the 4-port N71 is 9.
    Its ADT tuple correspondence remains conditional on runtime order.
    """
    ldr_x(embedded,0x1f4c,8,19,0)
    ldr_x(embedded,0x1f50,8,8,1880)
    need(word(embedded,0x1f54)==0xAA1303E0 and
         word(embedded,0x1f58)==0xD63F0100,
         "Original common resource-index selection changed")
    need(word(embedded,0x1f5c)==0xAA0003E1,
         "Computed resource index not used as provider argument")
    ldr_x(embedded,0x1f60,8,20,0)
    ldr_x(embedded,0x1f64,8,8,976)
    need(word(embedded,0x1f68)==0xAA1403E0 and
         word(embedded,0x1f6c)==0x52800002 and
         word(embedded,0x1f70)==0xD63F0100,
         "Original provider memory-map retrieval changed")
    store_x(embedded,0x1f74,0,19,416)
    need(word(embedded,0x1f78)&0xFF00001F==0xB4000000,
         "Original map availability check removed")
    ldr_x(embedded,0x1f7c,8,0,0)
    ldr_x(embedded,0x1f80,8,8,120)
    need(word(embedded,0x1f84)==0xD63F0100,
         "Original getVirtualAddress-style mapping call changed")
    store_x(embedded,0x1f88,0,19,424)

def qualify_code(shared:bytes,embedded:bytes)->dict[str,int]:
    need(len(shared)==18552 and len(embedded)==46924,
         "Unrecognized original shared/embedded A9 ARM64 code extents")
    # S800x ROOT status-query method: caller W1 is the port index.
    # Save into X2, call selector root slot2016 with ID5, then read
    # the selected offset via embedded root read32 method slot1808.
    need(word(shared,0x3c0)==0xAA0103E2,"Port index not forwarded to ID selector")
    ldr_x(shared,0x3c8,8,0,0)
    ldr_x(shared,0x3cc,8,8,2016)
    need(word(shared,0x3d0)==0x528000A1,
         "Original A9 common-register selector was not ID 5")
    need(word(shared,0x3d4)==0xD63F0100,
         "Original selector indirect call changed")
    need(word(shared,0x3d8)==0xAA0003E1,
         "Original selected offset not passed as read argument")
    ldr_x(shared,0x3dc,8,19,0)
    ldr_x(shared,0x3e0,8,8,1808)
    need(word(shared,0x3e4)==0xAA1303E0 and
         word(shared,0x3e8)==0xD63F0100,
         "Read32 method dispatch not grounded in root instance")
    need(word(shared,0x3ec)==0x12000000 and
         word(shared,0x3f8)==0xD65F03C0,
         "Original status mask must return ONLY bit 0")
    # Base EmbeddedPCIe root read32: 32-bit LOAD from pointer at
    # root-object field +424, indexed by returned byte offset in W1.
    verify_original_common_resource_mapping(embedded)
    ldr_x(embedded,0x4664,8,0,424)
    need(word(embedded,0x4668)==0xB8614913,
         "Original read32 no longer indexed by W1 zero-extended")
    need(word(embedded,0x469c)==0xAA1303E0 and
         word(embedded,0x46ac)==0xD65F03C0,
         "Original read32 no longer returns its loaded 32-bit value")
    return {"relative_byte_offset":0x12c+(1*0x80),
            "bit_mask":1, "root_virtual_status_method":2008,
            "root_register_selector_method":2016,
            "root_read32_method":1808,
            "root_mapped_pointer_field":424,
            "provider_index_for_root_common":9,
            "physical_base_verified":False,
            "bit_is_link_ready_verified":False}

def qualify_vtable_targets(original:bytes,main:dict,mods:dict):
    ptr=lambda slot:CTOR.read_data_pointer(
        original,main,mods["a9"]["vptr"]+slot)
    need(ptr(2008)==mods["shared"]["vm"]+0x3b4,
         "Original A9 root status method not inherited from S800x")
    need(ptr(2016)==mods["a9"]["vm"]+0x7d8,
         "Original A9 specialized ID-to-offset selector changed")
    need(ptr(1808)==mods["embedded"]["vm"]+0x4654,
         "Original EmbeddedPCIe register read32 method changed")

def inspect(original:bytes,adt:bytes)->dict:
    # These prior independent audits also validate N71 Apple ADT PCIe
    # regions, ctor inheritance, root resource indices and port1 call order.
    ROOT.audit(original,adt)
    shared=PORT.audited_shared_code(original)
    PORT.analyze_method(shared)
    mappings=COMMON.inspect_macho(original)
    need(len(mappings)==6 and mappings[5]==(0x12c,0x80),
         "Original A9 register ID5 port stride is not validated")
    main,mods=ROOT.auditable_root_code(original)
    ROOT.verify_root_inheritance(original,main,mods)
    qualify_vtable_targets(original,main,mods)
    result=qualify_code(mods["shared"]["code"],mods["embedded"]["code"])
    need(result["relative_byte_offset"]==0x1ac,
         "Original port1 register-relative offset calculation changed")
    return result

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("private_original_n71_arm64_macho",type=Path)
    ap.add_argument("private_original_n71_apple_adt",type=Path)
    x=ap.parse_args()
    try:
        a=x.private_original_n71_arm64_macho
        b=x.private_original_n71_apple_adt
        need(a.is_file() and not a.is_symlink() and
             1000<a.stat().st_size<=ROOT.G.KMAP.MAX_MACHO,
             "Original kernelcache not a supported private ARM64 Mach-O")
        need(b.is_file() and not b.is_symlink() and
             8<b.stat().st_size<=ROOT.ADT.ADT.MAX_FILE,
             "Original Apple ADT missing or too large")
        result=inspect(a.read_bytes(),b.read_bytes())
    except (OSError,UnicodeError,ValueError,KeyError,struct.error,
            UnqualifiedStatusBit,ROOT.G.UnqualifiedHardware,
            ROOT.G.KMAP.BadKernelcache,ROOT.ADT.RejectedADT,
            COMMON.UnverifiedCode,PORT.UnverifiedOriginalSequence) as exc:
        print("N71_A9_PORT1_STATUS_BIT_PROVENANCE_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_A9_PORT1_ORIGINAL_STATUS_REGISTER_CHAIN_STATIC_PASS")
    print("ORIGINAL_ROOT_SELECTOR_ID=5")
    print("PORT1_RELATIVE_REGISTER_OFFSET",hex(result["relative_byte_offset"]))
    print("ORIGINAL_PROVIDER_MEMORY_RESOURCE_INDEX=9")
    print("ROOT_COMMON_MAPPED_VIRTUAL_POINTER_FIELD=424")
    print("REGISTER_READ_WIDTH_BITS=32")
    print("RETURNED_STATUS_BIT_MASK",hex(result["bit_mask"]))
    print("CONTROLLER_STATUS_QUERY_POLL_BACKEDGE=VERIFIED")
    print("ROOT_POINTER_IODEVICE_MEMORY_PROVIDER_ORDER_PROVEN=NO")
    print("STATUS_BIT_PHY_OR_LINK_READY_MEANING_PROVEN=NO")
    print("SAFE_MMIO_DART1_DMA_AND_WIFI_HARDWARE_AUTHORIZED=NO")
    print("NO_PRIVATE_CODE_DUMP_NO_DEVICE_ACCESS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
