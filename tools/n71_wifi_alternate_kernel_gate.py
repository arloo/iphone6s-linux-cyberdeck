#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed OFFLINE N71 alternate Linux Wi-Fi kernel+module linkage gate.

Does NOT package or boot a RAM payload; input .config, Image/vmlinux and
modules must already have been built in a private directory. No devices,
network, firmware or kernel memory are touched. Passing does not qualify
PCIe S8000 host, DART1 DMA, or actual BCM4350 radio functionality.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
P=importlib.util.spec_from_file_location(
  "n71_wifi_kernel_cfg_gate",HERE/"n71_wifi_kernel_baseline_gate.py")
assert P and P.loader
CFG=importlib.util.module_from_spec(P)
P.loader.exec_module(CFG)

MODULE_PATHS=(
 "net/wireless/cfg80211.ko",
 "drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.ko",
 "drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.ko",
 "drivers/gpio/gpio-apple-pmic.ko",
)

class UnqualifiedAlternativeKernel(ValueError): pass

def need(ok:bool,reason:str)->None:
    if not ok:raise UnqualifiedAlternativeKernel(reason)

def output(argv:list[str],max_size:int=1_000_000)->str:
    try:
        data=subprocess.check_output(
            argv,stderr=subprocess.DEVNULL,timeout=20,
            env={**os.environ,"LC_ALL":"C"})
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise UnqualifiedAlternativeKernel("Could not read offline kernel ELF metadata") from exc
    need(len(data)<max_size,"Unexpectedly large output from ELF metadata inspector")
    return data.decode("ascii",errors="replace")

def file_sha256(p:Path)->bytes:
    with p.open("rb") as inp:
        return hashlib.file_digest(inp,"sha256").digest()

def verify_version_header(text:str)->str:
    match=re.fullmatch(r'#define UTS_RELEASE "([A-Za-z0-9._+-]{1,120})"\s*',text)
    need(match is not None,"Alternative kernel UTS_RELEASE header invalid")
    return match.group(1)

def inspect_module(vermagic:str,release:str,elf_header:str)->None:
    need("Machine:" in elf_header and "AArch64" in elf_header and
         "Type:" in elf_header and "REL" in elf_header,
         "Module is not an AArch64 relocatable ELF")
    need(vermagic.startswith(release+" "),
         "Module vermagic disagrees with actual alternate Linux kernel")
    need(vermagic.strip().endswith("aarch64"),
         "Module vermagic is not target AArch64")

def qualify_files(trusted_image:Path,alt_build:Path,
                  baseline_config:Path)->dict:
    need(alt_build.is_dir() and not alt_build.is_symlink(),
         "Alternative build must be a real separate private directory")
    need(trusted_image.is_file() and not trusted_image.is_symlink(),
         "Trusted known-good kernel image must be real and immutable")
    config=alt_build/".config"
    need(config.is_file() and not config.is_symlink(),
         "Missing isolated A9 Wi-Fi kernel configuration")
    CFG.verify(CFG.parse_kconfig(baseline_config.read_bytes()),
               CFG.parse_kconfig(config.read_bytes()))
    img=alt_build/"arch/arm64/boot/Image"
    vmlinux=alt_build/"vmlinux"
    symvers=alt_build/"Module.symvers"
    for p in (img,vmlinux,symvers):
        need(p.is_file() and not p.is_symlink(),
             "Complete alternate kernel images/symbols missing or symlinked")
    need(5_000_000<img.stat().st_size<80_000_000,
         "Incomplete or oversized ARM64 Image")
    need(10_000_000<vmlinux.stat().st_size<900_000_000,
         "Incomplete or oversized alternative vmlinux")
    need(100_000<symvers.stat().st_size<5_000_000,
         "Incomplete alternate core/module symbol map")
    need(5_000_000<trusted_image.stat().st_size<80_000_000,
         "Unexpected original known-good Linux Image")
    need(file_sha256(trusted_image)!=file_sha256(img),
         "Alternative Wi-Fi kernel is identical to non-Wi-Fi known-good Image")
    hdr=output(["aarch64-linux-gnu-readelf","-h",str(vmlinux)])
    need("Machine:" in hdr and "AArch64" in hdr and "Type:" in hdr,
         "Alternate kernel vmlinux is not ELF64 AArch64")
    release=verify_version_header(
        (alt_build/"include/generated/utsrelease.h").read_text())
    symbols=output(["aarch64-linux-gnu-nm","--defined-only",str(vmlinux)],
                   max_size=50_000_000)
    need(re.search(r"\b(?:T|t)\s+verify_pkcs7_signature\b",symbols) is not None,
         "Signed regulatory PKCS7 verification symbol missing in new linked core")
    for rel in MODULE_PATHS:
        path=alt_build/rel
        need(path.is_file() and not path.is_symlink() and
             50_000<path.stat().st_size<100_000_000,
             "Missing or unsafe kernel module: "+rel)
        vermagic=output(["modinfo","-F","vermagic",str(path)]).strip()
        elf_header=output(["aarch64-linux-gnu-readelf","-h",str(path)])
        inspect_module(vermagic,release,elf_header)
    return {"release":release,"modules":len(MODULE_PATHS),
            "kernel_image_bytes":img.stat().st_size,
            "full_image_built":True,"booted":False,"wifi_functional":False}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trusted_known_good_linux_image",type=Path)
    ap.add_argument("trusted_known_good_kernel_config",type=Path)
    ap.add_argument("isolated_alternate_arm64_build_directory",type=Path)
    x=ap.parse_args()
    try:
        result=qualify_files(x.trusted_known_good_linux_image,
                             x.isolated_alternate_arm64_build_directory,
                             x.trusted_known_good_kernel_config)
    except (OSError,UnicodeError,UnqualifiedAlternativeKernel,
            CFG.UnqualifiedConfig) as exc:
        print("N71_WIFI_ALTERNATE_IMAGE_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_WIFI_ALTERNATE_KERNEL_IMAGE_AND_FOUR_MODULES_STATIC_PASS")
    print("ARM64_KERNEL_RELEASE",result["release"])
    print("ALTERNATIVE_ARM64_MODULE_COUNT",result["modules"])
    print("NEW_LINKED_KERNEL_PKCS7_EXPORT_PRESENT=YES")
    print("NATIVE_TOUCH_DISPLAY_USB_BASELINE_CONFIG_PRESERVED=YES")
    print("ALTERNATIVE_KERNEL_BOOTED=NO")
    print("PCIe_S8000_DART1_DMA_WIFI_HARDWARE_VERIFIED=NO")
    print("NO_BOOTABLE_RAM_BUNDLE_ASSEMBLED_NO_DEVICE_ACCESS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
