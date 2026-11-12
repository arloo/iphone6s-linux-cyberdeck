#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate exact 100-us port1 research metadata in an OWNER-PRIVATE N71 FDT.

The initial physical guarded boot was safely rejected: fdtput -t x "100"
writes hexadecimal 0x100 = 256 us, while the verified original A9 delay is
decimal 100 us = hexadecimal 0x64. Inspect ONLY existing FDT metadata, do not
touch hardware, and do not weaken the fail-closed kernel driver.
No original DTB bytes, calibration, credentials or device IDs are printed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

NODE="/soc/pcie-port1-preflight@602000000"
GOOD_COMPAT="apple,s8000-pcie-research-blocked"
EXPECTED_REG=(
 0x6,0x02000000,0,0x4000,
 0x6,0x02004000,0,0x4000,
 0x6,0x02008000,0,0x4000,
)

class UnprovenMetadata(ValueError):
    pass

def decode_hex_cells(raw:str)->tuple[int,...]:
    parts=raw.strip().split()
    if not parts or len(parts)>32:
        raise UnprovenMetadata("unexpected FDT cell count")
    if not all(re.fullmatch(r"[0-9a-fA-F]{1,8}",p) for p in parts):
        raise UnprovenMetadata("malformed FDT hex cells")
    return tuple(int(v,16) for v in parts)

def validate_snapshot(props:dict[str,str])->bool:
    """Fail closed on anything besides the exact inert metadata profile."""
    expected_keys={
        "compatible","status","reg","reg-names","hardware-block",
        "research-port","dart-mapper","refclk-us"
    }
    if set(props)!=expected_keys:
        raise UnprovenMetadata("required original N71 metadata unavailable")
    if props["compatible"].strip()!=GOOD_COMPAT or props["status"].strip()!="okay":
        raise UnprovenMetadata("wrong synthetic port1 compatibility")
    if props["reg-names"].strip()!="port1-reg-a port1-reg-b dart1-reg":
        raise UnprovenMetadata("changed N71/DART1 resource order")
    if decode_hex_cells(props["reg"])!=EXPECTED_REG:
        raise UnprovenMetadata("unexpected N71 physical address descriptors")
    if props["hardware-block"]!="YES":
        raise UnprovenMetadata("hardware activation prohibition absent")
    if decode_hex_cells(props["research-port"])!=(1,):
        raise UnprovenMetadata("not Apple PCIe port1")
    if decode_hex_cells(props["dart-mapper"])!=(0,):
        raise UnprovenMetadata("not expected original DART mapper0")
    value=decode_hex_cells(props["refclk-us"])
    if value!=(100,):
        raise UnprovenMetadata("incorrect refclk-to-PERST delay, expected 100 us")
    return True

def fdtget(path:Path,*args:str)->str:
    return subprocess.run(["fdtget",*args[:2],str(path),*args[2:]],
                          check=True,capture_output=True,
                          text=True,timeout=8).stdout.strip()

def real_snapshot(path:Path)->dict[str,str]:
    if path.is_symlink() or not path.is_file() or not (10000<path.stat().st_size<200000):
        raise UnprovenMetadata("unexpected private FDT file type/size")
    def x(prop):return fdtget(path,"-t","x",NODE,prop)
    def s(prop):return fdtget(path,"-t","s",NODE,prop)
    def p():return subprocess.run(["fdtget","-p",str(path),NODE],
                       check=True,capture_output=True,text=True,timeout=8).stdout
    props_list=p().splitlines()
    if len(props_list)!=len(set(props_list)):
        raise UnprovenMetadata("unexpected duplicated OF property")
    return {
        "compatible":s("compatible"),
        "status":s("status"),
        "reg":x("reg"),
        "reg-names":s("reg-names"),
        "hardware-block":"YES" if "research,hardware-activation-blocked" in props_list else "NO",
        "research-port":x("research,pcie-port-index"),
        "dart-mapper":x("research,dart1-mapper-index"),
        "refclk-us":x("research,refclk-to-perst-delay-us")
    }

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("private_n71_dtb",type=Path)
    args=a.parse_args()
    try:
        validate_snapshot(real_snapshot(args.private_n71_dtb))
    except (UnprovenMetadata,OSError,subprocess.SubprocessError):
        print("N71_PORT1_100US_REFCLK_METADATA_NOT_PROVEN",file=sys.stderr)
        return 2
    print("N71_S8000_PORT1_REFCLK_100US_INERT_FDT_METADATA_GATE_PASS")
    print("N71_ORIGINAL_RESEARCH_REFCLK_TO_PERST_US_DECIMAL=100")
    print("N71_PORT1_ORIGINAL_3_RESOURCE_WINDOWS_AND_MAPPER0_VERIFIED=YES")
    print("N71_HARDWARE_ACTIVATION_BLOCKED_PROPERTY_PRESENT=YES")
    print("N71_NO_MMIO_DMA_NAND_OR_RADIO_OPERATION_PERFORMED=YES")
    print("N71_NATIVE_WIFI_FUNCTIONALITY_NOT_PROVEN=YES")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
