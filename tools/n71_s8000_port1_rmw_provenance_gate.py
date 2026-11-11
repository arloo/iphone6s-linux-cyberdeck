#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71 S8000 port-1 original controller register-RMW provenance: OFFLINE.

Audits original N71 Apple S800x/A9 ROOT vtables and bounded AArch64
subroutines, proving selector IDs and bit masks for four virtual
controller operations and a shared/global status-read dependency.

This is a static code-fact audit, NOT a hardware driver. Do not confuse
C++ virtual-table byte offsets with MMIO offsets. Neither the runtime
IOProvider memory-map order nor register side effects on other ports
are proven. Never write MMIO, clocks, resets, or DART DMA based on this.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent

def load(name:str,filename:str):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ROOT=load("n71_rmw_root","n71_s8000_root_resource_gate.py")
STAT=load("n71_rmw_static","n71_s8000_port1_status_bit_provenance_gate.py")
PORT=load("n71_rmw_port","n71_s8000_port1_inherited_sequence_gate.py")
CTOR=load("n71_rmw_ctor","n71_s8000_constructor_chain_gate.py")
COMMON=load("n71_rmw_offsets","n71_s8000_common_reg_audit.py")

class UnprovenPortRegisters(ValueError):
    pass

def need(ok:bool,reason:str):
    if not ok:raise UnprovenPortRegisters(reason)

def w(blob:bytes,at:int)->int:
    need(0<=at<len(blob)-3 and at%4==0,
         "Truncated original AArch64 method")
    return struct.unpack_from("<I",blob,at)[0]

def same(code:bytes,site:int,expected:int,why:str):
    need(w(code,site)==expected,why)

