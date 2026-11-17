#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed original N71/S8000 PCIe 3/7 command and storage-callback order.

Source: owner-private original N71 Apple ARM64 kernelcache and ADT.
No kernelcache bytes, unique identifiers, raw firmware, or SSH material
are embedded in this source. This NEVER accesses physical hardware.
The original 3/7 commands have unknown side effects: neither is
authorized to be issued on Linux by this verifier.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import n71_s8000_original_port1_local_fanout_gate as PORT
import n71_s8000_storage_force_active_chain_gate as STORAGE

class UnsafeAppleSequence(ValueError):
    pass

def require(v:bool,reason:str)->None:
    if not v:raise UnsafeAppleSequence(reason)

PORT_METHODS={1864:0xb3c,1872:0xb54}
ROOT_METHODS={2040:0x7d8,2048:0x7f0}
# Original strict ARM64 identities pinned by byte offsets in the
# source KEXT. Keep the smallest essential set for each proof.
S800X_COMMAND_WORDS={
  0x7d8:0x52880408,  # 0x4020 per-port root register
  0x7dc:0x0b011901,  # offset = 0x4020 + (port<<6)
  0x7e4:0xf9438d03,  # generic root write32 virtual method
  0x7e8:0x52800062,  # w2=3
  0x7ec:0xd61f0060,  # indirect tail-call
  0x7f0:0x52880408,
  0x7f4:0x0b011901,
  0x7fc:0xf9438d03,
  0x800:0x528000e2,  # w2=7
  0x804:0xd61f0060,
  0xb48:0xf943fd22,  # port slot 1864 -> root slot 2040
  0xb50:0xd61f0040,
  0xb60:0xf9440122,  # port slot 1872 -> root slot 2048
  0xb68:0xd61f0040,
  0xa5c:0xf943a908,  # separate S800x port call of slot 1872
  0x12f0:0xf943a508, # active startup calls slot 1864
  0x1300:0xf942f108, # next: port-local slot1504 config
  0x1310:0x350000c8, # conditional branch around port 1848
  0x1318:0xf9439d08, # conditional port 1848
  0x1328:0x52800028, # shared callback state=1
  0x132c:0xb9000fe8, # shared state stored to stack
  0x1330:0xf9409a60, # DART callback at obj+304
  0x1338:0xf9404108, # DART callback method slot128
  0x1348:0xd63f0100,
  0x134c:0xf945b260, # NVMMU callback obj+2912
  0x1358:0xf9404108, # NVMMU callback slot128
  0x1368:0xd63f0100,
  0x1174:0xb9000fff, # separate earlier method state=0
  0x1178:0xf9409800,
  0x1194:0xf945b260,
}
EMBEDDED_WORDS={
  0x3eb0:0xf943a908, # different flow invoking port slot1872
}
S800X_STARTUP_ORDER=(
  (0x12f0,"root_write_3_via_port1864"),
  (0x1300,"port_local_config_via_slot1504"),
  (0x1318,"conditional_root_config_via_port1848"),
  (0x1328,"callback_state_1"),
  (0x1338,"dart_force_active_callback"),
  (0x1358,"nvmmu_force_active_callback"),
)
S800X_SEPARATE_ZERO_STATE_METHOD=(0x1174,0x1178,0x1194)
S800X_ROOT_WRITE_7_CALL_SITES=(("shared",0xa5c),("embedded",0x3eb0))
ROOT_COMMON_WINDOW_LENGTH=0x8000

def check_words(blob:bytes,required:dict[int,int])->None:
    require(len(blob)>=max(required)+4,"Original ARM64 code truncated")
    for off,expected in required.items():
        require(struct.unpack_from("<I",blob,off)[0]==expected,
                "Original Apple ARM64 instruction identity not recognized")

