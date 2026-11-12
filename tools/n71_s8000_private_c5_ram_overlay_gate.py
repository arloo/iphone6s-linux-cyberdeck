#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71/S8000 strictly OFFLINE, privacy-safe C5 Wi-Fi RAM-image overlay gate.

Compare previous UNBOOTED software-only image and new UNBOOTED image with
private original-stock-Apple C5 generic firmware overlay; no device contact.
Verifies original m1n1, original two DTBs, compressed ARM64 kernel and 23 old
rootfs cpio entries are identical; exactly 17 original firmware files were
added to /lib/firmware/brcm, without any device OTP selection.
Does NOT assert PCIe link, native WLAN or any on-device boot has occurred.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import stat
import struct
import sys
import zlib

OLD_SHA="73a5beeba0793305c0fdace4f2fdf6fd844595a6030e18b7620b92a9dce144d7"
NEW_SHA="5740307928ede4c731b8a69ee6a83d865c6bc18441b4abc7cd090e7d9565f25f"
KERNEL_SHA="563e1157ca2dcca91acc6eeef266062795b1db6078c8c109a14a0ad4068ff95d"
BR_PREFIX="brcmfmac4350c2-pcie.apple,albarossa"
ORIGINAL_FILES=23
EXTRA_FILES=17

class UnqualifiedOverlay(ValueError):pass

def need(ok,why):
    if not ok:raise UnqualifiedOverlay(why)

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def uncompress_one(data:bytes):
    decompressor=zlib.decompressobj(16+zlib.MAX_WBITS)
    uncompressed=decompressor.decompress(data)+decompressor.flush()
    need(decompressor.eof and not decompressor.unconsumed_tail,
         "Invalid gzip stream")
    return uncompressed,len(data)-len(decompressor.unused_data)

def decompose(image:bytes):
    start=image.find(b"\xd0\x0d\xfe\xed",1_150_000,1_350_000)
    need(start>1_150_000,"Original N71 Apple Device Tree missing")
    at=start
    for _ in range(2):
        need(image[at:at+4]==b"\xd0\x0d\xfe\xed","Missing original Device Tree")
        n=struct.unpack_from(">I",image,at+4)[0]
        need(20_000<n<50_000,"Unknown original Device Tree size")
        at+=n
    original_linux,klen=uncompress_one(image[at:])
    need(len(original_linux)>1_000_000 and
         original_linux[0x38:0x3c]==b"ARM\x64" and
         sha(original_linux)==KERNEL_SHA,
         "Not the previously compiled full ARM64 BRCMFMAC image")
    rootfs,consumed=uncompress_one(image[at+klen:])
    need(consumed==len(image)-(at+klen) and rootfs[:6]==b"070701",
         "Non-final or invalid RAM root filesystem")
    return image[:at],image[at:at+klen],rootfs

def archive(raw:bytes):
    pos=0;members={};trail=None
    while pos<len(raw):
        need(pos+110<=len(raw) and raw[pos:pos+6] in (b"070701",b"070702"),
             "Malformed newc header")
        h=raw[pos:pos+110]
        try:f=[int(h[6+i*8:14+i*8],16) for i in range(13)]
        except ValueError:raise UnqualifiedOverlay("Bad newc hex field")
        mode,size,namesize=f[1],f[6],f[11]
        need(1<namesize<4096 and 0<=size<50_000_000,
             "Invalid CPIO member length")
        n=raw[pos+110:pos+110+namesize]
        need(len(n)==namesize and n[-1:]==b"\0","Unterminated CPIO filename")
        name=n[:-1].decode("utf8")
        need(not name.startswith("/") and ".." not in Path(name).parts,
             "Unsafe CPIO absolute/path traversal")
        payload=(pos+110+namesize+3)&~3
        end=(payload+size+3)&~3
        need(end<=len(raw),"CPIO entry out of bounds")
        if name=="TRAILER!!!":
            need(size==0 and all(b==0 for b in raw[end:]),
                 "Unexpected trailing CPIO payload")
            trail=pos
            break
        need(name not in members,"Duplicate CPIO path")
        members[name]=(mode,raw[payload:payload+size])
        pos=end
    need(trail is not None,"Missing CPIO trailer")
    return members,trail

