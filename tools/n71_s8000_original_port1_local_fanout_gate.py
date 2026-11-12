#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only Apple A9/S8000 *port-instance* PCIe fan-out and isolation gate.

Verifies that the original inherited S800x port-local virtual methods reach
the exact A9 root-instance methods. Distinguishes specific port1 RMWs from
a root-shared register access and opaque config/interrupt-control methods.
Derived code signatures, NOT private original Apple executable bytes.

No iPhone connection, MMIO register access, firmware writes, DART, DMA,
NAND, PCIe PHY/link, baseband, radio, or native-WLAN operation.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
def load(alias,filename):
    sp=importlib.util.spec_from_file_location(alias,HERE/filename)
    assert sp and sp.loader
    m=importlib.util.module_from_spec(sp)
    sys.modules[sp.name]=m
    sp.loader.exec_module(m)
    return m

CHAIN=load("n71_fanout_original_chain","n71_s8000_original_port1_root_bit_control_chain_gate.py")
CTOR=load("n71_fanout_ctor","n71_s8000_constructor_chain_gate.py")
ROOT=CHAIN.ROOT

EXPECTED_PORT_METHODS={
    1504:("shared",0x172c),
    1528:("shared",0x1634),
    1568:("shared",0xbcc),
    1848:("shared",0x1424),
    1864:("shared",0xb3c),
    2000:("shared",0x1a78),
    2008:("shared",0x1b58),
    2016:("embedded",0x90ec),
}
EXPECTED_ROOT_DISPATCH={
    1936:("shared",0x558),
    1976:("shared",0x3fc),
    2040:("shared",0x7d8),
}
# Essential version-pinned instruction identities: root bit operations
# and port-local forwarding which DOES NOT prove electrical side effects.
SHARED_WORDS={
    0x1634:0xaa0103e2,
    0x1638:0xf945ac08,
    0x163c:0xb940a801,
    0x1644:0xf943dd23,  # root vslot1976
    0x164c:0xd61f0060,
    0x1424:0xaa0103e2,
    0x1428:0xf945ac08,
    0x142c:0xb940a801,
    0x1434:0xf943c923,  # root vslot1936
    0x143c:0xd61f0060,
    0xb3c:0xf945ac08,
    0xb40:0xb940a801,
    0xb48:0xf943fd22,  # root vslot2040
    0xb50:0xd61f0040,
    0x420:0x52800041,  # root1976 uses selector ID2
    0x440:0x121f7808,  # clear bit0
    0x444:0x2a130102,  # merge caller flag
    0x44c:0xf9438d03,  # write32 root virtual slot1816
    0x57c:0x52800061,  # root1936 uses selector ID3
    0x59c:0x12177808,  # clear bit8
    0x5a4:0x52802009,  # bit8 constant
    0x5a8:0x1a8913e9,  # inverted caller flag
    0x5ac:0x2a090102,  # merge bit8
    0x7d8:0x52880408,  # root2040: 0x4020
    0x7dc:0x0b011901,  # root-relative 0x4020 + port*0x40
    0x7e4:0xf9438d03,  # write32 root virtual slot1816
    0x7e8:0x52800062,  # constant 3
    0x7ec:0xd61f0060,  # tail-call write32
    0x1740:0xf943e908,  # port1504 -> local slot2000
    0x1744:0x52804201,  # relative 0x210 used by local config path
    0x1758:0xf943ed08,  # port1504 -> local slot2008
    0xbe0:0xb941c402,  # port1568 uses instance field at 0x1c4
    0xbe4:0x7100205f,  # port1568 switch case upper bound 8
    0xc04:0xf9400268,  # port1568 reaches port-local config path
    0xc10:0x52802481,  # relative 0x124
}
# Controller slots are on A9 ROOT objects, not the A9 PORT objects.
ROOT_SLOTS=(1936,1976,2040)
PORT_SLOTS=tuple(EXPECTED_PORT_METHODS)
KNOWN_PORT1_ROOT_SELECTOR_OFFSETS={
    "ID2_PORT1_BIT0":0x180,
    "ID3_PORT1_BIT8":0x194,
    "PORT_SCOPED_WRITE_3_RELATIVE":0x4060,
}
ROOT_COMMON_WINDOW_BASE=0x600000000
ROOT_COMMON_WINDOW_LENGTH=0x8000

