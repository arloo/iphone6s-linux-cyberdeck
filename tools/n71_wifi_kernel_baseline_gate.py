#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed Wi-Fi-only N71 kernel config regression gate, offline.

Compares a known-good native Apple N71 framebuffer/Z2/USB kernel config to
an isolated candidate enabling cfg80211+Broadcom PCIe. It does not build,
boot, flash or touch physical hardware. Outputs only aggregate statistics.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

RE_ASSIGN = re.compile(r"^(CONFIG_[A-Z0-9_]+)=(.*)$")
RE_DISABLED = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")
REQUIRED_BASE = {
    "CONFIG_ARCH_APPLE":"y",
    "CONFIG_PCI":"y",
    "CONFIG_INPUT_EVDEV":"y",
    "CONFIG_TOUCHSCREEN_APPLE_Z2":"y",
    "CONFIG_DRM":"y",
    "CONFIG_DRM_SIMPLEDRM":"y",
    "CONFIG_USB_GADGET":"y",
    "CONFIG_USB_CONFIGFS":"y",
    "CONFIG_USB_CONFIGFS_NCM":"y",
    "CONFIG_APPLE_DART":"y",
    "CONFIG_MODULES":"y",
}
REQUIRED_NEW = {
    "CONFIG_WIRELESS":"y",
    "CONFIG_WLAN":"y",
    "CONFIG_CFG80211":"m",
    "CONFIG_BRCMUTIL":"m",
    "CONFIG_BRCMFMAC":"m",
    "CONFIG_BRCMFMAC_PCIE":"y",
    "CONFIG_APPLE_DART":"y",
    "CONFIG_GPIO_APPLE_PMIC":"m",
    "CONFIG_BRCMFMAC_SDIO":"n",
    "CONFIG_BRCMFMAC_USB":"n",
}
ALLOW_CHANGED_ORIGINAL = frozenset(("CONFIG_WIRELESS","CONFIG_WLAN"))
class UnqualifiedConfig(ValueError):
    pass

def need(ok:bool,msg:str):
    if not ok:raise UnqualifiedConfig(msg)

def parse_kconfig(blob:bytes)->dict[str,str]:
    need(0<len(blob)<4_000_000,"Invalid Linux Kconfig file size")
    try:lines=blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as e:raise UnqualifiedConfig("Invalid text encoding") from e
    data={}
    for line in lines:
        m=RE_ASSIGN.fullmatch(line)
        if m:
            key,value=m.groups()
        else:
            m=RE_DISABLED.fullmatch(line)
            if not m:continue
            key,value=m.group(1),"n"
        need(key not in data,"Duplicate Kconfig key")
        need(0<len(value)<256,"Unexpected Kconfig value")
        data[key]=value
    return data

def verify(base:dict[str,str],new:dict[str,str])->dict[str,int]:
    for key,want in REQUIRED_BASE.items():
        need(base.get(key)==want and new.get(key)==want,
             "Known-good N71 kernel feature removed or altered: "+key)
    for key,want in REQUIRED_NEW.items():
        need(new.get(key,"n")==want,
             "Expected Broadcom PCIe / Apple baseline gate failed: "+key)
    need(new.get("CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD","n")=="n",
         "Unsafe/unreviewed S8000 PCIe research guard enabled")
    need(new.get("CONFIG_BRCMSMAC","n")=="n",
         "Unneeded Broadcom SoftMAC enabled")
    need(base.get("CONFIG_WIRELESS","n")=="n" and
         base.get("CONFIG_WLAN","n")=="n",
         "Baseline radio state unexpectedly different")
    changed_original=[]
    preserved=0
    for key,old in base.items():
        current=new.get(key,"n")
        if old in ("y","m"):
            need(current==old,"Known-good enabled Linux feature altered: "+key)
            preserved+=1
        elif old=="n" and current in ("y","m") and key not in (
            ALLOW_CHANGED_ORIGINAL
        ):
            # New options appearing as 'n' in old config were possible
            # but should not enable unrelated peripherals or root drivers.
            need(key.startswith(("CONFIG_CFG80211","CONFIG_BRCM",
                                 "CONFIG_WLAN_VENDOR","CONFIG_IEEE80211")),
                 "Previously disabled nonwireless feature enabled: "+key)
        if old!=current:changed_original.append(key)
    need(new.get("CONFIG_MODULE_UNLOAD","n") ==
         base.get("CONFIG_MODULE_UNLOAD","n"),
         "Module-unload behavior unexpectedly changed")
    return {"preserved_enabled_symbols":preserved,
            "original_flags_changed":len(changed_original),
            "candidate_symbol_count":len(new)}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("known_good_config",type=Path)
    ap.add_argument("candidate_wifi_config",type=Path)
    args=ap.parse_args()
    try:
        a,b=args.known_good_config.read_bytes(),args.candidate_wifi_config.read_bytes()
        result=verify(parse_kconfig(a),parse_kconfig(b))
    except (OSError,UnqualifiedConfig) as exc:
        print("N71_WIFI_CONFIG_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_KNOWN_GOOD_LINUX_CORE_CONFIG_PRESERVED_PASS")
    print("PRESERVED_ENABLED_BASELINE_SYMBOLS",result["preserved_enabled_symbols"])
    print("ORIGINAL_SYMBOL_CHANGES",result["original_flags_changed"])
    print("BRCMFMAC_PCIE_AND_CFG80211_CONFIGURED_OFFLINE=YES")
    print("S8000_PCIE_HOST_AND_NATIVE_WIFI_OPERATIONAL=NO")
    print("NO_PHONE_BOOT_OR_MMIO_OR_NAND_ACCESS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
