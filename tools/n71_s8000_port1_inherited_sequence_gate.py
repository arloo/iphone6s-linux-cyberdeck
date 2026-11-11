#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, version-pinned original A9 S800x PCIe PORT call-order audit.

Decodes a bounded original iOS N71 kernelcache ARM64 method inherited by
the S8000 port 1. Validates the ordered virtual dispatch sites, port-index
argument provenance, repeated bounded query back-edge and two calls to the
same delay-like target. Virtual slot numbers are NOT hardware register
offsets or proof of PHY/clock/reset semantics.

No executable bytes, private addresses, raw Apple disassembly, firmware,
calibration, or device-unique values are written or printed. No devices.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
def get_tool(alias:str,name:str):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

KMAP=get_tool("n71_port_sequence_kmap","n71_kernelcache_pcie_kext_map.py")
CTOR=get_tool("n71_port_sequence_ctor","n71_s8000_constructor_chain_gate.py")

SHARED_ID="com.apple.driver.AppleS800xPCIe"
SHARED_TEXT_LENGTH=18552
METHOD_START=0x121c
METHOD_END=0x1420

# First instruction, port index in W1, vtable owner, slot, optional W2, call.
ROOT_CALLS=(
 (0x1230,0,0x1234,0x1238,0x123c,1968,0x1240,1,0x1244),
 (0x1248,19,0x124c,0x1250,0x1254,1984,0x1258,1,0x125c),
 (0x127c,19,0x1280,0x1284,0x1288,2008,None,None,0x128c),
 (0x1294,19,0x1298,0x129c,0x12a0,1992,0x12a4,0,0x12a8),
 (0x12d4,19,0x12d8,0x12dc,0x12e0,1968,0x12e4,0,0x12e8),
)
OTHER_PORT_VTABLE_CALLS=(
 (0x126c,1528),
 (0x12f0,1864),
 (0x1300,1504),
 (0x1318,1848),
 (0x137c,1568),
 (0x13b8,2016),
 (0x13ec,2016),
)

class UnverifiedOriginalSequence(ValueError):
    pass

def need(ok:bool,reason:str)->None:
    if not ok:raise UnverifiedOriginalSequence(reason)

def word(code:bytes,off:int)->int:
    need(METHOD_START<=off<METHOD_END and off%4==0 and
         off+4<=len(code),"Unexpected original method instruction boundary")
    return struct.unpack_from("<I",code,off)[0]

def check_load(code:bytes,off:int,register_width:int,
               dest:int,base:int,offset:int)->None:
    require_base=0xF9400000 if register_width==64 else 0xB9400000
    unit=8 if register_width==64 else 4
    need(0<=offset<4096*unit and offset%unit==0,
         "Original ARM64 immediate out of bounds")
    mask=0xFFC003FF
    expected=require_base | (base<<5) | dest
    opcode=word(code,off)
    need(opcode & mask==expected and
         ((opcode>>10)&0xfff)*unit==offset,
         "Original port/controller object field load changed")

def movz_w(code:bytes,off:int,reg:int,value:int)->None:
    need(0<=value<65536 and
         word(code,off)==0x52800000 | (value<<5) | reg,
         "Original virtual-call immediate changed")

def blr_reg(code:bytes,off:int,reg:int)->None:
    need(word(code,off)==0xD63F0000 | (reg<<5),
         "Original virtual method dispatch register changed")

def target_branch(code:bytes,off:int,kind:str,reg:int|None=None)->int:
    instruction=word(code,off)
    if kind=="bl":
        need(instruction&0xFC000000==0x94000000,
             "Expected bounded direct BL call")
        value=instruction&0x3ffffff
        if value&(1<<25):value-=1<<26
        return off+4*value
    need(kind in ("cbz","cbnz") and reg is not None,"Unknown conditional")
    head=0x34000000 if kind=="cbz" else 0x35000000
    need(instruction&0x7F00001F==head|reg,
         "Expected original conditional branch type/register")
    value=(instruction>>5)&0x7ffff
    if value&(1<<18):value-=1<<19
    return off+4*value

