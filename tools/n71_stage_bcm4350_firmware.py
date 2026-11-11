#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Privately stage original N71 BCM4350 Wi-Fi firmware for Linux brcmfmac.

Inputs must be extracted from an operator-owned authentic iPhone 6s IPSW.
Do not publish original Broadcom/Apple firmware, profiles or calibration.

Stages C2 and C5 in separate, inaccessible-by-default directories.
DOES NOT SELECT the actual WLAN silicon revision or configure radio/PCIe.
Firmware basename is from the Linux BCM4350 PCIe driver; final device
board type, required revision and SysCfg profile must be confirmed live.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib
import os
import re
import shutil
import stat
import sys

FAMILIES=("C-4350__s-C2","C-4350__s-C5")
COMPONENTS={
    "albarossa.trx":"brcmfmac4350c2-pcie.apple,albarossa.bin",
    "albarossa.clmb":"brcmfmac4350c2-pcie.apple,albarossa.clm_blob",
    "albarossa.txcb":"brcmfmac4350c2-pcie.apple,albarossa.txcap_blob",
}
MAX_BYTES={
    "albarossa.trx":3_000_000,
    "albarossa.clmb":100_000,
    "albarossa.txcb":30_000,
}
PROFILE_NAME=re.compile(r"P-albarossa_M-(?:BLMA|STBL)_V-[mtu]__m-[0-9]+\.[0-9]+\.txt\Z")

class UnsafeFirmwareStaging(ValueError):
    pass

def require(cond:bool,reason:str)->None:
    if not cond:raise UnsafeFirmwareStaging(reason)

def valid_regular_file(p:Path,limit:int)->bool:
    st=p.lstat()
    return stat.S_ISREG(st.st_mode) and 0<st.st_size<=limit

def inspect_private_source(root:Path)->dict[str,dict[str,Path]]:
    require(root.is_absolute(),"Source root must be absolute")
    require(root.is_dir() and not root.is_symlink(),"Invalid source directory")
    results={}
    for family in FAMILIES:
        base=root/family
        require(base.is_dir() and not base.is_symlink(),
                "Missing authentic C2 or C5 firmware family")
        names={}
        for entry in base.iterdir():
            name=entry.name
            if name in COMPONENTS:
                limit=MAX_BYTES[name]
            elif PROFILE_NAME.fullmatch(name) is not None:
                limit=32_768
            else:
                raise UnsafeFirmwareStaging("Unexpected firmware input name")
            require(valid_regular_file(entry,limit),
                    "Unreadable or unsafe private firmware source")
            names[name]=entry
        require(all(name in names for name in COMPONENTS),
                "One of the three native BCM4350 firmware components is missing")
        require(any(PROFILE_NAME.fullmatch(x) for x in names),
                "No original Apple module-revision profiles found")
        require(len(names)<=64,
                "Excessive original firmware profile count")
        results[family]=names
    return results

def stage(src:Path,dest:Path)->dict[str,int]:
    repo=Path(__file__).resolve().parents[1]
    dest=dest.absolute()
    require(dest!=src and not dest.is_relative_to(repo),
            "Apple firmware must stay OUTSIDE the public source repository")
    require(not dest.exists() and not dest.is_symlink(),
            "Destination already exists: refuse overwriting")
    for parent in dest.parents:
        require(not parent.is_symlink(),
                "Destination parent must not be a symlink")
    data=inspect_private_source(src)
    dest.mkdir(mode=0o700,parents=True)
    try:
        written={}
        for family,files in data.items():
            label=family.rsplit("-",1)[-1]
            folder=dest/label
            (folder/"brcm").mkdir(mode=0o700,parents=True)
            (folder/"original-profiles").mkdir(mode=0o700)
            total=0
            for name,source in sorted(files.items()):
                if name in COMPONENTS:
                    target=folder/"brcm"/COMPONENTS[name]
                else:
                    target=folder/"original-profiles"/name
                require(not target.exists(),
                        "Unexpected existing private firmware output")
                shutil.copyfile(source,target,follow_symlinks=False)
                os.chmod(target,0o600)
                # Check hashes without logging/exporting original bytes.
                with source.open("rb") as s, target.open("rb") as t:
                    require(hashlib.file_digest(s,"sha256").digest()==
                            hashlib.file_digest(t,"sha256").digest(),
                            "Original Apple firmware checksum changed on copy")
                total+=1
            written[label]=total
        return written
    except Exception:
        shutil.rmtree(dest)
        raise

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-source",type=Path,required=True)
    parser.add_argument("--private-destination",type=Path,required=True)
    args=parser.parse_args()
    try:
        source=args.private_source.expanduser().resolve(strict=True)
        target=args.private_destination.expanduser().absolute()
        copied=stage(source,target)
    except (OSError,UnsafeFirmwareStaging) as exc:
        print("BCM4350_PRIVATE_STAGING_BLOCKED:",str(exc),file=sys.stderr)
        return 1
    print("BCM4350_PRIVATE_FIRMWARE_STAGED")
    for family,count in sorted(copied.items()):
        print("REVISION",family,"COMPONENT_AND_PROFILE_COUNT",count)
    print("SILICON_REVISION_AND_SYS_CFG_MATCH_PENDING")
    print("NO_FIRMWARE_PUBLISHED_NO_DEVICE_PROBED_NO_WIFI_CLAIM")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
