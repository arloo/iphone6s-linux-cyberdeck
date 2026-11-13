#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original N71 S8000 Apple PCIe PORT configuration writer provenance, OFFLINE.

Verifies version-pinned Apple ARM64 method opcodes and authentic constructed
port vtable using independently authenticated owner-private original kernelcache,
original Apple ADT and original iOS IORegistry port1/root snapshots.

A *source* mapping-pointer call at slot 976 is not the same as an observed
physical register aperture. No real hardware register address, original
Apple binary, private UUID/serial/MAC or calibration is disclosed.
This is NOT a PCIe-DART SID/IOMMU or Wi-Fi hardware enablement tool.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import struct
import sys

BASE=Path(__file__).resolve().parent

def load(alias:str,filename:str):
    sp=importlib.util.spec_from_file_location(alias,BASE/filename)
    assert sp and sp.loader
    module=importlib.util.module_from_spec(sp)
    sys.modules[sp.name]=module
    sp.loader.exec_module(module)
    return module

FANOUT=load("n71_original_port_provider_fanout",
            "n71_s8000_original_port1_local_fanout_gate.py")
IOS_ORDER=load("n71_original_port_provider_ios_order",
               "n71_ios_iodevicememory_order_gate.py")

class UnqualifiedPortMMIO(ValueError):pass

def need(value,reason):
    if not value:raise UnqualifiedPortMMIO(reason)

# These are selected short AArch64 instruction signatures, NOT an extracted
# original Apple method or executable. Full proprietary kernel remains private.
CONFIG_SWITCH_OPS={
    0xbe0:0xb941c402,  # object selector field +452
    0xbe4:0x7100205f,  # compare against 8; table-driven path
    0xbf8:0xb8a2790a, # relative jump table
    0xc04:0xf9400268, # load original port object vtable
    0xc08:0xf943ed03, # local slot2008
    0xc10:0x52802481, # relative config offset0x124
    0xc14:0x52800002, # zero input in one branch
    0xc54:0xf943ed08, # local slot2008
    0xc5c:0x52802481, # relative config offset0x124
    0xc60:0xd63f0100, # indirect call
    0xc64:0xb941ca68, # port instance field +456
    0xc68:0x2a084102, # replicate low 16 bits
    0xc70:0xf943ed03, # local slot2008
    0xc78:0x52802501, # relative config offset0x128
    0xc88:0xd61f0060, # indirect tail call
}
CONFIG_WRITE_OPS={
    0x1bb4:0xf9434d08, # local validation virtual slot1688
    0x1bb8:0xaa1403e0,
    0x1bbc:0xaa1303e1,
    0x1bc0:0xd63f0100, # check virtual accessor
    0x1bc4:0x36000120, # branch on failed validation
    0x1bc8:0xf9406a88, # x8 = port object field +208
    0x1bcc:0xb8334915, # STR W21 indexed from x8 by W19
}
PROVIDER_INIT_OPS={
    0x2060:0xf941e908, # parent/root provider slot976
    0x2064:0xaa1403e0, # parent object argument
    0x2068:0x52800001, # parameter 0 (source only)
    0x206c:0x52800002, # parameter 0
    0x2070:0xd63f0100, # root provider indirect call
    0x2074:0xf9006a60, # result stored in port field +208
    0x2078:0xb4003520, # abort on null
    0x2080:0xf9403d08, # mapping/object vtable slot120
    0x2084:0xd63f0100, # indirect mapping call
    0x2088:0xf9006e60, # second result stored at +216
}
GROUPS=(CONFIG_SWITCH_OPS,CONFIG_WRITE_OPS,PROVIDER_INIT_OPS)

def audit_words(shared:bytes)->bool:
    need(type(shared) is bytes and len(shared)==18552,
         "Unrecognized Apple S800x port section length")
    for group in GROUPS:
        for offset,opcode in group.items():
            need(offset+4<=len(shared) and
                 struct.unpack_from("<I",shared,offset)[0]==opcode,
                 "Original Apple port config/provider opcode mismatch")
    all_offsets=[off for group in GROUPS for off in group]
    need(len(all_offsets)==len(set(all_offsets)),
         "Overlapping pinned instruction ranges")
    need(0xbcc<min(CONFIG_SWITCH_OPS) and
         max(CONFIG_SWITCH_OPS)<0xcb4 and
         0x1b58<min(CONFIG_WRITE_OPS) and
         max(CONFIG_WRITE_OPS)<0x1be8 and
         min(PROVIDER_INIT_OPS)>0x2000,
         "Source port method bounds changed")
    return True

