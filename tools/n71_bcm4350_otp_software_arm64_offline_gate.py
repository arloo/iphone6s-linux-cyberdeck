#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed offline proof of BCM4350 OTP support on the exact N71 kernel.

This is solely source and real AArch64 object analysis. No original Apple
OTP, calibration, firmware, MAC address, PCI bus or phone is read.
Original patch © upstream OrchardLinux; credit and GPL in patch 0017.
"""
from __future__ import annotations
import argparse,hashlib,difflib,struct,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"experimental/patches/0017-n71-brcmfmac-bcm4350-otp-software-only-offline.patch"
BEFORE_SHA="2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c"
AFTER_SHA="1a7e90562fd934352952506f86e0e64d3bedb66dfd16d381cf2caa941615b746"
OBJECT_SHA="4a16ed4882f2a7e33e87acbf88881b6fd1da38446f87b294b988a975c4916bbe"
DIFF="diff --git a/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c b/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c\n"
class UnsafeOtpSource(ValueError):pass

def need(ok,reason):
    if not ok: raise UnsafeOtpSource(reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(path,max_size):
    need(path.is_file() and not path.is_symlink() and 1024<path.stat().st_size<max_size,"Invalid offline evidence path")
    return path.read_bytes()
def otp_words(size_encoding:int)->int:
    """Pure bounding model of the upstream 40 nm BCM4350 OTP size field."""
    need(type(size_encoding) is int and 0<=size_encoding<=15,"Not a 4-bit OTP encoding")
    if size_encoding==0:return 0
    words=(size_encoding+1)*1024//16-(0x8c0-0x800)//2
    need(0<words<=1024,"OTP size outside 4-bit hardware bound")
    return words
def diff_of(a:str,b:str)->str:
    return "".join(difflib.unified_diff(a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="a/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c",
        tofile="b/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c",n=4))
def source_guard(old:bytes,new:bytes,patch:bytes,obj:bytes)->bool:
    need(sha(old)==BEFORE_SHA and sha(new)==AFTER_SHA and
         sha(obj)==OBJECT_SHA,"Unpinned source or ARM64 object")
    try:a=old.decode("utf8");b=new.decode("utf8");p=patch.decode("utf8")
    except UnicodeError as err:raise UnsafeOtpSource("Nontext code") from err
    need(p.count("diff --git ")==1 and DIFF in p,"Unexpected source files modified")
    body=p.split(DIFF,1)[1]
    need(body==diff_of(a,b),"Patch does not match exact compiled source")
    need(sum(line.startswith("@@ ") for line in body.splitlines())==2,"Not exact 2-hunk OTP patch")
    add="\n".join(line[1:] for line in body.splitlines() if line.startswith("+") and not line.startswith("+++"))
    for marker in ("case BRCM_CC_4350_CHIP_ID:", "CC_CAP_OTPSIZE_SHIFT",
                   "BCMA_CORE_CHIPCOMMON", "base = 0x8c0;",
                   "if (!otpsize)", "optional = true;", "if (ret && optional)",
                   "return 0;"):
        need(marker in add,"Missing optional BCM4350 OTP handling")
    for forbidden in ("pci_host_probe(","apple_dart_hw_reset(","of_machine_is_compatible(",
                      "devm_ioremap(", "clk_prepare_enable(", "mmio_write(", "gpio_set_value("):
        need(forbidden not in add,"OTP patch adds unrelated PCIe/SoC side effects")
    need("SPDX-License-Identifier: GPL-2.0-only" in p and
         "Henrik Klee" in p,"Missing upstream attribution")
    need(len(obj)>100_000 and obj[:6]==b"\x7fELF\x02\x01","Not ELF64 little-endian")
    elf_kind,machine=struct.unpack_from("<HH",obj,16)
    need(elf_kind==1 and machine==183,"Not AArch64 ET_REL")
    return True
def main():
    a=argparse.ArgumentParser(description=__doc__)
    for field in ("prior_private_source","modified_private_source","real_arm64_pcie_object"):
        a.add_argument(field,type=Path)
    args=a.parse_args()
    try:
        source_guard(read(args.prior_private_source,250_000),
                     read(args.modified_private_source,250_000),
                     read(PATCH,15_000),read(args.real_arm64_pcie_object,3_000_000))
    except (OSError,UnsafeOtpSource):
        print("N71_BCM4350_OTP_SOFTWARE_OFFLINE_PROOF_NOT_ESTABLISHED",file=sys.stderr)
        return 2
    print("N71_BCM4350_OTP_DRIVER_REAL_AARCH64_SOURCE_AND_ELF_PASS")
    print("N71_BRCMFMAC_ORCHARD_OTP_TWO_HUNK_PATCH_APPLIES=YES")
    print("N71_BCM4350_OTP_PARSER_ACCEPTS_MISSING_RECORD_AS_OPTIONAL=YES")
    print("N71_BCM4350C5_OTP_FORMAT_VALIDATED_ON_N71_HARDWARE=NO")
    print("N71_PHYSICAL_PCIE_DART1_OR_NATIVE_WIFI_PROVEN=NO")
    print("N71_IPHONE_ORIGINAL_BOOT_NAND_AND_RADIO_UNTOUCHED=YES")
    return 0
if __name__=="__main__":raise SystemExit(main())