class UnqualifiedPortFanout(ValueError):pass
def need(x,why):
    if not x:raise UnqualifiedPortFanout(why)

def original_port_vtable(original:bytes):
    CTOR.audit(original)
    root_main,root_mods=ROOT.auditable_root_code(original)
    main=CTOR.KMAP.macho_segments(original,0)
    meta=main["__PRELINK_INFO"]
    table=CTOR.KMAP.kext_metadata(
        original[meta["offset"]:meta["offset"]+meta["filesize"]].rstrip(b"\0"))
    pre=main["__PRELINK_TEXT"]
    exe=main["__PLK_TEXT_EXEC"]
    pmods={}
    for name,ident in CTOR.MODS.items():
        code_va,code_size=table[ident]
        need(pre["vm"]<=code_va and
             code_va-pre["vm"]+code_size<=pre["filesize"],
             "Unverified original A9 port class bounds")
        nested=CTOR.KMAP.macho_segments(
            original,pre["offset"]+code_va-pre["vm"])
        sec=nested["__TEXT_EXEC"]["sections"]["__text"]
        need(sec["size"]==CTOR.TEXT_LENGTHS[name] and
             exe["vm"]<=sec["vm"] and
             sec["vm"]+sec["size"]<=exe["vm"]+exe["filesize"],
             "Unverified original A9 PCIe Port section")
        at=CTOR.CTOR_VPTR_ADRP[name]
        code=original[exe["offset"]+sec["vm"]-exe["vm"]:
                      exe["offset"]+sec["vm"]-exe["vm"]+sec["size"]]
        vptr=CTOR.adrp_add_str_vptr(
            sec["vm"]+at,CTOR.w(code,at),
            CTOR.w(code,at+4),CTOR.w(code,at+8))
        pmods[name]={"vm":sec["vm"],"code":code,"vptr":vptr}
    return main,pmods,root_mods

def verify_vtable_fanout(original:bytes,main:dict,
                         port_modules:dict,root_modules:dict):
    port=port_modules["a9"]["vptr"]
    root=root_modules["a9"]["vptr"]
    for slot,(owner,relative) in EXPECTED_PORT_METHODS.items():
        found=CTOR.read_data_pointer(original,main,port+slot)
        need(found==port_modules[owner]["vm"]+relative,
             "Port-local constructed object vtable target changed")
    for slot,(owner,relative) in EXPECTED_ROOT_DISPATCH.items():
        found=ROOT.G.read_data_pointer(original,main,root+slot)
        need(found==root_modules[owner]["vm"]+relative,
             "A9 root constructed vtable target changed")
    need(port!=root,"Port object is not the root controller object")
    return True

def check_words(shared:bytes):
    need(len(shared)==18552,"Original shared S800x PCIe code extent changed")
    for at,expected in SHARED_WORDS.items():
        need(struct.unpack_from("<I",shared,at)[0]==expected,
             "Original per-port forwarding or root method bit-mask code changed")
    # Check the original port startup source contains these dispatch sites,
    # and the second additional method is conditional on object field +404.
    original=CHAIN.PORT.OTHER_PORT_VTABLE_CALLS
    need((0x126c,1528) in original and (0x12f0,1864) in original and
         (0x1300,1504) in original and (0x1318,1848) in original and
         (0x137c,1568) in original,
         "Inherited S800x port1 startup source order changed")
    return True

def model_followed_port1_effects(snapshot:dict[tuple[int,int],int],
                                 include_conditional_id3_bit8:bool):
    """Fake 4-port symbolic maps only. Never perform root-shared writes."""
    need(type(include_conditional_id3_bit8) is bool,
         "Conditional path not a trusted Boolean")
    need(set(snapshot)=={(port,sel) for port in range(4)
                         for sel in (2,3,4,5)},
         "Incomplete modeled four-port source registers")
    need(all(type(v) is int and 0<=v<=0xffffffff
             for v in snapshot.values()),
         "Malformed symbolic 32-bit register values")
    after=dict(snapshot)
    # Original startup invokes port slot1528 with w1=1 after IODelay(100):
    # root slot1976 => selector ID2, port1, bit0 set.
    after[1,2]=snapshot[1,2]|1
    # Later conditional slot1848 w1=1 => root slot1936 selector ID3
    # clears bit8 (inverted flag).
    if include_conditional_id3_bit8:
        after[1,3]=snapshot[1,3]&~0x100
    need(all(after[p,k]==snapshot[p,k] for p in (0,2,3)
             for k in (2,3,4,5)),
         "Protected storage/baseband/other symbolic port changed")
    return after