def symbolic_port_config(offset:int,value:int,provider_proven:bool):
    """Test-only fail-closed model; never maps or touches actual hardware."""
    need(type(offset) is int and type(value) is int and
         type(provider_proven) is bool,
         "Invalid synthetic port config argument")
    need(0<=value<=0xffffffff,"Not a 32-bit synthetic word")
    need(offset in (0x124,0x128),"Unverified config register offset")
    # Neither the original ARM64 slot nor IORegistry establishes the
    # physical provider return range or storage/modem independence.
    need(provider_proven,
         "No original physical MMIO mapping -> no simulated write permission")
    return (offset,value)

def full_audit(original:bytes,adt:bytes,root_plist:bytes,port1_plist:bytes)->bool:
    # Re-run all previously audited original Apple constructor chain,
    # original stock-iOS provider references, vtables and per-port RMW.
    FANOUT.audit(original,adt,root_plist,port1_plist)
    main,ports,roots=FANOUT.original_port_vtable(original)
    FANOUT.verify_vtable_fanout(original,main,ports,roots)
    need(FANOUT.EXPECTED_PORT_METHODS[1568]==("shared",0xbcc),
         "Original A9 config selector dispatch changed")
    need(FANOUT.EXPECTED_PORT_METHODS[2008]==("shared",0x1b58),
         "Original A9 config writer dispatch changed")
    audit_words(ports["shared"]["code"])
    # Independent real iOS: root provider index 0 is global PCIe CONFIG,
    # NOT either isolated port1 data/control region. Source requests index0
    # from provider slot976; dynamic provider's return remains unobserved.
    resources=IOS_ORDER.compare_private_inputs(root_plist,adt)
    need(len(resources)==11 and resources[0]==(0x610000000,0x1000000),
         "Original root provider global config index 0 mismatch")
    need(resources[3]==(0x602000000,0x4000) and
         resources[4]==(0x602004000,0x4000),
         "Original WLAN port1 resources not independent windows")
    # Port object field+208 is therefore NOT qualified as port1-only.
    return True

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("original_private_n71_kernelcache_macho",
                 "original_private_n71_adt",
                 "original_private_ios_pcie_root_plist",
                 "original_private_ios_pcie_port1_plist"):
        ap.add_argument(name,type=Path)
    args=ap.parse_args()
    files=[args.original_private_n71_kernelcache_macho,
           args.original_private_n71_adt,
           args.original_private_ios_pcie_root_plist,
           args.original_private_ios_pcie_port1_plist]
    limits=(150_000_000,200_000,2_000_000,2_000_000)
    try:
        data=[]
        for p,limit in zip(files,limits):
            need(p.is_file() and not p.is_symlink() and
                 8<p.stat().st_size<limit,"Owner private source not accepted")
            data.append(p.read_bytes())
        full_audit(*data)
    except Exception:
        print("N71_S8000_ORIGINAL_PORT_CONFIG_POINTER_PROVENANCE_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S8000_ORIGINAL_APPLE_PCIE_PORT_CONFIG_POINTER_SOURCE_PASS")
    print("N71_ORIGINAL_PORT_METHOD1568_CONFIG_OFFSETS_0X124_0X128=YES")
    print("N71_ORIGINAL_PORT_WRITER_METHOD2008_VALIDATES_BEFORE_STORE=YES")
    print("N71_ORIGINAL_PORT_METHOD2008_STORES_VIA_INSTANCE_FIELD208=YES")
    print("N71_ORIGINAL_PORT_FIELD208_FROM_PARENT_PROVIDER_SLOT976=YES")
    print("N71_ORIGINAL_PORT_SECOND_MAPPING_RESULT_STORED_FIELD216=YES")
    print("N71_IOS_ROOT_PROVIDER_INDEX0_GLOBAL_PCIE_CONFIG_WINDOW_PASS=YES")
    print("N71_ORIGINAL_PORT1_RESOURCE_INDEX3_4_DISTINCT_FROM_GLOBAL_CONFIG=YES")
    print("N71_PORT_WRITER_INDIRECT_PROVIDER_CALL_REQUESTS_INDEX0=SOURCE_PROVEN")
    print("N71_PORT1_PHYSICAL_MMIO_PROVIDER_REGION_BOUNDARY_PROVEN=NO")
    print("N71_PORT1_0X124_0X128_CROSSPORT_EFFECTS_SAFE=NO")
    print("N71_S8000_PCIE_DART1_REQUESTER_SID_PROVEN=NO")
    print("N71_PHYSICAL_PCIE_OR_NATIVE_BCM4350_WIFI_ACTIVATION_AUTHORIZED=NO")
    print("N71_NO_PHONE_MMIO_DMA_PONGO_NAND_OR_RADIO_ACTION=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
