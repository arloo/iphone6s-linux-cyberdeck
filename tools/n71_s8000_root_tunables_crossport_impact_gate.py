#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A9/S8000 four-port cross-port PCIe root-tunable impact gate (OFFLINE).

Inputs: owner-private Apple original N71 ADT, paired stock-iOS IORegistry
root+port1 snapshots and original Apple ARM64 kernelcache. Reuses the
existing trusted 83-record ADT/iOS/software-width verification, then finds
cross-port aliasing with four per-port selector-bank offsets.

This is a *risk classification*, NOT qualification to write registers.
No MMIO, DMA, NAND, PMIC, PCIe, shell connection, or on-phone actions.
Never emits per-device tunable masks/values or original binary contents.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location(
    "n71_private_crossport_provenance",
    HERE/"n71_s8000_private_pcie_tunable_stage_gate.py")
assert SPEC and SPEC.loader
T=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=T
SPEC.loader.exec_module(T)

ROOT_GROUP="apcie-common-tunables"
PROTECTED_PORTS=(0,2,3)
TOTAL=83
REGION_ROOT_SHARED=0x8000
SELECTORS={2:0x100,3:0x114,4:0x124,5:0x12c}
PORT_STRIDE=0x80
STATUS_SHARED=0x2c
EXPECTED_CROSSPORT={(port,2,0x100+PORT_STRIDE*port) for port in range(4)}

class UnqualifiedCrossPortWrite(ValueError):
    pass

def check(ok,reason):
    if not ok:raise UnqualifiedCrossPortWrite(reason)

def mapping():
    """Official S8000 original six-case relative-register selector derivation."""
    return {(port,selector):base+port*PORT_STRIDE
            for port in range(4)
            for selector,base in SELECTORS.items()}

def classify_original_records(groups):
    check(set(groups)==set(T.PROPS),"Unexpected Apple tunable banks")
    for name,(_,count,size) in T.PROPS.items():
        check(len(groups[name])==count,"Unexpected original record count")
        seen=set()
        for row in groups[name]:
            check(set(row)=={"offset","width","candidate_mask","candidate_value"},
                  "Unexpected original tunable field")
            o,w,m,v=(row[k] for k in
                     ("offset","width","candidate_mask","candidate_value"))
            check(all(type(x) is int for x in (o,w,m,v)),
                  "Non-integer original tunable")
            check(w==4 and o%4==0 and 0<=o<=size-4,
                  "Unbounded or unaligned original register")
            check(0<=m<=0xffffffff and 0<=v<=0xffffffff and not v&~m,
                  "Invalid masked RMW record")
            check(o not in seen,
                  "Duplicate original tunable offset within same bank")
            seen.add(o)
    check(sum(len(x) for x in groups.values())==TOTAL,
          "Original record total not verified")
    root={r["offset"]:r for r in groups[ROOT_GROUP]}
    check(STATUS_SHARED not in root,
          "Original root status offset must not be directly written")
    targets=mapping()
    collisions={(port,selector,offset) for (port,selector),offset
                in targets.items() if offset in root}
    check(collisions==EXPECTED_CROSSPORT,
          "Unrecognized cross-port common-register aliases")
    check(all(root[offset]["candidate_mask"]!=0 and
              (root[offset]["candidate_mask"]&1)==0
              for _,_,offset in collisions),
          "Original cross-port RMW effect mask changed")
    check(not any(row["offset"]==0x1ac for row in groups[ROOT_GROUP]),
          "Original per-port link/status read offset unexpectedly modified")
    check(not ({r["offset"] for r in groups["apcie-config-tunables"]} &
               {r["offset"] for r in groups["pcie-rc-tunables"]}),
          "Original port1 tuning sub-banks unexpectedly overlap")
    # Different resource mapping domains can use the same relative offset.
    # Never infer cross-bank physical address collisions without validated bases.
    return {
        "total":TOTAL,
        "root_common_records":len(root),
        "crossport":len(collisions),
        "protected_ports":tuple(port for port in PROTECTED_PORTS
                                 if (port,2,targets[port,2]) in collisions),
        "port1_id2":(1,2,targets[1,2]) in collisions,
        "status_direct":STATUS_SHARED in root,
        "port1_link_status_tuned":0x1ac in root,
        "root_write_safely_isolated":False,
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for opt in ("original_apple_adt","stock_ios_apcie_plist",
                "stock_ios_port1_plist","original_arm64_kernelcache"):
        ap.add_argument(opt,type=Path)
    a=ap.parse_args()
    try:
        T.verify_original_apple_tunable_code(
            T.read_private(a.original_arm64_kernelcache,150_000_000))
        records=T.corroborate(
            T.read_private(a.original_apple_adt,T.ADT.ADT.MAX_FILE),
            T.read_private(a.stock_ios_apcie_plist,T.MAX_PLIST_SIZE),
            T.read_private(a.stock_ios_port1_plist,T.MAX_PLIST_SIZE))
        results=classify_original_records(records)
    except (OSError,ValueError,KeyError,TypeError,AssertionError):
        print("N71_S8000_CROSSPORT_ROOT_TUNABLE_PROVENANCE_NOT_QUALIFIED",
              file=sys.stderr)
        return 2
    print("N71_S8000_APPLE_PCIE_ROOT_CROSSPORT_TUNABLE_PROVENANCE_PASS")
    print("N71_ORIGINAL_APPLE_ADT_STOCK_IOS_AND_ARM64_FORMAT_MATCH=YES")
    print("N71_ORIGINAL_TUNABLE_TOTAL",results["total"])
    print("N71_COMMON_ROOT_TUNABLE_RECORDS",results["root_common_records"])
    print("N71_COMMON_ROOT_RELATIVE_REGISTERS_ALIAS_SELECTOR_ID2_ALL_FOUR_PORTS=YES")
    print("N71_CROSSPORT_ALIAS_TOTAL",results["crossport"])
    print("N71_PROTECTED_STORAGE_PORT0_COMMON_ALIAS=YES")
    print("N71_WLAN_PORT1_COMMON_ALIAS=YES")
    print("N71_PROTECTED_BASEBAND_PORT2_COMMON_ALIAS=YES")
    print("N71_PROTECTED_UNKNOWN_PORT3_COMMON_ALIAS=YES")
    print("N71_DIRECT_ORIGINAL_COMMON_STATUS_0X2C_WRITE=NO")
    print("N71_DIRECT_ORIGINAL_PORT1_STATUS_0X1AC_WRITE=NO")
    print("N71_S8000_SHARED_ROOT_BANK_REPLAY_AS_PORT1_ONLY_SAFE=NO")
    print("N71_CROSSPORT_MMIO_REGISTER_SIDE_EFFECTS_AND_DART_SID_PROVEN=NO")
    print("N71_HARDWARE_DMA_NAND_RADIO_AND_LINUX_PCIE_WRITES_AUTHORIZED=NO")
    print("N71_ORIGINAL_PRIVATE_MASKS_VALUES_OR_CALIBRATION_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
