#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed ABI/source audit for owner's *private* N71 S8000 port1 guard.

This does NOT load the kernel module, reboot, probe hardware, read firmware,
write MMIO, or discover a BCM4350 PCIe SID. Only the owner-provided local,
already-build artifact paths are processed. No raw proprietary content is
printed. Forbids driver additions that gain direct register/DMA capabilities.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

PHYSICAL_KERNEL_SHA256="fbf9ec6754245d48922e6da8b82c90e6c985ea088ed8ab896397af8e3f9f7845"
EXPECTED_VERMAGIC="7.3.0-rc1-g68aadac820d0-dirty SMP preempt aarch64"
EXPECTED_NAME="pcie_apple_s8000_guard"
EXPECTED_DESCRIPTION="N71 S8000 PCIe WLAN port1 metadata-only preflight, ALWAYS BLOCKED"
ALLOWED_IMPORTS=frozenset({
    "_dev_info","of_machine_compatible_match","of_property_read_bool",
    "of_property_read_variable_u32_array","__platform_driver_register",
    "platform_driver_unregister","platform_get_resource",
    "platform_get_resource_byname","__stack_chk_fail"
})
FORBIDDEN_C_APIS=frozenset({
    "readl","readq","writel","writeq","ioread8","iowrite8","ioremap",
    "devm_ioremap","devm_ioremap_resource","devm_platform_ioremap_resource",
    "of_iomap","clk_prepare_enable","clk_enable","clk_set_rate",
    "reset_control_assert","reset_control_deassert","gpiod_set_value",
    "regulator_enable","dma_map_single","dma_alloc_coherent",
    "iommu_map","pci_host_probe","pci_scan_root_bus",
    "request_irq","devm_request_irq","of_platform_populate",
    "of_address_to_resource","memcpy_toio","memset_io",
})
class GuardABIUnproven(ValueError):
    pass

def require(ok, why):
    if not ok:raise GuardABIUnproven(why)

def sha256(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def source_guard_gate(src:str)->None:
    src=re.sub(r"/\*.*?\*/|//[^\n]*","",src,flags=re.S)
    for danger in FORBIDDEN_C_APIS:
        require(not re.search(r"\b"+re.escape(danger)+r"\s*\(",src),
                "Dangerous register, DMA or hardware function in guard")
    for required in (
        "static int apple_s8000_guard_probe",
        "return -EOPNOTSUPP;",
        "apple,s8000-pcie-research-blocked",
        "research,hardware-activation-blocked",
        "research,pcie-port-index",
        "research,dart1-mapper-index",
        "platform_get_resource_byname",
        "apple_s8000_regions_overlap",
        "of_machine_is_compatible",
    ):
        require(required in src,"Mandatory fail-closed guard code absent")
    require("0x602000000" in src and "0x602004000" in src and
            "0x602008000" in src,"Original N71 port1/DART1 windows absent")

def parse_imports_nm(output:str)->set[str]:
    return set(re.findall(r"(?m)^\s*U\s+([A-Za-z_][A-Za-z_0-9]*)\s*$",output))

def parse_kernel_export_symbols(output:str)->set[str]:
    return set(re.findall(r"(?m)\b__ksymtab_([A-Za-z_][A-Za-z_0-9]*)$",output))

def verify_imports(imports:set[str],exports:set[str]):
    require(imports==ALLOWED_IMPORTS,"Unexpected kernel symbol or absent required import")
    require(imports<=exports,"An imported symbol is not exported by physically matching kernel")

def first_embedded_kernel(boot:bytes)->bytes:
    # Two contiguous FDTs precede the raw gzip Linux Image.
    fd=boot.find(b"\xd0\x0d\xfe\xed",1_150_000)
    require(fd>0 and fd+8<len(boot),"Expected N71 FDT not found")
    for _ in range(2):
        require(boot[fd:fd+4]==b"\xd0\x0d\xfe\xed",
                "Malformed pair of N71/S8003 Device Trees")
        n=struct.unpack_from(">I",boot,fd+4)[0]
        require(20000<n<50000,"Unexpected original DTB length")
        fd+=n
    require(boot[fd:fd+3]==b"\x1f\x8b\x08",
            "Original physically booted kernel gzip not present")
    inflator=zlib.decompressobj(16+zlib.MAX_WBITS)
    result=inflator.decompress(boot[fd:])+inflator.flush()
    require(inflator.eof and result,"Kernel decompression incomplete")
    return result

def command(*argv):
    p=subprocess.run(argv,check=True,capture_output=True,text=True,timeout=40,
                     env={**os.environ,"LC_ALL":"C"})
    return p.stdout

def verify(inputs):
    for path in inputs:
        require(path.is_file() and not path.is_symlink(),
                "A private binary/source path is missing or symlinked")
    module,vmlinux,source,boot,image=inputs
    require(sha256(image.read_bytes())==PHYSICAL_KERNEL_SHA256,
            "Kernel disk build differs from actual physically booted N71 Image")
    require(first_embedded_kernel(boot.read_bytes())==image.read_bytes(),
            "Research candidate does not contain byte-identical physical kernel")
    modinfo=command("modinfo",module)
    for label,expected in (
        ("vermagic",EXPECTED_VERMAGIC),
        ("name",EXPECTED_NAME),
        ("description",EXPECTED_DESCRIPTION),
        ("license","GPL")
    ):
        exp=re.compile(r"(?m)^"+re.escape(label)+r":\s+"+re.escape(expected)+r"\s*$")
        require(bool(exp.search(modinfo)),"Kernel guard module identity mismatch")
    elf=command("readelf","-h",module)
    require("AArch64" in elf and "ELF64" in elf and "REL (Relocatable file)" in elf,
            "Kernel module is not relocatable 64-bit ARM")
    imports=parse_imports_nm(command("aarch64-linux-gnu-nm","-u",module))
    exports=parse_kernel_export_symbols(
        command("aarch64-linux-gnu-nm","--defined-only",vmlinux))
    verify_imports(imports,exports)
    source_guard_gate(source.read_text())
    return len(imports)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("module","vmlinux","source","boot","image"):
        ap.add_argument("--"+key,required=True,type=Path)
    arg=ap.parse_args()
    try:
        n=verify([arg.module,arg.vmlinux,arg.source,arg.boot,arg.image])
    except (GuardABIUnproven,OSError,subprocess.SubprocessError):
        print("N71_PORT1_GUARD_ABI_OR_SOURCE_SAFETY_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_PORT1_EXACT_PHYSICAL_KERNEL_OFFLINE_MODULE_ABI_GATE_PASS")
    print("N71_IDENTICAL_BOOT_IMAGE_AND_VMLINUX_BUILD=YES")
    print("N71_GUARD_MODULE_VERMAGIC_AARCH64_PASS=YES")
    print("N71_GUARD_EXACT_KERNEL_SYMBOL_EXPORTS_VERIFIED",n)
    print("N71_GUARD_SOURCE_DIRECT_MMIO_DMA_RESET_CLOCK_APIS_ABSENT=YES")
    print("N71_GUARD_PROBE_ALWAYS_RETURNS_EOPNOTSUPP=YES")
    print("N71_GUARD_RUN_ON_REAL_IPHONE_YET=NO")
    print("N71_PCIE_DART1_REAL_DMA_REQUESTER_SID_STILL_UNPROVEN=YES")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
