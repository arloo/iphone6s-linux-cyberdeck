#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71 S8000 PCIe port1 original Apple root RMW sequencing: OFFLINE ONLY.

Authentic private ARM64 code + private Apple ADT + original iOS IORegistry:
checks actual root instance vtable targets, original direct ARM64 instruction
identities and known masked-RMW operations at specialized register selector
ID2/ID3/ID4, plus unbounded status queries ID5 and globally shared ID1.

This is NOT a Linux hardware driver and MUST NOT be used as a write sequence.
No MMIO/DMA, register maps, NAND, hardware clocks, reset, Wi-Fi, or phone IO.
Only derived, non-sensitive source-control facts are printed.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
def module(alias,filename):
    sp=importlib.util.spec_from_file_location(alias,HERE/filename)
    assert sp and sp.loader
    m=importlib.util.module_from_spec(sp)
    sys.modules[sp.name]=m
    sp.loader.exec_module(m)
    return m

STATUS=module("n71_original_port1_status", "n71_s8000_port1_status_bit_provenance_gate.py")
DELAY=module("n71_original_delay", "n71_s8000_original_refclk_perst_delay_gate.py")
MEM=module("n71_original_live_iod_mem", "n71_ios_iodevicememory_order_gate.py")
ROOT=STATUS.ROOT
PORT=STATUS.PORT

# Version-pinned derived ARM64 instruction words from genuine AppleS800xPCIe.
# Only the essential register-ID / RMW mask / dispatch / loop signatures;
# never store, publish or disassemble the private original Apple binary.
PINNED={
    # root virtual slot1968 -> ID4(port) -> read32 -> bit0 XOR flag -> write32.
    0x6ac:0x52800081, # selector ID4
    0x6b0:0xd63f0100, # root selector indirect BLR
    0x6cc:0x121f7808, # value &= ~1
    0x6d0:0x52000269, # flag XOR 1
    0x6d4:0x2a090102, # value |= inverted flag
    0x6dc:0xf9438d03, # virtual root write32, slot1816
    0x6f4:0xd61f0060, # tail BR to write32
    # root virtual slot1984 -> ID3(port) -> bit0 -> shared ID1 bit4 poll.
    0x5f4:0x52800061, # selector ID3
    0x618:0x121f7808, # value &= ~1
    0x61c:0x2a150102, # value |= arg flag
    0x624:0xf9438d08, # root write32 slot1816
    0x634:0x34000235, # skip global status loop if flag0
    0x644:0x52800021, # shared/global selector ID1
    0x668:0x37200080, # TB(N)Z W0 bit4 -> escape when set
    0x66c:0x52800140, # IODelay(10) argument
    0x670:0x94001082, # original direct call (target validated by DELAY)
    0x674:0x17fffff8, # backwards branch into status poll
    # root virtual slot1992 -> ID2(port) -> read32 bit8 clear/set.
    0x48c:0x52800041, # selector ID2
    0x4ac:0x12177808, # value &= ~(1<<8)
    0x4b0:0x7100027f, # compare flag
    0x4b4:0x52802009, # bit8 constant
    0x4b8:0x1a9f1129, # CSEL bit if flag nonzero
    0x4bc:0x2a090102, # merge preserved bits
    0x4c4:0xf9438d03, # root write32
    # root virtual slot2000 -> ID2(port) -> read32 bit20 clear/set.
    0x504:0x52800041, # selector ID2
    0x524:0x120b7808, # value &= ~(1<<20)
    0x528:0x7100027f, # compare flag
    0x52c:0x52a00209, # bit20 constant
    0x530:0x1a9f1129, # CSEL bit if flag nonzero
    0x534:0x2a090102, # merge preserved bits
    0x53c:0xf9438d03, # root write32
}
EXPECTED_ROOT_SLOT_TARGETS={
 1808:("embedded",0x4654),
 1816:("embedded",0x46b0),
 1968:("shared",0x688),
 1984:("shared",0x5d0),
 1992:("shared",0x468),
 2000:("shared",0x4e0),
 2008:("shared",0x3b4),
 2016:("a9",0x7d8),
}
# The old Apple S800x inherited *port1* method's source-level order.
EXPECTED_ROOT_STARTUP=(1968,1984,2008,1992,2000,1968)
PER_PORT_REG_BASE={2:0x100,3:0x114,4:0x124,5:0x12c}
PER_PORT_STRIDE=0x80
SHARED_GLOBAL_STATUS_OFFSET=0x2c
ROOT_MMIO_START=0x600000000
ROOT_COMMON_INDEX=9

