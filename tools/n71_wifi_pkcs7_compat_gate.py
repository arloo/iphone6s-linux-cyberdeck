#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline N71 Wi-Fi signed regulatory PKCS#7 core-export compatibility gate.

Proves that separately compiled AArch64 certs/system_keyring.o exports the
cfg80211-required PKCS7 verification symbol while original trusted kernel
does not. Does NOT construct/link/boot any new vmlinux or load a module.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def import_tool(name:str,relative:str):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    assert spec and spec.loader
    tool=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool

KCONFIG=import_tool("n71_regdb_config","n71_wifi_kernel_baseline_gate.py")
SYMBOLS=import_tool("n71_regdb_symbols","n71_wifi_kernel_symbol_gate.py")

class UnsupportedRegulatoryKernel(ValueError):
    pass

def need(ok:bool,why:str):
    if not ok:raise UnsupportedRegulatoryKernel(why)

def qualify_config(
    base:dict[str,str],candidate:dict[str,str],
    original_exported:set[str],cert_new_exports:set[str],
    cfg80211_imports:set[str])->dict[str,bool]:
    symbol="verify_pkcs7_signature"
    need(base.get("CONFIG_SYSTEM_DATA_VERIFICATION","n")=="n",
         "Known-good original N71 core signature feature changed")
    need(candidate.get("CONFIG_SYSTEM_DATA_VERIFICATION")=="y",
         "Candidate kernel lacks original PKCS7 data verification")
    need(candidate.get("CONFIG_CFG80211_REQUIRE_SIGNED_REGDB")=="y",
         "Unsigned regulatory database would be accepted")
    need(candidate.get("CONFIG_CFG80211_USE_KERNEL_REGDB_KEYS")=="y",
         "Kernel signing keys not explicitly selected")
    need(candidate.get("CONFIG_ASYMMETRIC_KEY_TYPE")=="y" and
         candidate.get("CONFIG_PKCS7_MESSAGE_PARSER")=="y",
         "Kernel certificate parser dependencies missing")
    need(symbol not in original_exported,
         "Original vmlinux export unexpectedly present")
    need(symbol in cert_new_exports,
         "Candidate certs/system_keyring.o lacks PKCS7 export")
    need(symbol in cfg80211_imports,
         "Candidate cfg80211 no longer references expected PKCS7 validator")
    return {
       "old_core_lacks_pkcs7":True,
       "candidate_source_object_exports_pkcs7":True,
       "signed_regulatory_policy_enabled":True,
       "new_core_linked_and_booted":False,
    }

def nm(source:Path)->tuple[set[str],set[str]]:
    SYMBOLS.aarch64_relocatable_file(source)
    try:
        lines=subprocess.check_output(
            ["aarch64-linux-gnu-nm",str(source)],
            text=True,stderr=subprocess.DEVNULL,timeout=15)
    except (OSError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise UnsupportedRegulatoryKernel("Could not read AArch64 ELF symbols") from exc
    return SYMBOLS.parse_nm(lines)

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("known_good_kernel_config",type=Path)
    p.add_argument("candidate_wifi_kernel_config",type=Path)
    p.add_argument("known_good_vmlinux_symvers",type=Path)
    p.add_argument("candidate_cert_system_keyring_arm64_object",type=Path)
    p.add_argument("candidate_cfg80211_arm64_object",type=Path)
    args=p.parse_args()
    try:
        base=KCONFIG.parse_kconfig(args.known_good_kernel_config.read_bytes())
        new=KCONFIG.parse_kconfig(args.candidate_wifi_kernel_config.read_bytes())
        core=SYMBOLS.parse_kernel_exports(args.known_good_vmlinux_symvers.read_bytes())
        _cert_imports,cert_exports=nm(args.candidate_cert_system_keyring_arm64_object)
        cfg_imports,_cfg_exports=nm(args.candidate_cfg80211_arm64_object)
        qualify_config(base,new,core,cert_exports,cfg_imports)
    except (OSError,KCONFIG.UnqualifiedConfig,
            SYMBOLS.IncompatibleSymbols,UnsupportedRegulatoryKernel) as exc:
        print("N71_PKCS7_WIFI_CORE_EXPORT_FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1
    print("N71_WIFI_NEW_ARM64_CERTS_PKCS7_EXPORT_COMPILATION_PASS")
    print("KNOWN_GOOD_BOOT_KERNEL_EXPORT_MISSING=YES")
    print("CFG80211_EXPECTED_DEPENDENCY_SATISFIED_IN_CANDIDATE_OBJECT_GRAPH=YES")
    print("CFG80211_SIGNED_REGULATORY_DATABASE_POLICY_RETAINED=YES")
    print("NEW_VMLINUX_LINKED_OR_BOOTED=NO")
    print("NO_KERNEL_MODIFY_NO_MODULE_LOAD_NO_HARDWARE_ACCESS")
    return 0

if __name__=="__main__":raise SystemExit(main())
