#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify original N71/S8000 NVMMU table ownership prerequisites only."""
import argparse
from pathlib import Path
import n71_s8000_storage_fact_implementation_gate as F

WORDS={
    0x21e4:0x52808260,0x21e8:0x52880001,0x21ec:0x52801002,
    0x21f4:0xf9008660,0x221c:0xf9008a60,
    0x23c0:0x52800260,0x23c4:0x52820001,0x23c8:0x52820002,
    0x23d0:0xf900a660,0x2530:0xf900ae60,
    0x2540:0xb9001100,0x254c:0xb9001509,
    0x2554:0xf9408660,0x25b8:0xaa0003e1,0x25c0:0x9400008a,
    0x2f14:0xd34cfc4a,0x2f30:0xb82b59ac,
    0x3134:0xb9000b88,0x3164:0xb9000388,
    0x3230:0xb9000788,0x32fc:0x530922ca,0x3300:0xaa14014a,
}
def audit(kernel,adt):
    F.audit(kernel,adt)
    _,port,_=F.STORAGE.FANOUT.original_port_vtable(kernel)
    F.check_words(port["shared"]["code"],WORDS)
    nodes=F.STORAGE.ADT.parse_adt(adt)
    node=nodes[F.STORAGE.ADT.ROOT+"nvme-mmu0"]
    for key,value in {"tags":128,"sgl-entries":256,"virtual-base":0x40000000}.items():
        F.require(node.get(key)==value.to_bytes(4,"little"),"Original NVMMU table geometry changed")
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kernelcache",type=Path);ap.add_argument("apple_adt",type=Path)
    a=ap.parse_args()
    try:audit(a.kernelcache.read_bytes(),a.apple_adt.read_bytes())
    except (OSError,ValueError,KeyError,IndexError):
        print("N71_NVMMU_OWNED_TABLE_SOURCE_GATE=REJECTED");return 1
    print("N71_NVMMU_OWNED_TABLE_SOURCE_GATE=PASS")
    print("ORIGINAL_TCB_TABLE_BYTES=16384 ALIGNMENT=128 REGISTER_PAIR=0x08,0x0c")
    print("ORIGINAL_AUX_TABLE_BYTES=4096 ALIGNMENT=4096 REGISTER_PAIR=0x10,0x14")
    print("ORIGINAL_TCB_TAG_COUNT=128 SGL_ENTRIES_PER_TAG=256 TAG_ADDRESS_SHIFT=23")
    print("ORIGINAL_NVMMU_VIRTUAL_BASE=0x40000000")
    print("HARDWARE_ACCESS_OR_DMA_QUALIFICATION=NO");return 0
if __name__=="__main__":raise SystemExit(main())