def ldr_vtable(code:bytes,site:int,slot:int,dst:int=8,base:int=8):
    need(slot%8==0,"Virtual slot is not an aligned pointer index")
    expected=0xF9400000|((slot//8)<<10)|(base<<5)|dst
    same(code,site,expected,"Original root virtual method selector changed")

def movz_w(code:bytes,site:int,dst:int,val:int):
    need(0<=val<65536,"Unexpected register ID")
    same(code,site,0x52800000|(val<<5)|dst,
         "Original A9 register-ID or method argument changed")

def branch_imm(code:bytes,at:int,branch_type:str)->int:
    ins=w(code,at)
    if branch_type=="b":
        need(ins&0xFC000000==0x14000000,
             "Original shared-register polling loop branch not direct B")
        delta=ins&0x3FFFFFF
        if delta&(1<<25):delta-=1<<26
    elif branch_type=="bl":
        need(ins&0xFC000000==0x94000000,
             "Original delay helper not direct BL")
        delta=ins&0x3FFFFFF
        if delta&(1<<25):delta-=1<<26
    else:raise UnprovenPortRegisters("Unexpected branch type")
    return at+4*delta

def cbz_w(code:bytes,site:int,register:int)->int:
    ins=w(code,site)
    need(ins&0xFF00001F==0x34000000|register,
         "Original 32-bit CBZ register/branch changed")
    d=(ins>>5)&0x7FFFF
    if d&(1<<18):d-=1<<19
    return site+4*d

def tbnz_w(code:bytes,site:int,register:int,bit:int)->int:
    ins=w(code,site)
    need((ins&0x7F00001F)==(0x37000000|register) and
         ((ins>>19)&0x1F)==bit and ((ins>>31)&1)==0,
         "Original per-port shared-global bit test changed")
    d=(ins>>5)&0x3FFF
    if d&(1<<13):d-=1<<14
    return site+4*d

def audit_rmw_methods(shared:bytes)->dict:
    need(len(shared)==18552,
         "Wrong original shared-root A9 PCIe executable length")
    # The constructed A9 root class inherits these four operations
    # directly from its S800x superclass; the actual virtual targets
    # are separately checked against the original constructed vtable.
    # Each target invokes the A9 register-ID selector (vslot2016),
    # the Embedded root read32 (vslot1808), and write32 (vslot1816).
    table=(
        # vslot, base, register-ID, ID selector site,
        # root read32 site, root write32 site, masked bit, mask site,
        # composition site
        (1968,0x688,4,0x6ac,0x6bc,0x6dc,0,0x6cc,0x6d4),
        (1984,0x5d0,3,0x5f4,0x608,0x624,0,0x618,0x61c),
        (1992,0x468,2,0x48c,0x49c,0x4c4,8,0x4ac,0x4bc),
        (2000,0x4e0,2,0x504,0x514,0x53c,20,0x524,0x534),
    )
    expected_masks={
        1968:0x121F7808, # AND W8,W0,#~1
        1984:0x121F7808, # AND W8,W0,#~1
        1992:0x12177808, # AND W8,W0,#~(1<<8)
        2000:0x120B7808, # AND W8,W0,#~(1<<20)
    }
    expected_compositions={
        1968:0x2A090102, # ORR W2,W8,W9
        1984:0x2A150102, # ORR W2,W8,W21
        1992:0x2A090102,
        2000:0x2A090102,
    }
    for slot,start,regid,select,read,write,bit,mask_site,combine in table:
        need(start>=0 and start<0x800 and start%4==0,
             "Original root method entry outside bounded subset")
        movz_w(shared,select,1,regid)
        ldr_vtable(shared,select-4,2016)
        ldr_vtable(shared,read,1808)
        ldr_vtable(shared,write,1816,dst=(3 if slot!=1984 else 8))
        same(shared,mask_site,expected_masks[slot],
             "Original register RMW clear-bit mask changed")
        same(shared,combine,expected_compositions[slot],
             "Original register RMW bit composition changed")
    # The slot-1968 control argument is INVERTED before OR into bit0.
    same(shared,0x6d0,0x52000269,
         "Original slot1968 bit-zero polarity inversion changed")
    # The slot-1984 arg is forwarded to bit0, then a separate
    # shared/global ID1/bit4 read is repeated if enable arg !=0.
    same(shared,0x5e0,0xAA0203F5,
         "Original slot1984 boolean input provenance changed")
    need(cbz_w(shared,0x634,21)==0x678,
         "Original ID1 global state-check bypass when arg is zero changed")
    movz_w(shared,0x644,1,1)
    ldr_vtable(shared,0x63c,2016)
    ldr_vtable(shared,0x658,1808)
    need(tbnz_w(shared,0x668,0,4)==0x678,
         "Original shared ID1 bit4 wait condition changed")
    movz_w(shared,0x66c,0,10)
    need(branch_imm(shared,0x674,"b")==0x654,
         "Original ID1 status poll backedge changed")
    need(branch_imm(shared,0x670,"bl") ==
         branch_imm(shared,0x1264,"bl"),
         "Original shared-state polling delay callback identity changed")
    # ID2 bit8 and bit20 set conditionally on original W2 !=0.
    for compare,mov,select in (
        (0x4b0,0x4b4,0x4b8),
        (0x528,0x52c,0x530),
    ):
        same(shared,compare,0x7100027F,
             "Original slot1992/2000 input nonzero test changed")
        same(shared,select,0x1A9F1129,
             "Original bit insertion condition select changed")
    movz_w(shared,0x4b4,9,0x100)
    # W9=1<<20 is encoded with MOVZ halfword shifted by 16.
    same(shared,0x52c,0x52A00209,
         "Original slot2000 bit20 constant changed")
    same(shared,0x5f8,0xAA1403E2,
         "Original slot1984 must forward port index to selector")
    return {
      "rmw_slots":(1968,1984,1992,2000),
      "selector_ids":(4,3,2,2),
      "relative_port1_byte_offsets":(0x1a4,0x194,0x180,0x180),
      "bit_indices":(0,0,8,20),
      "shared_status_register_id":1,
      "shared_status_relative_offset":0x2c,
      "shared_status_bit":4,
      "shared_status_retry_backedge":True,
      "caller_level_timeout_implemented_in_original":False,
      "physical_provider_order_verified":False,
      "hardware_safe":False,
    }

def audit(blob:bytes,adt:bytes)->dict:
    ROOT.audit(blob,adt)
    STAT.inspect(blob,adt)
    # Original constructed A9 ROOT instance table, never metaclass.
    main,classes=ROOT.auditable_root_code(blob)
    ROOT.verify_root_inheritance(blob,main,classes)
    root=classes["a9"]
    shared=classes["shared"]
    for slot,rel in ((1968,0x688),(1984,0x5d0),
                     (1992,0x468),(2000,0x4e0)):
        pointer=CTOR.read_data_pointer(blob,main,root["vptr"]+slot)
        need(pointer==shared["vm"]+rel,
             "Actual A9 root register-operation vtable target changed")
    offsets=COMMON.inspect_macho(blob)
    need(offsets[1]==(0x2c,0) and
         offsets[2]==(0x100,0x80) and
         offsets[3]==(0x114,0x80) and
         offsets[4]==(0x124,0x80),
         "Actual original A9 selector ID1-4 offsets changed")
    return audit_rmw_methods(shared["code"])

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_original_n71_kernelcache_macho",type=Path)
    p.add_argument("private_original_n71_adt",type=Path)
    x=p.parse_args()
    try:
        a=x.private_original_n71_kernelcache_macho
        b=x.private_original_n71_adt
        need(a.is_file() and not a.is_symlink() and
             1000<a.stat().st_size<=ROOT.G.KMAP.MAX_MACHO,
             "Original kernelcache missing, symlinked or unsupported")
        need(b.is_file() and not b.is_symlink() and
             8<b.stat().st_size<=ROOT.ADT.ADT.MAX_FILE,
             "Original N71 ADT missing, symlinked or unsupported")
        r=audit(a.read_bytes(),b.read_bytes())
    except (OSError,ValueError,KeyError,UnicodeError,struct.error,
            UnprovenPortRegisters,ROOT.G.UnqualifiedHardware,
            ROOT.G.KMAP.BadKernelcache,ROOT.ADT.RejectedADT,
            STAT.UnqualifiedStatusBit,PORT.UnverifiedOriginalSequence,
            COMMON.UnverifiedCode) as exc:
        print("N71_PORT1_REGISTER_RMW_AUDIT_FAIL_CLOSED:",str(exc),
              file=sys.stderr)
        return 1
    print("N71_A9_ORIGINAL_PORT1_CONTROLLER_REGISTER_RMW_STATIC_PASS")
    for slot,idx,offset,bit in zip(
        r["rmw_slots"],r["selector_ids"],
        r["relative_port1_byte_offsets"],r["bit_indices"]):
        print("PORT1_CONTROLLER_OPERATION_VSLOT",slot,
              "REG_ID",idx,"RELATIVE_OFFSET",hex(offset),"BIT",bit)
    print("SHARED_GLOBAL_CONTROLLER_POLL_REG_ID=1")
    print("SHARED_GLOBAL_CONTROLLER_POLL_RELATIVE_OFFSET=0x2c")
    print("SHARED_GLOBAL_CONTROLLER_POLL_BIT=4")
    print("ORIGINAL_SHARED_STATUS_POLL_HAS_FINITE_BOUND=NO")
    print("PROVIDER_MEMORY_ORDER_AND_GLOBAL_CROSS_PORT_EFFECTS_PROVEN=NO")
    print("S8000_PCIE_DART1_AND_WIFI_HARDWARE_INIT_AUTHORIZED=NO")
    print("NO_FIRMWARE_DUMP_NO_DEVICE_ACCESS_NO_MMIO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
