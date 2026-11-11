#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline S8000 PCIe port-1 guard ↔ authentic N71 ADT consistency gate.

Cross-validates the existing intentionally NONFUNCTIONAL kernel-side PCIe
research guard and its compiled AArch64 object against the independently
parsed original N71 Apple Device Tree. No MMIO, clocks, GPIO, IRQ, DMA,
firmware or device accesses. Success NEVER authorizes hardware probing.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location(
    "s8000_port1_private_adt",HERE/"n71_s8000_adt_window_gate.py")
assert SPEC and SPEC.loader
ADT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADT)

class Port1Unqualified(ValueError):
    pass

def need(ok:bool,reason:str):
    if not ok: raise Port1Unqualified(reason)

def ranges_from_c(source:str,identifier:str)->tuple[tuple[int,int],...]:
    pattern=(r"static\s+const\s+struct\s+apple_s8000_guard_range\s+"
             +re.escape(identifier)+r"\[\]\s*=\s*\{(.*?)\n\};")
    matches=re.findall(pattern,source,re.S)
    need(len(matches)==1,"Missing or duplicate C hardware-range table")
    body=matches[0]
    lines=[]
    for raw in body.splitlines():
        clean=raw.split("/*",1)[0].strip()
        if not clean:continue
        matched=re.fullmatch(
            r"\{\s*0x([0-9a-f]+)ULL\s*,\s*0x([0-9a-f]+)\s*\}\s*,?",
            clean)
        need(matched is not None,"Unexpected C guard range declaration")
        lines.append((int(matched.group(1),16),int(matched.group(2),16)))
    need(lines,"Empty guard resource table")
    return tuple(lines)

def qualify(source:str,private_adt:bytes)->dict:
    need(len(source)<32_000,"Unexpectedly long PCIe port1 research guard")
    msg=ADT.audit_bytes(private_adt)
    need("S8000_ADT_METADATA_GATE_PASS" in msg and
         "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in msg,
         "Authentic N71 ADT lacks validated port1 and IOMMU relationship")
    expected_wlan=(
        ADT.HOST_LAYOUT[3],
        ADT.HOST_LAYOUT[4],
        ADT.DART_LAYOUT[1],
    )
    expected_protected=(
        ADT.HOST_LAYOUT[9],ADT.HOST_LAYOUT[10],
        (ADT.HOST_LAYOUT[1][0],0xC000),
        (ADT.HOST_LAYOUT[5][0],0xC000),
        (ADT.HOST_LAYOUT[7][0],0x8000),
        ADT.HOST_LAYOUT[0],
    )
    wlan=ranges_from_c(source,"wlan_candidate")
    protected=ranges_from_c(source,"protected")
    need(wlan==expected_wlan,
         "Port1 WLAN/DART1 windows differ from original N71 ADT")
    need(protected==expected_protected,
         "Storage/modem/global protected areas differ from original N71 ADT")
    ADT.disjoint([
        (f"wlan{i}",*pair) for i,pair in enumerate(wlan)
    ]+[(f"protected{i}",*pair) for i,pair in enumerate(protected)])
    # Strip block and line comments. Only the *executable C* is checked.
    code=re.sub(r"/\*.*?\*/","",source,flags=re.S)
    code=re.sub(r"//[^\n]*","",code)
    need('apple,s8000-pcie-research-blocked' in code and
         'apple,s8000-pcie-unimplemented' not in code and
         '.compatible = "apple,pcie"' not in code and
         '.compatible = "apcie,s8000"' not in code,
         "Driver would bind to a live PCIe controller without explicit opt-in")
    need("return -EOPNOTSUPP;" in code and
         "return -ENODEV;" in code and "return -ERANGE;" in code,
         "Guard lacks definitive fail-closed probe")
    need("apple_s8000_port1_metadata_isolated()" in code,
         "Guard probe does not check resource isolation")
    for danger in (
        "ioremap", "readl(", "writel(", "ioread", "iowrite",
        "regmap_read", "regmap_write", "request_irq(",
        "clk_prepare", "clk_enable", "reset_control",
        "gpiod_", "dma_map", "dma_alloc", "iommu_",
        "pci_host_probe", "pci_scan", "pci_bus_",
        "regulator_", "phy_power", "pm_runtime",
    ):
        need(danger not in code,
             "Research guard contains real hardware action API")
    return {
        "candidate_windows":len(wlan),
        "protected_windows":len(protected),
        "adt_consistent":True,
        "wlan_port":1,
        "dart_index":1,
        "hardware_probe_enabled":False,
        "runtime_memory_order_verified":False,
        "stream_id_dma_verified":False,
    }

def require_elf64_aarch64_rel(path:Path):
    stat=path.stat()
    need(64<=stat.st_size<2_000_000,"Missing/oversized A9 guard ARM64 object")
    with path.open("rb") as f: head=f.read(64)
    need(head[:6]==b"\x7fELF\x02\x01" and
         struct.unpack_from("<H",head,16)[0]==1 and
         struct.unpack_from("<H",head,18)[0]==183,
         "Guard object not a relocatable AArch64 ELF")

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_n71_adt",type=Path)
    p.add_argument("private_linux_guard_c",type=Path)
    p.add_argument("private_compiled_guard_arm64_object",type=Path)
    x=p.parse_args()
    try:
        need(0<x.private_n71_adt.stat().st_size<=ADT.ADT.MAX_FILE,
             "Invalid original N71 ADT size")
        v=qualify(x.private_linux_guard_c.read_text(),
                  x.private_n71_adt.read_bytes())
        require_elf64_aarch64_rel(x.private_compiled_guard_arm64_object)
    except (OSError,UnicodeError,ValueError,struct.error,
            ADT.RejectedADT,Port1Unqualified) as e:
        print("N71_S8000_PORT1_GUARD_CONSISTENCY_FAIL_CLOSED:",e,file=sys.stderr)
        return 1
    print("N71_S8000_WLAN_PORT1_METADATA_GUARD_ARM64_STATIC_PASS")
    print("CANDIDATE_PORT1_WINDOWS",v["candidate_windows"])
    print("PROTECTED_STORAGE_MODEM_GLOBAL_WINDOWS",v["protected_windows"])
    print("ORIGINAL_ADT_BCM4350_DART1_ASSOCIATION_PASS")
    print("ROOT_PROVIDER_IODEVICE_MEMORY_ORDER_VERIFIED=NO")
    print("DART1_PHYSICAL_SID_DMA_ISOLATION_VERIFIED=NO")
    print("PORT1_PCIE_LINK_DRIVER_OR_RADIO_READY=NO")
    print("NO_DEVICE_ACCESS_NO_MMIO_NO_SAFE_HARDWARE_PROBE_CLAIM")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