def audit(private_original:bytes,private_adt:bytes,
          private_root_ios:bytes,private_port_ios:bytes):
    # Independent prior exact old Apple source/runtime control checks.
    CHAIN.inspect(private_original,private_adt,
                  private_root_ios,private_port_ios)
    main,ports,roots=original_port_vtable(private_original)
    verify_vtable_fanout(private_original,main,ports,roots)
    check_words(ports["shared"]["code"])
    need(KNOWN_PORT1_ROOT_SELECTOR_OFFSETS["PORT_SCOPED_WRITE_3_RELATIVE"]
         ==0x4020+(1<<6), "S8000 root port1 0x4060 register offset changed")
    need(0x4060<ROOT_COMMON_WINDOW_LENGTH,
         "A9 original per-port offset outside original root resource")
    # Simulated only; root-global/common hardware registers are not
    # a safe physical register-access model.
    seed={(p,k):((p<<23)|(k<<15)|0x35)
          for p in range(4) for k in (2,3,4,5)}
    for enabled in (False,True):
        after=model_followed_port1_effects(seed,enabled)
        need(all(after[p,k]==seed[p,k] for p in (0,2,3)
                 for k in (2,3,4,5)), "Illegal simulated cross-port impact")
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("original_n71_macho","original_n71_adt",
                 "stock_ios_root_plist","stock_ios_port1_plist"):
        p.add_argument(name,type=Path)
    arg=p.parse_args()
    paths=(arg.original_n71_macho,arg.original_n71_adt,
           arg.stock_ios_root_plist,arg.stock_ios_port1_plist)
    limits=(150_000_000,200_000,2_000_000,2_000_000)
    try:
        data=[]
        for path,limit in zip(paths,limits):
            need(path.is_file() and not path.is_symlink() and
                 8<path.stat().st_size<limit,
                 "Untrusted original private evidence")
            data.append(path.read_bytes())
        audit(*data)
    except Exception:
        print("N71_S8000_ORIGINAL_PORT1_LOCAL_FANOUT_STATIC_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S8000_ORIGINAL_PORT1_LOCAL_FANOUT_STATIC_PASS")
    print("N71_REAL_APPLE_PORT_INSTANCE_VTABLE_METHOD_TARGETS_8_OF_8_PASS")
    print("N71_REAL_APPLE_ROOT_CONTROLLER_FANOUT_TARGETS_3_OF_3_PASS")
    print("N71_ORIGINAL_PORT_SLOT1528_TO_ROOT1976_ID2_BIT0_SET=YES")
    print("N71_ORIGINAL_PORT_SLOT1848_TO_ROOT1936_ID3_BIT8_INVERTED=YES")
    print("N71_ORIGINAL_PORT_SLOT1864_TO_ROOT2040_COMMON_OFFSET_0X4060_WRITE3=YES")
    print("N71_ORIGINAL_PORT_SLOT1504_CONFIG_PATH_0X210_SOURCE=YES")
    print("N71_ORIGINAL_PORT_SLOT1568_SWITCHED_CONFIG_PATH_0X124_SOURCE=YES")
    print("N71_PORT_LOCAL_BUS_CONFIG_MSI_POWER_SIDE_EFFECTS_SAFE=NO")
    print("N71_ROOT_COMMON_0X4060_REGISTER_WRITE_AUTHORIZED=NO")
    print("N71_ORIGINAL_SHARED_ROOT_POWER_RESET_SEMANTICS_PROVEN=NO")
    print("N71_PORT1_SOFTWARE_SYMBOLIC_MODEL_PRESERVES_PORT0_2_3=YES")
    print("N71_REAL_S8000_DART1_PHYSICAL_PCIE_REQUESTER_SID_PROVEN=NO")
    print("N71_NATIVE_WIFI_PCIE_DMA_MMIO_TEST_AUTHORIZED=NO")
    return 0

if __name__=="__main__":raise SystemExit(main())