class OriginalRootControlNotQualified(ValueError):
    pass

def require(ok,msg):
    if not ok:raise OriginalRootControlNotQualified(msg)

def check_control_rmw_original(shared:bytes,embedded:bytes):
    require(len(shared)==18552 and len(embedded)==46924,
            "Original A9 shared/embedded root code length changed")
    for off,opcode in PINNED.items():
        require(struct.unpack_from("<I",shared,off)[0]==opcode,
                "A9 controller RMW/mask/branch instruction changed")
    # Actual original root write32 routine: read mapped root base field
    # +424, store 32-bit value at indexed byte offset. Does not prove
    # electrical safety or exclusivity of the common root.
    require(struct.unpack_from("<I",embedded,0x4704)[0]==0xf940d688,
            "Original common-root mapped pointer field changed")
    require(struct.unpack_from("<I",embedded,0x4708)[0]==0xb8356913,
            "Original common-root 32-bit store method changed")
    # Control branch: source-language roots 1968/1984/2008/... proven in PORT.
    steps=tuple(x[5] for x in PORT.ROOT_CALLS)
    require(steps==(1968,1984,2008,1992,1968),
            "Original port1 root method ordering changed")
    # Optional root2000 between root1992 & root1968.
    require(PORT.ROOT_CALLS[3][5]==1992 and
            PORT.ROOT_CALLS[4][5]==1968 and
            PORT.OTHER_PORT_VTABLE_CALLS[0][1]==1528,
            "Original port1 source dispatch gating changed")
    return True

def check_vtables(original:bytes,main:dict,mods:dict):
    for slot,(owner,offset) in EXPECTED_ROOT_SLOT_TARGETS.items():
        actual=ROOT.G.read_data_pointer(
            original,main,mods["a9"]["vptr"]+slot)
        require(actual==mods[owner]["vm"]+offset,
                "Real constructed A9 root vtable slot target changed")
    return True

def offsets(port:int)->dict[int,int]:
    require(type(port) is int and 0<=port<=3,
            "Unverified Apple A9 physical PCIe port")
    return {key:base+port*PER_PORT_STRIDE
            for key,base in PER_PORT_REG_BASE.items()}

def symbolic_port1_only_rmw(registers:dict[tuple[int,int],int],
                           optional_id2_bit20:bool):
    """Pure software model. Simulates known bit effects, not power-up safety.

    No interaction with any actual register, platform or original firmware.
    Registers have keyed (port,selector-id) symbolic fake values.
    Original reads/polls are NOT simulated as physical ready conditions.
    """
    require(type(optional_id2_bit20) is bool,"Unexpected optional path")
    require(set(registers)=={(port,idx)
                             for port in range(4)
                             for idx in (2,3,4,5)},
            "Incomplete symbolic controller register snapshot")
    require(all(type(x) is int and 0<=x<=0xffffffff
                for x in registers.values()),"Bad symbolic register value")
    after=dict(registers)
    actions=[]
    def write_id(idx:int,flag_bit:int,flag_enabled:bool):
        k=(1,idx)
        before=after[k]
        if flag_enabled:after[k]=(before|(1<<flag_bit))&0xffffffff
        else:after[k]=before&~(1<<flag_bit)
        actions.append((idx,flag_bit,int(flag_enabled)))
    write_id(4,0,False)  # original slot1968(flag=1): invert bit0 -> 0
    write_id(3,0,True)   # original slot1984(flag=1): ID3 bit0 -> 1
    # Original bit4 shared status poll & ID5 bit0 poll: NO write.
    write_id(2,8,False)  # original slot1992(flag=0)
    if optional_id2_bit20:
        write_id(2,20,True) # original optional slot2000(flag=1)
    write_id(4,0,True)   # original slot1968(flag=0)
    require(all(after[(p,i)]==registers[(p,i)]
                for p in (0,2,3) for i in (2,3,4,5)),
            "Symbolic cross-port register modification detected")
    return after,tuple(actions)

