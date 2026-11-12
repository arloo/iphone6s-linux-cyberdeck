#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71/S8000 read-only live iOS DART1+Wi-Fi PCIe port1 provenance gate.

Original N71 Apple ADT + PRIVATE named IORegistry snapshots captured from
a PASSCODE-UNLOCKED owner's iPhone 6s running original iOS. Reconciles the
actual original node properties, DART1 mapper, PCIe port index, CLKREQ,
force-active metadata, stable Gen1 x1 Apple iOS link and DART matched driver.

Do not confuse IORegistry metadata with live MMIO, DMA ownership or a
safe S8000 Linux boot. No physical access, no sensitive data is printed.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import plistlib
import struct
import sys

HERE=Path(__file__).resolve().parent

def module(alias,filename):
    sp=importlib.util.spec_from_file_location(alias,HERE/filename)
    assert sp and sp.loader
    m=importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m

ADT=module("live_n71_dart_adt","n71_s8000_adt_window_gate.py")
CENSUS=module("live_n71_dart_census","n71_dart1_consumer_census_gate.py")

FIELDS={
    "bridge1":(ADT.HOST+"/pci-bridge1",(
        "apcie-port","t-refclk-to-perst","function-clkreq",
        "function-dart_force_active")),
    "mapper1":(ADT.MAPPER,("reg",)),
    "dart1":(ADT.DART_PATHS[1],("reg",)),
}
REQUIRED_SIZE={
    "apcie-port":4,
    "t-refclk-to-perst":4,
    "function-clkreq":16,
    "function-dart_force_active":8,
    "reg":None,
}
SAFE_MAX_SNAPSHOT=1024*1024

class RejectedOriginalLive(Exception):
    pass

def must(condition,reason):
    if not condition:raise RejectedOriginalLive(reason)

def read_private_file(p:Path,max_bytes:int):
    must(p.is_file() and not p.is_symlink(),"Private source absent/symlink")
    n=p.stat().st_size
    must(8<n<=max_bytes,"Unqualified private source length")
    return p.read_bytes()

def read_registry(plist:bytes):
    must(8<len(plist)<=SAFE_MAX_SNAPSHOT,"Private IORegistry size invalid")
    try:
        obj=plistlib.loads(plist)
    except (ValueError,TypeError,plistlib.InvalidFileException) as exc:
        raise RejectedOriginalLive("Original IORegistry plist unavailable") from exc
    must(type(obj) is dict and type(obj.get("IORegistry")) is dict,
         "Original IORegistry missing dictionary")
    return obj["IORegistry"]

def original_expected(adt:bytes):
    original=CENSUS.audit_bytes(adt)
    must(original["dart1_mapper_declared_consumers"]==1 and
         original["dart1_child_nodes"]==1,
         "Original S8000 DART1 consumer graph not uniquely qualified")
    wanted={path for path,_ in FIELDS.values()}
    names=frozenset(key for _,(_,ks) in FIELDS.items() for key in ks)
    items={}
    def visitor(path,props):
        if path in wanted:
            must(path not in items,"Original Apple duplicate target node")
            items[path]=props
    try:
        ADT.ADT.parse_node(adt,0,"",visitor=visitor,
                           visit_all=True,extra_props=names)
    except (ADT.ADT.InvalidADT,struct.error) as exc:
        raise RejectedOriginalLive("Original Apple ADT malformed") from exc
    must(set(items)==wanted,"Original N71 DART1/port1 nodes missing")
    return items

