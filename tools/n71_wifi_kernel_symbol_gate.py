#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only N71 ARM64 brcmfmac module-to-kernel symbol coverage gate.

Classifies undefined references of FOUR offline AArch64 composite objects
against an operator-supplied known-good ARM64 vmlinux Module.symvers and
the other newly built modules' EXPORT_SYMBOL records. Does not link,
load, patch or export kernel binaries. Matching exports is NOT ABI proof.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys

COMPONENTS=("cfg80211","brcmutil","brcmfmac","gpio_apple_pmic")
EXPECTED_SINGLE_BLOCKER=("cfg80211","verify_pkcs7_signature")
MAX_OBJ=40_000_000
MAX_SYMVERS=4_000_000
EXPORT_PREFIX="__export_symbol_"

class IncompatibleSymbols(ValueError):pass

def need(ok:bool,reason:str):
    if not ok:raise IncompatibleSymbols(reason)

def parse_kernel_exports(data:bytes)->set[str]:
    need(0<len(data)<MAX_SYMVERS,"Invalid original kernel symbol map size")
    try: lines=data.decode("ascii").splitlines()
    except UnicodeError as exc:raise IncompatibleSymbols("Invalid symbol export map") from exc
    names=set()
    for line in lines:
        fields=line.split("\t")
        need(len(fields)>=4,"Unexpected original Module.symvers format")
        if fields[2]=="vmlinux":
            name=fields[1]
            need(re.fullmatch(r"[A-Za-z0-9_]+",name) is not None,
                 "Invalid exported kernel symbol")
            names.add(name)
    need(len(names)>100,"Kernel symbol map lacks original vmlinux exports")
    return names

def aarch64_relocatable_file(path:Path)->None:
    s=path.stat()
    need(0<s.st_size<=MAX_OBJ,
         "ARM64 object is empty/oversized")
    with path.open("rb") as f:hdr=f.read(64)
    need(len(hdr)>=20 and hdr[:4]==b"\x7fELF" and hdr[4]==2
         and hdr[5]==1 and struct.unpack_from("<H",hdr,16)[0]==1
         and struct.unpack_from("<H",hdr,18)[0]==183,
         "Expected ELF64 LE AArch64 relocatable object")

def parse_nm(lines:str)->tuple[set[str],set[str]]:
    imported=set()
    exported=set()
    for line in lines.splitlines():
        fields=line.split()
        if len(fields)<2:continue
        symbol=fields[-1]
        if fields[-2]=="U":
            imported.add(symbol)
        if symbol.startswith(EXPORT_PREFIX) and len(symbol)>len(EXPORT_PREFIX):
            exported.add(symbol[len(EXPORT_PREFIX):])
    need(len(imported)>0,"No undefined symbols in aggregate kernel object")
    return imported,exported

def calculate(kernel:set[str],modules:dict[str,tuple[set[str],set[str]]])->dict:
    need(set(modules)==set(COMPONENTS),
         "Incomplete offline Wi-Fi module analysis")
    own_export=set().union(*(pair[1] for pair in modules.values()))
    missing={}
    resolved={}
    for component,(imports,_own) in modules.items():
        need(len(imports)>0,"Missing imports from module")
        unknown=imports-kernel-own_export-{"__this_module"}
        missing[component]=sorted(unknown)
        resolved[component]=len(imports)-len(unknown)-int("__this_module" in imports)
    return {"missing":missing,"resolved":resolved,
            "core_export_count":len(kernel),
            "new_module_export_count":len(own_export)}

def inspect(symvers:Path,objects:dict[str,Path])->dict:
    kernel=parse_kernel_exports(symvers.read_bytes())
    inputs={}
    for name,path in objects.items():
        aarch64_relocatable_file(path)
        try:
            lines=subprocess.check_output(
                ["aarch64-linux-gnu-nm",str(path)],stderr=subprocess.DEVNULL,
                text=True,timeout=15)
        except (OSError,subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as exc:
            raise IncompatibleSymbols("Could not inspect AArch64 object symbols") from exc
        inputs[name]=parse_nm(lines)
    return calculate(kernel,inputs)

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("known_good_vmlinux_module_symvers",type=Path)
    for component in COMPONENTS:
        p.add_argument(component+"_object",type=Path)
    args=p.parse_args()
    files={name:getattr(args,name+"_object") for name in COMPONENTS}
    try:
        result=inspect(args.known_good_vmlinux_module_symvers,files)
    except (OSError,IncompatibleSymbols) as exc:
        print("N71_WIFI_SYMBOL_AUDIT_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    for name in COMPONENTS:
        missing=result["missing"][name]
        print("MODULE",name,"RESOLVED",result["resolved"][name],
              "UNRESOLVED",len(missing))
        if missing:
            print("MISSING_GENERIC_KERNEL_SYMBOLS",",".join(missing[:30]))
    expected={name:[] for name in COMPONENTS}
    expected[EXPECTED_SINGLE_BLOCKER[0]]=[EXPECTED_SINGLE_BLOCKER[1]]
    need_expected=result["missing"]==expected
    if not need_expected:
        print("N71_WIFI_SYMBOL_AUDIT_UNEXPECTED_DEPENDENCY_BLOCKED")
        return 1
    print("N71_BRCMFMAC_STATIC_SYMBOL_COVERAGE_EXPECTED_SINGLE_BLOCKER_PASS")
    print("CFG80211_KERNEL_PKC7_VERIFICATION_EXPORT_MISSING=YES")
    print("BRCMUTIL_GPIO_MODULE_OFFLINE_LINK_INDEPENDENT=YES")
    print("ALTERNATE_KERNEL_LINKAGE_AND_NATIVE_PCIE_WIFI_PROVEN=NO")
    return 0

if __name__=="__main__":raise SystemExit(main())