def inspect(original:bytes,adt:bytes,stock_root:bytes,stock_port:bytes):
    STATUS.inspect(original,adt)
    require(DELAY.verify(original,adt,stock_port)==100,
            "Original XNU microsecond delay provenance unproven")
    mem=MEM.compare_private_inputs(stock_root,adt)
    require(len(mem)==11 and
            mem[9]==(ROOT_MMIO_START,0x8000),
            "Original live Apple mapped common resource index9 mismatched")
    require(mem[1]==(0x601000000,0x4000) and
            mem[5]==(0x603000000,0x4000),
            "Original storage/baseband resource isolation metadata changed")
    main,mods=ROOT.auditable_root_code(original)
    check_vtables(original,main,mods)
    check_control_rmw_original(mods["shared"]["code"],
                               mods["embedded"]["code"])
    # Actual original Apple root 2016 specialized six-case selector already
    # validated by STATUS.inspect. These are ROOT-relative byte offsets.
    require(offsets(1)=={2:0x180,3:0x194,4:0x1a4,5:0x1ac},
            "S8000 original port1 selector offsets changed")
    seed={(p,i):(0x4b000000 ^ (p<<24) ^ (i<<16) ^ (p*i))
          for p in range(4) for i in (2,3,4,5)}
    for flag in (False,True):
        updated,ops=symbolic_port1_only_rmw(seed,flag)
        require(all(updated[(p,i)]==seed[(p,i)] for p in (0,2,3)
                    for i in (2,3,4,5)),
                "Original port1-only RMW symbolic scope violated")
        require(len(ops)==(5 if flag else 4),
                "Unexpected symbolic port1 RMW count")
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("original_n71_arm64_macho",type=Path)
    p.add_argument("original_n71_apple_adt",type=Path)
    p.add_argument("original_ios_apcie",type=Path)
    p.add_argument("original_ios_pci_bridge1",type=Path)
    a=p.parse_args()
    try:
        paths=(a.original_n71_arm64_macho,a.original_n71_apple_adt,
               a.original_ios_apcie,a.original_ios_pci_bridge1)
        limits=(150_000_000,200_000,2_000_000,2_000_000)
        blobs=[]
        for path,limit in zip(paths,limits):
            require(path.is_file() and not path.is_symlink() and
                    8<path.stat().st_size<limit,
                    "Private original Apple evidence not available")
            blobs.append(path.read_bytes())
        inspect(*blobs)
    except Exception:
        print("N71_S8000_ORIGINAL_PORT1_ROOT_CONTROL_STATIC_NOT_QUALIFIED",
              file=sys.stderr)
        return 2
    print("N71_S8000_ORIGINAL_PORT1_ROOT_BIT_RMW_CHAIN_STATIC_PASS")
    print("N71_REAL_A9_ROOT_VTABLE_SLOT_METHOD_TARGETS_8_OF_8_PASS")
    print("N71_REAL_APPLE_ROOT_WRITE32_MAP_RESOURCE_INDEX9=VERIFIED")
    print("N71_PER_PORT_ID2_BIT8_AND_BIT20_RMW_SOFTWARE_PROVEN=YES")
    print("N71_PER_PORT_ID3_BIT0_AND_ID4_INVERTED_BIT0_RMW_PROVEN=YES")
    print("N71_ORIGINAL_SHARED_ROOT_ID1_STATUS_BIT4_POLL=YES")
    print("N71_ORIGINAL_PORT1_ID5_STATUS_BIT0_POLL=YES")
    print("N71_ORIGINAL_POLL_TIMEOUT_IN_CALLER_PROVEN=NO")
    print("N71_ORIGINAL_XNU_IODelay_100US_AND_10US_PROVEN=YES")
    print("N71_ORIGINAL_ROOT_RESOURCE9_PHYSICAL_BASE_FROM_STOCK_IOS=0x600000000")
    print("N71_PER_PORT_RMW_SOFTWARE_MODEL_PRESERVES_OTHER_PORT_REGISTERS=YES")
    print("N71_GLOBAL_ROOT_SHARED_TUNING_NO_CROSSPORT_IMPACT_PROVEN=NO")
    print("N71_RESET_CLOCK_PHY_ELECTRICAL_BIT_MEANINGS_PROVEN=NO")
    print("N71_HARDWARE_REQUESTER_TO_DART_SID_AND_DMA_ISOLATION_PROVEN=NO")
    print("N71_SAFE_PCIE_MMIO_DART_DMA_NATIVE_WIFI_AUTHORIZED=NO")
    print("N71_OWNER_PRIVATE_ORIGINAL_CODE_AND_TUNABLES_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
