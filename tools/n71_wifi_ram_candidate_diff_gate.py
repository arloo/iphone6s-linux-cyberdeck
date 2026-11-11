#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify candidate N71 RAM payload differs ONLY by a new ARM64 Image.gz.

Read-only validator for operator-supplied private original/reference images,
m1n1, two board DTBs and private initramfs. Does NOT authenticate original
Apple firmware provenance, inspect device IDs, boot or touch iPhone hardware.
Passing does not establish kernel bootability or functional Wi-Fi.
"""
from __future__ import annotations
import argparse
import gzip
from pathlib import Path
import sys

MAX_PAYLOAD=80_000_000
MAX_COMPONENT=60_000_000
BOOTARGS_PREFIX=b"chosen.bootargs="

class UnsafeRAMCandidate(ValueError):
    pass

def need(ok:bool,msg:str)->None:
    if not ok:raise UnsafeRAMCandidate(msg)

def compare_components(ref:bytes,candidate:bytes,m1n1:bytes,
                       dtb_a9:bytes,dtb_a9_tsmc:bytes,
                       old_image_gz:bytes,new_image_gz:bytes,
                       private_ramdisk:bytes)->dict:
    need(0<len(ref)<MAX_PAYLOAD and 0<len(candidate)<MAX_PAYLOAD,
         "Unexpected N71 private RAM payload size")
    for b in (m1n1,dtb_a9,dtb_a9_tsmc,old_image_gz,
              new_image_gz,private_ramdisk):
        need(0<len(b)<MAX_COMPONENT,"Missing or excessive private boot component")
    pos=len(m1n1)
    need(ref[:pos]==m1n1 and
         ref[pos:pos+len(BOOTARGS_PREFIX)]==BOOTARGS_PREFIX,
         "Known-good N71 m1n1/bootargs prefix is not verified")
    newline=ref.find(b"\n",pos)
    need(pos+len(BOOTARGS_PREFIX)<newline<=pos+1024,
         "Known-good RAM payload has malformed boot arguments")
    args=ref[pos+len(BOOTARGS_PREFIX):newline]
    need(b"\0" not in args and b"\r" not in args,
         "Unexpected original bootarg control characters")
    header=ref[pos:newline+1]
    prefix=m1n1+header+dtb_a9+dtb_a9_tsmc
    need(ref==prefix+old_image_gz+private_ramdisk,
         "Reference RAM payload does not match operator supplied original inputs")
    need(candidate==prefix+new_image_gz+private_ramdisk,
         "Alternative RAM payload changed something other than the kernel")
    need(new_image_gz!=old_image_gz,
         "Alternative Linux kernel compressed bytes equal known-good kernel")
    try:
        old=gzip.decompress(old_image_gz)
        new=gzip.decompress(new_image_gz)
        gzip.decompress(private_ramdisk)
    except (OSError,EOFError) as exc:
        raise UnsafeRAMCandidate("Original/new kernel or initramfs gzip invalid") from exc
    need(len(new)>1 and new!=old,
         "Alternative Linux kernel uncompressed bytes equal known-good kernel")
    return {
        "same_m1n1":True,
        "same_bootargs":True,
        "same_a9_and_tsmc_dtbs":True,
        "same_private_ramdisk":True,
        "only_compressed_kernel_replaced":True,
        "candidate_kernel_booted":False,
        "native_wifi_usable":False,
    }

def read_private(path:Path)->bytes:
    stat=path.stat()
    need(path.is_file() and not path.is_symlink() and
         0<stat.st_size<MAX_PAYLOAD,
         "Private input missing, symlinked or oversized")
    return path.read_bytes()

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("known_good_ram_payload",type=Path)
    p.add_argument("candidate_ram_payload",type=Path)
    p.add_argument("private_original_m1n1",type=Path)
    p.add_argument("private_n71_s8000_dtb",type=Path)
    p.add_argument("original_untested_s8003_dtb",type=Path)
    p.add_argument("known_good_kernel_image_gz",type=Path)
    p.add_argument("alternate_kernel_image_gz",type=Path)
    p.add_argument("known_good_private_initramfs_gz",type=Path)
    x=p.parse_args()
    try:
        result=compare_components(*[
            read_private(getattr(x,name)) for name in (
              "known_good_ram_payload","candidate_ram_payload",
              "private_original_m1n1","private_n71_s8000_dtb",
              "original_untested_s8003_dtb","known_good_kernel_image_gz",
              "alternate_kernel_image_gz","known_good_private_initramfs_gz"
            )
        ])
    except (OSError,UnsafeRAMCandidate) as exc:
        print("N71_WIFI_RAM_CANDIDATE_DIFFERENCE_FAIL_CLOSED:",
              str(exc),file=sys.stderr)
        return 1
    print("N71_WIFI_PRIVATE_RAM_BOOT_ONLY_KERNEL_COMPRESSED_BYTES_CHANGED_PASS")
    print("M1N1_BOOTARGS_DTBS_PRIVATE_RAMDISK_UNCHANGED=YES")
    print("KNOWN_GOOD_Z2_TOUCH_AND_USB_FALLBACK_BYTES_PRESERVED=YES")
    print("ALTERNATE_KERNEL_BOOTED_OR_WLAN_FUNCTIONAL=NO")
    print("NO_DEVICE_ACCESS_NO_BOOT_NO_NAND_CHANGE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