def validate(previous:bytes,candidate:bytes,firmware:dict[str,bytes]):
    need(sha(previous)==OLD_SHA and sha(candidate)==NEW_SHA,
         "Unreviewed private RAM boot generation")
    oldpre,oldkernel,oldroot=decompose(previous)
    newpre,newkernel,newroot=decompose(candidate)
    need(oldpre==newpre and oldkernel==newkernel,
         "Known-good m1n1/DTBs or newly built ARM64 kernel mutated")
    old,oldtrailer=archive(oldroot)
    new,newtrailer=archive(newroot)
    need(len(old)==ORIGINAL_FILES and
         len(new)==ORIGINAL_FILES+1+EXTRA_FILES,
         "Unexpected old/new RAM filesystem archive inventory")
    need(oldroot[:oldtrailer]==newroot[:oldtrailer],
         "Original touch, USB or research guard CPIO records changed")
    need(newroot[newtrailer:]==oldroot[oldtrailer:],
         "Original CPIO trailer or padding changed")
    need(all(new.get(k)==v for k,v in old.items()),
         "Known-good RAM filesystem member content changed")
    dirname="lib/firmware/brcm"
    need(dirname in new and stat.S_ISDIR(new[dirname][0]),
         "Missing private Linux Wi-Fi firmware directory")
    need(len(firmware)==EXTRA_FILES,"Incorrect original Apple C5 package count")
    expected=set(old)|{dirname}
    for name,contents in firmware.items():
        need(name.startswith(BR_PREFIX) and
             name in (
               BR_PREFIX+".bin",BR_PREFIX+".clm_blob",
               BR_PREFIX+".txcap_blob",
             ) or name.startswith(BR_PREFIX+"-BLMA-") and name.endswith(".txt"),
             "Unexpected private N71 Apple C5 firmware filename")
        full=dirname+"/"+name
        expected.add(full)
        need(full in new and stat.S_ISREG(new[full][0]) and
             new[full][1]==contents,
             "Original C5 firmware bytes not preserved in RAM cpio")
    need(set(new)==expected,"Unapproved CPIO files injected")
    need(sum(k.endswith(".txt") for k in firmware)==14,
         "All genuine N71 C5 NVRAM variants not included")
    return True

def safe_bytes(p:Path,limit:int):
    need(p.is_file() and not p.is_symlink() and 100<p.stat().st_size<limit,
         "Owner-private binary unavailable")
    return p.read_bytes()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prior_private_software_only_ram_image",type=Path)
    parser.add_argument("new_private_c5_overlay_ram_image",type=Path)
    parser.add_argument("private_genuine_c5_brcm_firmware_directory",type=Path)
    a=parser.parse_args()
    try:
        fw=a.private_genuine_c5_brcm_firmware_directory
        need(fw.is_dir() and not fw.is_symlink(),
             "Owner-private genuine C5 firmware missing")
        entries={x.name:safe_bytes(x,2_000_000) for x in fw.iterdir()}
        validate(safe_bytes(a.prior_private_software_only_ram_image,20_000_000),
                 safe_bytes(a.new_private_c5_overlay_ram_image,20_000_000),
                 entries)
    except (UnqualifiedOverlay,UnicodeError,OSError):
        print("N71_S8000_PRIVATE_C5_RAM_BOOT_OVERLAY_NOT_VERIFIED",file=sys.stderr)
        return 2
    print("N71_S8000_PRIVATE_C5_RAM_IMAGE_OVERLAY_OFFLINE_PASS")
    print("N71_M1N1_BOTH_DEVICE_TREES_AND_NEW_BRCM_PCIE_ARM64_KERNEL_IDENTICAL=YES")
    print("N71_ALL_23_ORIGINAL_TOUCH_USB_GUARD_CPIO_MEMBERS_AND_METADATA_IDENTICAL=YES")
    print("N71_3_ORIGINAL_APPLE_C5_FIRMWARE_COMPONENTS_INCLUDED_IN_RAM=YES")
    print("N71_ALL_14_GENUINE_STOCK_APPLE_C5_NVRAM_PROFILES_INCLUDED_IN_RAM=YES")
    print("N71_REAL_DEVICE_OTP_PROFILE_SELECTED=NO")
    print("N71_NATIVE_PCIE_DART_DMA_AND_BRCM4350_WIFI_ENABLED=NO")
    print("N71_NEW_PRIVATE_WLAN_FIRMWARE_IMAGE_HAS_NOT_BEEN_BOOTED=YES")
    print("N71_PRIVATE_BINARIES_CALIBRATION_AND_USER_IDENTIFIERS_EXPORTED=NO")
    return 0

if __name__=="__main__":raise SystemExit(main())