def analyze_method(code:bytes)->dict:
    need(len(code)==SHARED_TEXT_LENGTH,
         "Not the exact bounded N71 S800x PCIe executable section")
    need(word(code,METHOD_START)==0xD100C3FF and
         word(code,METHOD_END-4)==0xD65F03C0,
         "Unexpected inherited S800x method boundary")
    for (obj,root_reg,idx,vptr,virt,slot,val_off,val,call) in ROOT_CALLS:
        check_load(code,obj,64,0,root_reg,2904)
        check_load(code,idx,32,1,19,168)
        check_load(code,vptr,64,8,0,0)
        check_load(code,virt,64,8,8,slot)
        if val_off is not None:
            movz_w(code,val_off,2,val)
        blr_reg(code,call,8)
    # A second optional controller call; it reuses the x0 root object
    # obtained at offset 0x12ac, not an out-of-range alternative base.
    check_load(code,0x12ac,64,0,19,2904)
    check_load(code,0x12b8,32,1,19,168)
    check_load(code,0x12bc,64,8,0,0)
    check_load(code,0x12c0,64,8,8,2000)
    movz_w(code,0x12c4,2,1)
    blr_reg(code,0x12c8,8)
    for site,slot in OTHER_PORT_VTABLE_CALLS:
        check_load(code,site,64,8,8,slot)
    need(target_branch(code,0x1290,"cbz",0)==0x127c,
         "Status-query retry back-edge no longer matches original")
    need(target_branch(code,0x12b4,"cbz",8)==0x12cc,
         "Original optional controller-call skip changed")
    need(target_branch(code,0x1310,"cbnz",8)==0x1328,
         "Original optional port-method skip changed")
    # Exactly the same original direct-call target, with two different
    # sources of the argument: a constant 100 and object field at +416.
    movz_w(code,0x1260,0,100)
    check_load(code,0x12cc,32,0,19,416)
    wait_constant_target=target_branch(code,0x1264,"bl")
    wait_dynamic_target=target_branch(code,0x12d0,"bl")
    need(wait_constant_target==wait_dynamic_target and
         wait_constant_target>=SHARED_TEXT_LENGTH,
         "Original two delay-like calls changed identity")
    return {
        "port_index_field_bytes":168,
        "root_reference_field_bytes":2904,
        "root_virtual_slots_in_program_order":(1968,1984,2008,1992,2000,1968),
        "controller_status_query_poll_retries_to_self":True,
        "controller_status_query_caller_timeout_proven":False,
        "conditional_controller_calls":2,
        "fixed_callback_argument":100,
        "dynamic_callback_argument_field":416,
        "two_calls_same_callback":True,
        "hardware_register_meanings_proven":False,
        "safe_for_writes_or_dma":False,
    }

def audited_shared_code(blob:bytes)->bytes:
    need(1000<len(blob)<=KMAP.MAX_MACHO,
         "Original private A9 Mach-O file outside expected bounds")
    parent=CTOR.audit(blob)
    need(parent["non_port3_parent_method_fallback"] and
         parent["a9_changed_vtable_slots"]==CTOR.EXPECTED_CHANGED,
         "A9 port1-to-inherited shared virtual method not verified")
    segments=KMAP.macho_segments(blob,0)
    for section in ("__PRELINK_TEXT","__PRELINK_INFO","__PLK_TEXT_EXEC"):
        need(section in segments,"Missing original prelinked KEXT evidence")
    pre,info,exe=(segments[k] for k in (
        "__PRELINK_TEXT","__PRELINK_INFO","__PLK_TEXT_EXEC"))
    met=KMAP.kext_metadata(blob[
        info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\x00"))
    va,size=met[SHARED_ID]
    need(pre["vm"]<=va and va-pre["vm"]+size<=pre["filesize"],
         "Original S800x Mach-O extent invalid")
    nested=KMAP.macho_segments(blob,pre["offset"]+va-pre["vm"])
    section=nested["__TEXT_EXEC"]["sections"]["__text"]
    need(section["size"]==SHARED_TEXT_LENGTH and
         exe["vm"]<=section["vm"] and
         section["vm"]+section["size"]<=exe["vm"]+exe["filesize"],
         "Original shared executable changed")
    start=exe["offset"]+section["vm"]-exe["vm"]
    return blob[start:start+section["size"]]

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_decompressed_original_n71_macho",type=Path)
    x=p.parse_args()
    try:
        size=x.private_decompressed_original_n71_macho.stat().st_size
        need(1000<size<=KMAP.MAX_MACHO,"Private input size unreasonable")
        code=audited_shared_code(
            x.private_decompressed_original_n71_macho.read_bytes())
        result=analyze_method(code)
    except (OSError,ValueError,KeyError,struct.error,UnicodeError,
            KMAP.BadKernelcache,CTOR.UnqualifiedHardware,
            UnverifiedOriginalSequence) as exc:
        print("N71_S8000_PORT1_SEQUENCE_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_S8000_ORIGINAL_PORT1_INHERITED_CALL_ORDER_STATIC_PASS")
    print("ORIGINAL_PORT_INDEX_FIELD",result["port_index_field_bytes"])
    print("CONTROLLER_VTABLE_DISPATCH_SLOTS",
          ",".join(map(str,result["root_virtual_slots_in_program_order"])))
    print("PORT_SPECIFIC_STATUS_QUERY_BACKEDGE_PRESENT=YES")
    print("CALLER_LEVEL_EXPLICIT_POLL_TIMEOUT_PROVEN=NO")
    print("CONSTANT_PARAMETER_TO_SHARED_CALLBACK",
          result["fixed_callback_argument"])
    print("ADDITIONAL_PARAMETER_ORIGIN=PORT_OBJECT_FIELD")
    print("SAME_CALLBACK_TARGET_ON_TWO_PATHS=YES")
    print("VIRTUAL_METHODS_HARDWARE_ROLE_AND_MMIO_SEMANTICS_KNOWN=NO")
    print("PCIE_PORT1_LINK_AND_DART1_HARDWARE_SAFE=NO")
    print("NO_FIRMWARE_DUMP_NO_HARDWARE_ACCESS_NO_REGISTER_WRITES")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
