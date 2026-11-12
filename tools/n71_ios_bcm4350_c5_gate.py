#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Safely identify N71 onboard BCM4350 C5 requests from a PRIVATE iOS plist.

Reads only local private AppleBCMWLANCore IORegistry and the names of the
private original Apple firmware package files; prints only sanitized variant
status. Does NOT read OTP, MAC, NVRAM contents, radio profiles, or load
firmware. No file is created or changed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import plistlib
import sys

EXPECTED={"Firmware":".trx","NVRAM":".txt",
          "Regulatory":".clmb","TxCap":".txcb"}
PREFIX="C-4350__s-C5/"
LIMIT=2_000_000

class RejectedFirmwareMetadata(ValueError):
    pass

def must(ok:bool,why:str)->None:
    if not ok:raise RejectedFirmwareMetadata(why)

def validate_core_plist(data:bytes)->dict[str,str]:
    must(0<len(data)<=LIMIT,"Private iOS plist size rejected")
    try:
        parsed=plistlib.loads(data)
    except Exception as exc:
        raise RejectedFirmwareMetadata("Unreadable private iOS registry") from exc
    must(isinstance(parsed,dict) and "IORegistry" in parsed,
         "Missing private IORegistry entry")
    core=parsed["IORegistry"]
    must(isinstance(core,dict),"Invalid BCM4350 registry entry")
    must(type(core.get("ChipSet")) is int and core["ChipSet"]==4350,
         "Original iOS WLAN chipset does not identify BCM4350")
    must(core.get("FirmwareLoaded") is True,
         "Original iOS firmware-load state not confirmed")
    must(core.get("IOClass")=="AppleBCMWLANCore" and
         core.get("IOProviderClass")=="AppleBCMWLANBusInterfacePCIe",
         "Unexpected iOS WLAN core/PCIe class")
    config=core.get("PlatformConfigFileName")
    must(isinstance(config,str) and
         "albarossa" in config.lower() and len(config)<256,
         "Unexpected N71 platform configuration family")
    requests=core.get("RequestedFiles")
    must(isinstance(requests,list) and len(requests)==1 and
         isinstance(requests[0],dict) and
         set(requests[0])==set(EXPECTED),
         "Original iOS file requests are missing/ambiguous")
    results={}
    for kind,suffix in EXPECTED.items():
        name=requests[0][kind]
        must(isinstance(name,str) and name.startswith(PREFIX) and
             name.endswith(suffix) and len(name)<256 and
             name.count("/")==1,
             "Original iOS request is not a bounded C5 filename")
        base=name[len(PREFIX):]
        must(base and base not in (".","..") and
             "/" not in base and chr(92) not in base and
             ".." not in base,
             "Invalid firmware filename")
        results[kind]=base
    return results

def verify_bundle_files(requests:dict[str,str],root:Path)->None:
    must(root.is_dir() and not root.is_symlink(),
         "Original private Apple firmware bundle directory not available")
    # Validate file names only. No original firmware or private calibration
    # bytes are opened, hashed, copied, displayed, or uploaded.
    for kind,basename in requests.items():
        matches=[p for p in root.rglob(basename)
                 if p.is_file() and not p.is_symlink()
                 and "C-4350__s-C5" in p.parts]
        must(len(matches)==1 and
             0<matches[0].stat().st_size<=32_000_000,
             "Original extracted C5 asset missing or ambiguous")

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_ios_bcmwlan_core_plist",type=Path)
    p.add_argument("private_original_apple_wifi_bundle_dir",type=Path)
    a=p.parse_args()
    try:
        must(0<a.private_ios_bcmwlan_core_plist.stat().st_size<=LIMIT,
             "Original live iOS snapshot size rejected")
        expected=validate_core_plist(
            a.private_ios_bcmwlan_core_plist.read_bytes())
        verify_bundle_files(
            expected,a.private_original_apple_wifi_bundle_dir)
    except (OSError,RejectedFirmwareMetadata) as exc:
        print("N71_BCM4350_IOS_C5_MATCH_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_BCM4350_ORIGINAL_LIVE_IOS_REQUESTS_C5_PASS")
    print("CHIPSET=4350 PLATFORM=ALBAROSSA IOS_FIRMWARE_LOADED=YES")
    print("REQUESTED_C5_ASSET_TYPES",",".join(EXPECTED))
    print("ALL_FOUR_REQUESTED_ASSETS_HAVE_UNIQUE_PRIVATE_C5_BUNDLE_MATCH=YES")
    print("PRIVATE_FIRMWARE_OR_CALIBRATION_EXPORTED=NO")
    print("HARDWARE_BLOCKED: no Linux firmware loading or PCIe/DART radio access")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
