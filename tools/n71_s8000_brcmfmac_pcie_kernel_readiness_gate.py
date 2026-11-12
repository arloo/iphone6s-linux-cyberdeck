#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict OFFLINE Linux ARM64 Broadcom PCIe WLAN software-readiness gate for N71.

Separate source-verified facts from physical Apple A9/S8000 hardware support.
Requires a NEW build directory with BRCMFMAC/CFG80211 built-in. Validates
the original Linux Broadcom 14e4:43a3 PCI ID and firmware-name templates.
Does not probe PCI, map MMIO, perform IOMMU/DMA or load any module.
Never publishes or reads proprietary Apple Wi-Fi firmware contents.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

KNOWN_GOOD_LIVE_IMAGE_SHA256 = "fbf9ec6754245d48922e6da8b82c90e6c985ea088ed8ab896397af8e3f9f7845"
REQUIRED_BUILTIN = frozenset((
    "WIRELESS", "WLAN", "RFKILL", "CFG80211", "BRCMUTIL", "BRCMFMAC",
    "BRCMFMAC_PCIE", "BRCMFMAC_PROTO_MSGBUF", "PCI", "FW_LOADER",
))
MUST_REMAIN_DISABLED = frozenset((
    "BRCMFMAC_SDIO", "BRCMFMAC_USB", "NL80211_TESTMODE",
    "PCIE_APPLE_S8000_RESEARCH_GUARD",
))

class SoftwareReadinessUnproven(ValueError):
    pass

def require(ok,why):
    if not ok:raise SoftwareReadinessUnproven(why)

def config_dict(text:str)->dict[str,str]:
    settings={}
    for row in text.splitlines():
        if m:=re.fullmatch(r"CONFIG_([A-Z0-9_]+)=(y|m|n|[0-9]+|0x[0-9a-fA-F]+|\"[^\"\n]*\")",row):
            key,val=m.groups()
        elif m:=re.fullmatch(r"# CONFIG_([A-Z0-9_]+) is not set",row):
            key,val=m.group(1),"n"
        else:
            continue
        require(key not in settings,"Duplicate Kconfig symbol")
        settings[key]=val
    return settings

def check_config(baseline:str,candidate:str):
    old,new=config_dict(baseline),config_dict(candidate)
    require(old.get("WIRELESS")=="n" and old.get("WLAN")=="n",
            "The physically matching known-good boot is not the pinned wireless-disabled baseline")
    for key in REQUIRED_BUILTIN:
        require(new.get(key)=="y","Missing built-in required wireless software")
    for key in MUST_REMAIN_DISABLED:
        require(new.get(key,"n")=="n","Disallowed transport or hardware guard autostart")
    require(new.get("MODULES")=="y" and old.get("MODULES")=="y",
            "Linux native modules baseline missing")
    require(new.get("BT")==old.get("BT")=="y",
            "Existing BCM Bluetooth software must not be disabled")
    require(new.get("APPLE_DART")==old.get("APPLE_DART")=="y",
            "Original DART software config must be preserved without activating hardware")
    require(new.get("PCIE_APPLE")==old.get("PCIE_APPLE")=="y",
            "Original Apple host config must be preserved without adding new host hardware nodes")
    return True

def check_source(hw_header:str,pcie_source:str)->bool:
    require(bool(re.search(
        r"(?m)^#define\s+BRCM_PCIE_4350_DEVICE_ID\s+0x43a3\b",
        hw_header)), "Linux Broadcom 4350 14e4:43a3 ID not defined")
    require("BRCMF_PCIE_DEVICE(BRCM_PCIE_4350_DEVICE_ID," in pcie_source,
            "Expected brcmfmac PCIe device match absent")
    require('BRCMF_FW_DEF(4350C, "brcmfmac4350c2-pcie")' in pcie_source,
            "Expected Broadcom 4350C firmware template absent")
    require(bool(re.search(
        r"BRCMF_FW_ENTRY\(BRCM_CC_4350_CHIP_ID,\s*0x000000FF,\s*4350C\)",
        pcie_source)),
        "Broadcom 4350 revision-class C firmware selection mask absent")
    return True

def sha256(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def check_image(original:bytes,candidate:bytes)->bool:
    require(sha256(original)==KNOWN_GOOD_LIVE_IMAGE_SHA256,
            "Original physically booted kernel Image SHA changed")
    for src in (original,candidate):
        require(len(src)>1_000_000 and src[0x38:0x3c]==b"ARM\x64",
                "Not a Linux AArch64 Image")
    require(candidate!=original,
            "Candidate wireless Image unchanged from old Wi-Fi-disabled kernel")
    return True

def safe_read(path:Path,limit:int)->bytes:
    require(path.is_file() and not path.is_symlink(),
            "Required local software input missing")
    require(1<path.stat().st_size<limit,"Unexpected software input size")
    return path.read_bytes()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("old_config","new_config","brcm_hw_header",
                 "brcm_pcie_source","old_image"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--candidate-image",type=Path)
    a=parser.parse_args()
    try:
        old_config=safe_read(a.old_config,1_000_000).decode("utf8")
        new_config=safe_read(a.new_config,1_000_000).decode("utf8")
        check_config(old_config,new_config)
        check_source(safe_read(a.brcm_hw_header,100_000).decode("utf8"),
                     safe_read(a.brcm_pcie_source,300_000).decode("utf8"))
        original=safe_read(a.old_image,50_000_000)
        require(sha256(original)==KNOWN_GOOD_LIVE_IMAGE_SHA256,
                "Known-good original Apple A9 Linux image hash mismatch")
        if a.candidate_image:
            check_image(original,safe_read(a.candidate_image,50_000_000))
    except (SoftwareReadinessUnproven,OSError,UnicodeError):
        print("N71_S8000_BRCMFMAC_PCIE_OFFLINE_READINESS_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S8000_BRCMFMAC_PCIE_SOFTWARE_CONFIG_AND_PCI_ID_PASS")
    print("N71_S8000_KNOWN_GOOD_PHYSICAL_IMAGE_SHA_UNCHANGED=YES")
    print("N71_S8000_CFG80211_AND_BRCMFMAC_PCIE_BUILTIN_CONFIG=YES")
    print("N71_BROADCOM_DRIVER_RECOGNIZES_14E4_43A3=YES")
    print("N71_BRCM4350C_SOURCE_FIRMWARE_TEMPLATE_PRESENT=YES")
    print("N71_PRIVATE_BOARD_FIRMWARE_REQUIRES_SEPARATE_PROVENANCE_GATE=YES")
    print("N71_S8000_CANDIDATE_ARM64_IMAGE_BUILT_AND_DISTINCT="+
          ("YES" if a.candidate_image else "NOT_YET_CHECKED"))
    print("N71_S8000_PHYSICAL_PCIE_HOST_DART_DMA_AND_WLAN_INTERFACE_PROVEN=NO")
    print("N71_S8000_NO_FLASH_MMIO_DMA_RADIO_OR_MODULE_OPERATION=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