def check_live(adt:bytes,live_bridge:bytes,live_mapper:bytes,
               live_dart:bytes,live_dart_driver:bytes):
    known=original_expected(adt)
    snapshots={
        "bridge1":read_registry(live_bridge),
        "mapper1":read_registry(live_mapper),
        "dart1":read_registry(live_dart),
    }
    for name,(path,fields) in FIELDS.items():
        original=known[path]
        runtime=snapshots[name]
        for key in fields:
            v=runtime.get(key)
            must(type(v) is bytes and v==original.get(key),
                 "Live/ADT private N71 PCIe metadata disagree")
            req=REQUIRED_SIZE[key]
            if req is not None:
                must(len(v)==req,
                     "Original Apple DART1/CLKREQ metadata width changed")
    # The real original DART1 child mapper describes logical index0,
    # which original Apple driver code was separately statically proven
    # to dispatch to the packed TCR byte lane0.
    must(struct.unpack("<I",snapshots["mapper1"]["reg"])[0]==0,
         "Original DART1 mapper Apple logical index not zero")
    bridge=snapshots["bridge1"]
    must(struct.unpack("<I",bridge["apcie-port"])[0]==1,
         "Apple original BCM4350 PCIe port is not 1")
    must(struct.unpack("<I",bridge["t-refclk-to-perst"])[0]==100,
         "Unreviewed original Apple reference-clock/PERST metadata value")
    must(bridge.get("IOPCIConfigured") is True and
         bridge.get("IOPCIResourced") is True,
         "Apple iOS port1 not configured and resourced")
    status=bridge.get("IOPCIExpressLinkStatus")
    must(type(status) is int and 0<=status<=0xffff,
         "Apple original iOS PCIe link status unavailable")
    speed=status & 0xf
    width=(status>>4)&0x3f
    training=(status>>11)&1
    stable=(status>>12)&1
    must(speed==1 and width==1 and not training and stable,
         "Apple original iOS native Wi-Fi Gen1x1 link not stable")
    drv=read_registry(live_dart_driver)
    must(drv.get("IOClass")=="AppleS5L8960XDART" and
         drv.get("IONameMatched")=="dart,s5l8960x" and
         drv.get("IOMatchedAtBoot") is True and
         drv.get("IOProviderClass")=="AppleARMIODevice",
         "Original Apple S5L DART driver not boot matched")
    return {"matched_props":sum(len(t[1]) for t in FIELDS.values()),
            "apple_port":1,
            "mapper_index":0,
            "speed_code":speed,
            "lane_width":width,
            "refclk_perst_metadata":100}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("private_n71_apple_adt",type=Path)
    ap.add_argument("private_live_pci_bridge1_plist",type=Path)
    ap.add_argument("private_live_mapper_apcie1_plist",type=Path)
    ap.add_argument("private_live_dart_apcie1_plist",type=Path)
    ap.add_argument("private_live_apple_s5l_dart_driver_plist",type=Path)
    args=ap.parse_args()
    try:
        checked=check_live(
            read_private_file(args.private_n71_apple_adt,
                              ADT.ADT.MAX_FILE),
            read_private_file(args.private_live_pci_bridge1_plist,
                              SAFE_MAX_SNAPSHOT),
            read_private_file(args.private_live_mapper_apcie1_plist,
                              SAFE_MAX_SNAPSHOT),
            read_private_file(args.private_live_dart_apcie1_plist,
                              SAFE_MAX_SNAPSHOT),
            read_private_file(args.private_live_apple_s5l_dart_driver_plist,
                              SAFE_MAX_SNAPSHOT))
    except Exception:
        # Never print user-specific original property values or paths.
        print("N71_ORIGINAL_LIVE_S8000_DART1_PCIE_PORT1_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_ORIGINAL_LIVE_S8000_DART1_PCIE_PORT1_PROVENANCE_PASS")
    print("ORIGINAL_AND_LIVE_N71_DART1_PORT1_MATCHED_PROPERTIES",
          checked["matched_props"])
    print("LIVE_S8000_PCIe_WLAN_PORT_INDEX",checked["apple_port"])
    print("LIVE_APPLE_DART1_LOGICAL_MAPPER_INDEX",checked["mapper_index"])
    print("LIVE_ORIGINAL_IOS_PCIE_SPEED_CODE",checked["speed_code"])
    print("LIVE_ORIGINAL_IOS_PCIE_NEGOTIATED_LANE_WIDTH",
          checked["lane_width"])
    print("LIVE_ORIGINAL_IOS_PCIE_GEN1_X1_TRAINING_OFF=YES")
    print("ORIGINAL_IOS_S5L8960X_DART_DRIVER_MATCHED_AT_BOOT=YES")
    print("ORIGINAL_REFCLK_TO_PERST_METADATA",checked["refclk_perst_metadata"])
    print("REFCLK_TO_PERST_METADATA_TIME_UNITS_PROVEN=NO")
    print("LIVE_DART1_HARDWARE_STREAM_ID_DMA_TTBR_PROVEN=NO")
    print("PORT1_LINUX_HARDWARE_INITIALIZATION_AUTHORIZED=NO")
    print("RAW_PRIVATE_LIVE_REGISTRY_PROPERTIES_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
