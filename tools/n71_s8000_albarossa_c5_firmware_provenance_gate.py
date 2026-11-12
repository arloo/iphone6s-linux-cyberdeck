#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict ORIGINAL-APPLE-SOURCE N71/S8000 BCM4350C5 firmware provenance gate.

Reads only owner-private original stock-iOS IORegistry plist, the *previously
locally extracted* iOS 15.8.8 C-4350__s-C5/albarossa firmware directory and
the private, not-yet-installed Linux staging directory. Never exports firmware,
per-device calibration/WMac, OTP vendor selection, serial, SSID or passwords.

Verifies 3 exact binary-equivalent Apple-to-Linux components and 14 untouched
stock module-specific NVRAM alternatives. No guessing the real physical
module OTP; no device connection, kernel, NAND, DART, MMIO or RF action.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import plistlib
import re
import sys

LINUX_PREFIX="brcmfmac4350c2-pcie.apple,albarossa"
ORIG_TO_LINUX={
 "albarossa.trx":LINUX_PREFIX+".bin",
 "albarossa.clmb":LINUX_PREFIX+".clm_blob",
 "albarossa.txcb":LINUX_PREFIX+".txcap_blob",
}
VARIANT=re.compile(r"^P-albarossa_M-([A-Z0-9]+)_V-([a-z])__m-([0-9]+(?:\.[0-9]+)?)\.txt$")
PROFILES=14
TOTAL=17

class UnprovenFirmware(ValueError):pass
def need(ok,why):
    if not ok:raise UnprovenFirmware(why)

def validate_profile_name(name:str)->str:
    m=VARIANT.fullmatch(name)
    need(m is not None,"Unqualified original N71 NVRAM variant")
    module,vendor,version=m.groups()
    need(module=="BLMA" and vendor in ("m","u","t"),
         "Unqualified original N71 radio module or vendor")
    return f"{LINUX_PREFIX}-{module}-{vendor}-{version}.txt"

def sha(data:bytes):return hashlib.sha256(data).digest()

def exact_file(path:Path,max_bytes:int=2_000_000)->bytes:
    need(path.is_file() and not path.is_symlink(),
         "Private input file absent or symlinked")
    size=path.stat().st_size
    need(100<size<=max_bytes,"Unexpected Apple source size")
    return path.read_bytes()

def verify_sources(live:bytes,original:dict[str,bytes],
                   private_linux:dict[str,bytes])->bool:
    try: registry=plistlib.loads(live)["IORegistry"]
    except (ValueError,TypeError,KeyError,plistlib.InvalidFileException):
        raise UnprovenFirmware("Original stock-iOS WLAN snapshot malformed")
    need(type(registry) is dict and
         registry.get("module-instance",b"").rstrip(b"\0")==b"albarossa",
         "Original iPhone 6s WLAN module not verified as albarossa")
    need(len(original)==TOTAL and len(private_linux)==TOTAL,
         "Original C5 firmware source or staged variant inventory incomplete")
    expected={}
    for src,dst in ORIG_TO_LINUX.items():
        need(src in original,"C5 Apple common firmware component missing")
        expected[dst]=original[src]
    nvram=[name for name in original if name not in ORIG_TO_LINUX]
    need(len(nvram)==PROFILES,"Expected 14 generic Apple C5 NVRAM variants")
    for name in nvram:
        target=validate_profile_name(name)
        need(target not in expected,"Duplicate Linux NVRAM variant")
        expected[target]=original[name]
    need(set(private_linux)==set(expected),
         "Unrecognized private firmware files or missing exact target")
    for name,value in expected.items():
        need(type(value) is bytes and len(value)>100,
             "Invalid private original Apple firmware bytes")
        other=private_linux[name]
        need(type(other) is bytes and sha(other)==sha(value) and len(other)==len(value),
             "Renamed Linux component differs from authentic Apple C5 original")
    return True

def inventory(directory:Path):
    need(directory.is_dir() and not directory.is_symlink(),
         "Required original/staged directory absent")
    items={}
    for f in directory.iterdir():
        need(f.name not in items and f.is_file() and not f.is_symlink(),
             "Unexpected source entry or duplicate")
        need(len(items)<TOTAL,"Excess original or staged components")
        items[f.name]=exact_file(f)
    return items

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for name in ("private_ios_live_wlan_plist","private_original_c5_apple_directory",
                 "private_staged_brcm_directory"):
        a.add_argument(name,type=Path)
    args=a.parse_args()
    try:
        live=exact_file(args.private_ios_live_wlan_plist,1_000_000)
        original=inventory(args.private_original_c5_apple_directory)
        staged=inventory(args.private_staged_brcm_directory)
        verify_sources(live,original,staged)
    except (UnprovenFirmware,OSError):
        print("N71_S8000_ORIGINAL_ALBAROSSA_C5_FIRMWARE_PROVENANCE_NOT_QUALIFIED",
              file=sys.stderr)
        return 2
    print("N71_S8000_IOS_15_8_8_ALBAROSSA_C5_FIRMWARE_PRIVATE_PROVENANCE_PASS")
    print("N71_IOS_LIVE_WLAN_MODULE_INSTANCE_ALBAROSSA_PASS=YES")
    print("N71_ORIGINAL_3_APPLE_C5_FW_COMPONENTS_EQUIVALENT_TO_BRCMFMAC=YES")
    print("N71_ORIGINAL_STOCK_APPLE_NVRAM_VARIANTS_PROVEN=14")
    print("N71_ORIGINAL_PRIVATE_LINUX_FIRMWARE_FILES_VERIFIED=17")
    print("N71_SPECIFIC_DEVICE_OTP_VENDOR_VERSION_SELECTED=NO")
    print("N71_PRIVATE_SYSCFG_WMAC_WCAL_DEVICE_CALIBRATION_INCLUDED=NO")
    print("N71_REAL_PCIE_DART_DMA_WIFI_LINK_STILL_UNPROVEN=YES")
    print("N71_NO_PROPRIETARY_FIRMWARE_OR_DEVICE_IDENTIFIERS_PUBLISHED=YES")
    return 0

if __name__=="__main__":raise SystemExit(main())
