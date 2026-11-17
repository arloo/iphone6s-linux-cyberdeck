#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original Apple N71 S8000 port vslot1504: 0x210 conditional read-back write.

This proves an ARM64 call graph in the owner-supplied original Apple
kernelcache; it does not perform any PCIe write or prove whether the
0x210 register is write-one-to-clear, self-clearing or a status latch.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import n71_s8000_original_port1_local_fanout_gate as FANOUT

class UnqualifiedLocalConfiguration(ValueError):
    pass

# Original AppleS800xPCIe ARM64 __text byte offsets, not runtime MMIO.
ORIGINAL_1504={
    0x173c:0xf9400008, # source port vtable
    0x1740:0xf943e908, # local read method slot 2000
    0x1744:0x52804201, # register relative offset 0x210
    0x1748:0xd63f0100, # call read
    0x174c:0xaa0003f4, # save read result
    0x1750:0x340000e0, # if zero skip write
    0x1754:0xf9400268, # load same port object vtable
    0x1758:0xf943ed08, # local write method slot 2008
    0x175c:0xaa1303e0, # same port object
    0x1760:0x52804201, # identical relative offset 0x210
    0x1764:0xaa1403e2, # write exactly the read value
    0x1768:0xd63f0100, # call local write
    0x176c:0xaa1403e0, # return original read value
    0x1778:0xd65f03c0, # ret
}
ORIGINAL_DRIVER_ACCESSORS={
    0x1ad4:0xf9400288, # port object vptr
    0x1ad8:0xf9434d08, # vslot1688 actual port-local read
    0x1ae8:0x36000220, # read result is success gated
    0x1bb0:0xf9400288, # write path same port vptr
    0x1bb4:0xf9434d08, # vslot1688 actual port-local write
    0x1bc4:0x36000120, # write result success gated
    0x1bc8:0xf9406a88, # port mapped register bank pointer +208
    0x1bcc:0xb8334915, # memory store of original w21 value
}
STOCK_PORT_SLOTS={1504:0x172c,2000:0x1a78,2008:0x1b58}

def check_words(code:bytes,words:dict[int,int])->None:
    if not code or len(code)<max(words)+4:
        raise UnqualifiedLocalConfiguration("Original Apple S800x __text truncated")
    for offset,expected in words.items():
        if struct.unpack_from("<I",code,offset)[0]!=expected:
            raise UnqualifiedLocalConfiguration("Original S8000 port config instruction mutated")

def audit(kernel:bytes)->None:
    main,ports,roots=FANOUT.original_port_vtable(kernel)
    FANOUT.verify_vtable_fanout(kernel,main,ports,roots)
    for slot,expected in STOCK_PORT_SLOTS.items():
        dest=FANOUT.CTOR.read_data_pointer(kernel,main,ports["a9"]["vptr"]+slot)
        if dest!=ports["shared"]["vm"]+expected:
            raise UnqualifiedLocalConfiguration("Unexpected N71 S8000 port vtable")
    s=ports["shared"]["code"]
    if len(s)!=18552:
        raise UnqualifiedLocalConfiguration("N71 original S800x text changed")
    check_words(s,ORIGINAL_1504)
    check_words(s,ORIGINAL_DRIVER_ACCESSORS)
    # Prove exact w1 immediate (register selector) at both read & write.
    if (struct.unpack_from("<I",s,0x1744)[0] !=
        struct.unpack_from("<I",s,0x1760)[0]):
        raise UnqualifiedLocalConfiguration("Read/write selector differs")
    # Explicitly exclude unknown hardware side effects from claims.
    if not (0x1750<0x1758<0x1768<0x176c):
        raise UnqualifiedLocalConfiguration("Zero-guard branch no longer delimits write")

def main()->int:
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument("original_private_kernelcache",type=Path)
    opts=pa.parse_args()
    try:
        if not opts.original_private_kernelcache.is_file():
            raise UnqualifiedLocalConfiguration("Original private source absent")
        blob=opts.original_private_kernelcache.read_bytes()
        if not 20000000<len(blob)<150000000:
            raise UnqualifiedLocalConfiguration("Original source size invalid")
        audit(blob)
    except (ValueError,OSError,IndexError,KeyError,struct.error):
        print("N71_S8000_STOCK_PCIE_LOCAL_0210_GATE=REJECTED")
        return 2
    print("N71_S8000_STOCK_PCIE_LOCAL_0210_GATE=PASS")
    print("N71_PORT_SLOT1504_0210_READ_AND_CONDITIONAL_SAME_VALUE_WRITE=YES")
    print("N71_PORT_SLOTS_2000_2008_BOUND_TO_LOCAL_ACCESSORS=YES")
    print("N71_0210_WRITE_ONE_CLEAR_ELECTRICAL_SEMANTICS=UNKNOWN")
    print("N71_0210_LINUX_REGISTER_WRITES=NONE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
