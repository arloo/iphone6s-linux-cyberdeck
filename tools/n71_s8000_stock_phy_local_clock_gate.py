#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original N71/S8000 stock PCIe PHY and per-port-clock source gate.

The owner supplies the original, private Apple Device Tree at execution.
Never exports original mask/value bytes, stock firmware, board IDs or data.
This validates hardware descriptions, NOT actual clock activation or DMA.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import n71_original_apple_adt_iommu_parent_graph_gate as ADT

TUNE = struct.Struct("<IIQQ")
PHY_COUNT = 41
APP_PHY_PHYS = 0x600008000
APP_ROOT_PHYS = 0x600000000
PORT_WINDOWS = (
    0x601000000, 0x601004000,
    0x602000000, 0x602004000,
    0x603000000, 0x603004000,
    0x604000000, 0x604004000,
)
STOCK_CLOCK_IDS = tuple(range(0x39,0x3f))
STOCK_CLOCK_DEVICES = (
    "PCIE_AUX", "PCIE_REF", "PCIE_LINK0",
    "PCIE_LINK1", "PCIE_LINK2", "PCIE_LINK3",
)

class RejectedSource(ValueError):
    pass

def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RejectedSource(reason)

def tune_records(raw: bytes, count: int, size: int) -> dict[int, tuple[int, int]]:
    require(isinstance(raw, bytes) and len(raw) == count*TUNE.size,
            "Original Apple S8000 PCIe tunables length changed")
    decoded: dict[int, tuple[int,int]] = {}
    for off, width, mask, val in TUNE.iter_unpack(raw):
        require(width == 4 and off % 4 == 0 and off+4 <= size,
                "Invalid stock original per-register width or region")
        require(mask and mask <= 0xffffffff and val <= 0xffffffff and
                val & ~mask == 0 and off not in decoded,
                "Unrecognized original mask/value or duplicate offset")
        decoded[off] = (mask,val)
    return decoded

def verify_nodes(nodes: dict[str,dict[str,bytes]]) -> dict[str,int]:
    common = nodes.get(ADT.ROOT + "apcie")
    pmgr = nodes.get(ADT.ROOT + "pmgr")
    require(isinstance(common,dict) and isinstance(pmgr,dict),
            "Missing original Apple N71 controller or PMGR")
    require(b"apcie,s8000\0" == common.get("compatible"),
            "Not the genuine Apple S8000 PCIe controller")
    resources = common.get("reg",b"")
    require(len(resources)==11*16,
            "Original PCIe resources count changed")
    regs = tuple(struct.iter_unpack("<QQ", resources))
    require(regs[0]==(0x610000000,0x1000000) and
            regs[9]==(APP_ROOT_PHYS,0x8000) and
            regs[10]==(APP_PHY_PHYS,0x4000),
            "Original root/PHY resource mapping changed")
    for idx,address in enumerate(PORT_WINDOWS,1):
        require(regs[idx]==(address,0x4000),
                "Original PCIe per-port dual-bank MMIO map changed")
    require(common.get("clock-gates")==
            struct.pack("<6I",*STOCK_CLOCK_IDS),
            "Original Apple S8000 link/reference/aux gate hierarchy changed")
    require(common.get("power-gates")==struct.pack("<I",0x38),
            "Original shared root power gate changed")
    phy=tune_records(common.get("apcie-phy-tunables",b""),PHY_COUNT,0x4000)
    root=tune_records(common.get("apcie-common-tunables",b""),34,0x8000)
    require(all(offset in phy for offset in
                (0x108,0x118,0x308,0x318,0x518,0x1a18,0x1a58)),
            "Original sampled PHY register identity changed")
    require(0x2c not in root,"Original shared PCIe status register tuned")

    clock_table = pmgr.get("clocks",b"")
    require(len(clock_table)==9*24,
            "Original S8000 PMGR clock metadata count changed")
    app_clock=clock_table[5*24:6*24]
    require(struct.unpack_from("<I",app_clock,0)[0] == 0x06010022 and
            app_clock[8:].split(b"\0",1)[0] == b"PCIE_APP",
            "Original independent PCIE_APP clock identity changed")
    devices=pmgr.get("devices",b"")
    require(len(devices)==103*48,"PMGR device dictionary changed")
    for ident,name in zip(STOCK_CLOCK_IDS,STOCK_CLOCK_DEVICES):
        found=[record for (record,) in ((devices[k:k+48],)
               for k in range(0,len(devices),48))
               if record[3]==ident]
        require(len(found)==1 and
                found[0][32:48].split(b"\0",1)[0] == name.encode(),
                "Unexpected PMGR PCIe power state identity")

    banks: dict[int,tuple[bytes,bytes]] = {}
    for port in (0,1,2):
        path=ADT.ROOT+f"apcie/pci-bridge{port}"
        info=nodes.get(path)
        require(isinstance(info,dict),"Missing genuine S8000 PCIe bridge")
        c=info.get("apcie-config-tunables",b"")
        r=info.get("pcie-rc-tunables",b"")
        tune_records(c,6,0x4000)
        tune_records(r,2,0x4000)
        banks[port]=(c,r)
    require(banks[0]==banks[1]==banks[2],
            "Original S8000 port0, WLAN1 and baseband2 differ")
    return {"phy_records":len(phy),"common_records":len(root),
            "per_port_config_records":6,"per_port_root_records":2,
            "compared_ports":3,"phy_mmio_regions":1,
            "port_local_mmio_regions":8}

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_private_adt",type=Path)
    args=parser.parse_args()
    try:
        result=verify_nodes(ADT.parse_adt(args.original_private_adt.read_bytes()))
    except (OSError,RejectedSource,ValueError,KeyError,struct.error):
        print("N71_STOCK_PHY_LOCAL_CLOCK_SOURCE_GATE=REJECTED")
        raise SystemExit(1) from None
    print("N71_STOCK_PHY_LOCAL_CLOCK_SOURCE_GATE=PASS")
    for key,val in result.items():
        print("N71_SOURCE_"+key.upper()+"="+str(val))
    print("N71_STOCK_PCIE_APP_SEPARATE_CLOCK_DESCRIPTOR=YES")
    print("N71_PORT0_1_2_TUNABLE_BANKS_BYTE_IDENTICAL=YES")
    print("N71_PHY_CLOCK_ACTUAL_ENABLE_PROVEN=NO")
    print("N71_STORAGE_DMA_AND_NVME_OPERATION=NO")

if __name__=="__main__":
    main()
