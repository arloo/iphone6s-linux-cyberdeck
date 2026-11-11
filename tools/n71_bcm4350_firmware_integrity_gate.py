#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only BCM4350 N71 private firmware integrity / revision-isolation gate.

Inputs are operator-held Apple original C2+C5 files and a separate private
Linux-staging tree. No firmware is dumped, written, selected, uploaded or
loaded. An exact byte match does NOT prove brcmfmac firmware compatibility.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location(
    "n71_bcm4350_private_stager",ROOT/"n71_stage_bcm4350_firmware.py")
assert SPEC and SPEC.loader
STAGE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)

class UnverifiedFirmware(ValueError): pass

def need(ok:bool,reason:str):
    if not ok: raise UnverifiedFirmware(reason)

def regular(path:Path,max_bytes:int,require_private:bool)->None:
    s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and 0<s.st_size<=max_bytes,
         "Unexpected private firmware file type or size")
    if require_private:
        need((stat.S_IMODE(s.st_mode)&0o077)==0,
             "Staged firmware permissions are not private")

def sha(path:Path)->bytes:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").digest()

def inspect(source:Path,output:Path)->dict[str,object]:
    need(source.is_absolute() and output.is_absolute(),
         "Paths must be absolute")
    need(source.is_dir() and output.is_dir() and
         not source.is_symlink() and not output.is_symlink(),
         "Expected separate, real private source and staging directories")
    need(source.resolve()!=output.resolve() and
         not output.resolve().is_relative_to(ROOT.parent),
         "Never audit firmware inside the public Git repository")
    try:
        origins=STAGE.inspect_private_source(source)
    except (STAGE.UnsafeFirmwareStaging,OSError) as exc:
        raise UnverifiedFirmware("Private source family validation failed") from exc
    need(set(p.name for p in output.iterdir())=={"C2","C5"},
         "Output must contain two and only two isolated revisions")
    seen={}
    totals=0
    for family in STAGE.FAMILIES:
        label=family.rsplit("-",1)[-1]
        folder=output/label
        need(folder.is_dir() and not folder.is_symlink(),
             "Staged revision directory cannot be a symlink")
        need(set(p.name for p in folder.iterdir())=={
             "brcm","original-profiles"},"Unexpected staged revision content")
        binaries=folder/"brcm"
        profiles=folder/"original-profiles"
        for p in (binaries,profiles):
            need(p.is_dir() and not p.is_symlink(),
                 "Unsafe private destination subdirectory")
        need(set(p.name for p in binaries.iterdir())==
             set(STAGE.COMPONENTS.values()),
             "Incomplete or unexpected staged Broadcom component")
        candidates={name for name in origins[family]
                    if STAGE.PROFILE_NAME.fullmatch(name)}
        need(set(p.name for p in profiles.iterdir())==candidates,
             "Wrong/mixed staged Apple module profiles")
        for name,original in origins[family].items():
            if name in STAGE.COMPONENTS:
                staged=binaries/STAGE.COMPONENTS[name]
                maxbytes=STAGE.MAX_BYTES[name]
            else:
                staged=profiles/name
                maxbytes=32_768
            regular(staged,maxbytes,True)
            need(sha(original)==sha(staged),
                 "Original source/staging content mismatch")
            totals+=1
        seen[label]=sha(binaries/STAGE.COMPONENTS["albarossa.trx"])
    need(seen["C2"]!=seen["C5"],
         "Original C2 and C5 firmware improperly merged or identical")
    return {
      "firmware_families_checked":2,
      "total_files_checked":totals,
      "hash_matches_verified":True,
      "revisions_kept_separate":True,
      "chip_revision_detected":False,
      "board_calibration_verified":False,
      "brcmfmac_binary_compatibility_proven":False,
      "safe_to_auto_install":False,
    }

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original-private-source",required=True,type=Path)
    ap.add_argument("--private-linux-staging",required=True,type=Path)
    x=ap.parse_args()
    try:
        result=inspect(x.original_private_source,x.private_linux_staging)
    except (OSError,UnverifiedFirmware) as exc:
        print("N71_BCM4350_PRIVATE_FIRMWARE_GATE_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_BCM4350_TWO_REVISION_PRIVATE_SHA256_INTEGRITY_PASS")
    print("PRIVATE_FAMILIES",result["firmware_families_checked"])
    print("PRIVATE_COMPONENTS_AND_PROFILES",result["total_files_checked"])
    print("C2_C5_ISOLATION=VERIFIED")
    print("ACTUAL_SILICON_REVISION_AND_BOARD_NVRAM=UNKNOWN")
    print("LINUX_BRCMFMAC_FIRMWARE_FORMAT_RUNTIME_COMPATIBILITY=UNVERIFIED")
    print("NO_AUTO_SELECTION_NO_PRIVATE_OUTPUT_NO_HARDWARE_ACCESS")
    return 0

if __name__=="__main__":raise SystemExit(main())