def check_order(order= S800X_STARTUP_ORDER)->None:
    require(tuple(name for _,name in order)==tuple(name for _,name in S800X_STARTUP_ORDER),
            "Original Apple startup call phases changed")
    require(all(type(offset) is int and offset%4==0 and offset>=0
                for offset,_ in order), "Invalid original ARM64 call offset")
    require(tuple(x for x,_ in order)==tuple(x for x,_ in S800X_STARTUP_ORDER),
            "Original Apple startup callback instruction positions changed")
    require(list(x for x,_ in order)==sorted(x for x,_ in order),
            "Original Apple port command/callback source order changed")
    # Verify independent activation method state0 is BEFORE start1
    # in *source memory only*. We do NOT claim it always runs first.
    require(max(S800X_SEPARATE_ZERO_STATE_METHOD)<order[0][0],
            "Source methods unexpectedly overlap")

def check_original_constructed_vtables(kernel:bytes)->tuple[bytes,bytes]:
    main,port,root=PORT.original_port_vtable(kernel)
    PORT.verify_vtable_fanout(kernel,main,port,root)
    for slot,relative in PORT_METHODS.items():
        ptr=PORT.CTOR.read_data_pointer(kernel,main,
                                       port["a9"]["vptr"]+slot)
        require(ptr==port["shared"]["vm"]+relative,
                "Original Apple N71 port virtual command target changed")
    for slot,relative in ROOT_METHODS.items():
        ptr=PORT.ROOT.G.read_data_pointer(kernel,main,
                                         root["a9"]["vptr"]+slot)
        require(ptr==root["shared"]["vm"]+relative,
                "Original Apple N71 root virtual command target changed")
    shared=port["shared"]["code"]
    embedded=port["embedded"]["code"]
    require(len(shared)==18552 and len(embedded)==46924,
            "Original Apple source bounds changed")
    check_words(shared,S800X_COMMAND_WORDS)
    check_words(embedded,EMBEDDED_WORDS)
    check_order()
    require(S800X_ROOT_WRITE_7_CALL_SITES==
            (("shared",0xa5c),("embedded",0x3eb0)),
            "Original Apple source call paths changed")
    require(0x4020+(3<<6)<ROOT_COMMON_WINDOW_LENGTH,
            "Original port indexed command register outside root MMIO")
    return shared,embedded

def audit(kernel:bytes,adt:bytes)->None:
    STORAGE.audit(kernel,adt)
    check_original_constructed_vtables(kernel)

def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stock_kernelcache",type=Path)
    p.add_argument("original_apple_adt",type=Path)
    args=p.parse_args()
    try:
        src=args.stock_kernelcache.read_bytes()
        adt=args.original_apple_adt.read_bytes()
        require(20_000_000<len(src)<150_000_000 and 1000<len(adt)<200_000,
                "Original source size not plausible")
        audit(src,adt)
    except (OSError,ValueError,KeyError,IndexError,struct.error) as err:
        print("N71_APPLE_PCIE_STORAGE_COMMAND_AND_CALLBACK_ORDER_GATE=REJECTED")
        raise SystemExit(1) from None
    print("N71_APPLE_PCIE_STORAGE_COMMAND_AND_CALLBACK_ORDER_GATE=PASS")
    print("N71_ORIGINAL_ROOT_PORT_INDEXED_COMMAND_WRITES_3_AND_7_PROVEN=YES")
    print("N71_ROOT_VSLOTS_2040_AND_2048_TO_SINGLE_PER_PORT_COMMAND_REGISTER=YES")
    print("N71_PORT_VSLOTS_1864_AND_1872_CORRECTLY_DISPATCH=YES")
    print("N71_SOURCE_START_ORDER_WRITE3_THEN_CONFIG_THEN_DART_THEN_NVMMU=YES")
    print("N71_SEPARATE_CALLBACK_STATE0_SOURCE_PATH_CONFIRMED=YES")
    print("N71_REGISTER_3_7_ELECTRICAL_SEMANTICS_PROVEN=NO")
    print("N71_STORAGE_DMA_OR_NAND_OPERATION_PERFORMED=NO")

if __name__=="__main__":
    main()
