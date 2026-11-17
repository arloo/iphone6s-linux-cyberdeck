#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71 Samsung S8000 original Apple storage callback provenance gate.

Source: owner-authorized original Apple N71 ARM64 kernelcache + ADT.
Read-only and fail-closed. This code never opens /dev/mem or the phone.
No executable bytes or per-device identities are published.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import n71_s8000_original_port1_local_fanout_gate as FANOUT
import n71_original_apple_adt_iommu_parent_graph_gate as ADT

FOURCC = 0x46616374   # original Apple ADT storage callback tag
STORAGE_CALLBACKS = {
    "function-dart_force_active": 0x80,
    "function-nvme_mmu_force_active": 0x82,
}
# Genuine N71/S8000 phandles, NOT PMGR device IDs and NOT MMIO addresses.
EXPECTED_FORCE_ACTIVE_PHANDLES = {
    0x80: "dart-apcie0",
    0x81: "dart-apcie0/mapper-apcie0",
    0x82: "nvme-mmu0",
    0x83: "dart-apcie1",
    0x84: "dart-apcie1/mapper-apcie1",
    0x85: "dart-apcie2",
    0x86: "dart-apcie2/mapper-apcie2",
}
EXPECTED_BRIDGE_FACT_ACTIONS = {
    "apcie/pci-bridge0": {
        "function-dart_force_active": 0x80,
        "function-nvme_mmu_force_active": 0x82,
    },
    "apcie/pci-bridge1": {"function-dart_force_active": 0x83},
    "apcie/pci-bridge2": {"function-dart_force_active": 0x85},
}
# Derived, exact ARM64 instruction identities at known original KEXT offsets.
# These verify that two callback objects are fetched and called in the
# original N71 S8000 source. Not an authorization to execute them under Linux.
S800X_WORDS = {
    0x09dc: 0x90ffb501,   # Apple storage callback property ADRP (reference 1)
    0x09e0: 0x91392821,
    0x09f8: 0x90ffb501,   # same callback property, second reference
    0x09fc: 0x91392821,
    0x0a08: 0xf905b260,   # saved callback pointer -> port-object +2912
    0x1174: 0xb9000fff,   # first pass: value 0 in shared stack slot
    0x1178: 0xf9409800,   # DART function -> object +304
    0x1180: 0xf9404108,   # callback dispatch through virtual slot 128
    0x1184: 0x910033e1,
    0x1190: 0xd63f0100,
    0x1194: 0xf945b260,   # NVMMU function -> object +2912
    0x119c: 0xf9400008,
    0x11a0: 0xf9404108,
    0x11a4: 0x910033e1,
    0x11b0: 0xd63f0100,
    0x1328: 0x52800028,   # second pass: value 1 to shared stack slot
    0x132c: 0xb9000fe8,
    0x1330: 0xf9409a60,   # DART callback before NVMMU
    0x1338: 0xf9404108,
    0x1348: 0xd63f0100,
    0x134c: 0xf945b260,   # NVMMU callback second
    0x1358: 0xf9404108,
    0x1368: 0xd63f0100,
}
EMBEDDED_WORDS = {
    0x4e30: 0xd0ffb537,   # DART callback ADT name reference
    0x4e34: 0x910192f7,
    0x4e4c: 0x52800102,   # property size 8 bytes
    0x4e50: 0x52800003,
    0x4e74: 0xf9009a80,   # saved DART callback object -> +304
}

class UnsafeSource(ValueError):
    pass

def require(condition: bool, reason: str) -> None:
    if not condition:
        raise UnsafeSource(reason)

def check_callback_properties(bridge: dict[str, bytes]) -> None:
    require("nvme-mode" in bridge and bridge["nvme-mode"] == b"",
            "Missing original S8000 storage NVMe mode boolean")
    for key, expected in STORAGE_CALLBACKS.items():
        value = bridge.get(key)
        require(isinstance(value, bytes) and len(value) == 8,
                f"Invalid Apple storage callback {key} length")
        number, tag = struct.unpack("<II", value)
        require(number == expected and tag == FOURCC,
                f"Unrecognized callback descriptor {key}")
    require(STORAGE_CALLBACKS["function-dart_force_active"] !=
            STORAGE_CALLBACKS["function-nvme_mmu_force_active"],
            "Storage callback selectors unexpectedly alias")

def resolve_fact_phandle_graph(nodes: dict[str, dict[str, bytes]]) -> None:
    """Every original Fact selector resolves to a unique, correct ADT node.

    A Fact selector addresses an Apple IODeviceTree registry object.  The
    descriptor must not be confused with an ApplePMGR device-index, physical
    MMIO offset, or the distinct mapper child used in iommu-parent.
    """
    lookup: dict[int, str] = {}
    for path, properties in nodes.items():
        raw = properties.get("AAPL,phandle")
        if raw is None:
            continue
        require(len(raw) == 4, "Malformed ADT registry phandle")
        phandle = struct.unpack("<I", raw)[0]
        require(phandle not in lookup, "Duplicate ADT registry phandle")
        lookup[phandle] = path
    for number, expected_path in EXPECTED_FORCE_ACTIVE_PHANDLES.items():
        require(lookup.get(number) == ADT.ROOT + expected_path,
                "Fact target no longer resolves to the original Apple device")
    for name, expected_functions in EXPECTED_BRIDGE_FACT_ACTIONS.items():
        properties = nodes.get(ADT.ROOT + name)
        require(isinstance(properties, dict),
                "Required original Apple bridge missing")
        for key, phandle in expected_functions.items():
            raw = properties.get(key)
            require(isinstance(raw, bytes) and len(raw) == 8,
                    "Fact descriptor size invalid")
            require(struct.unpack("<II", raw) == (phandle, FOURCC),
                    "Fact callback ID does not resolve to intended device")
    endpoint = nodes.get(ADT.PORT0)
    require(isinstance(endpoint, dict), "Real S3E storage endpoint missing")
    parent = endpoint.get("iommu-parent")
    require(parent == struct.pack("<III", 0x81, 0x81, 0x82),
            "Storage endpoint IOMMU parent must resolve to DART0 mapper and NVMMU0")
    require(lookup[0x80] != lookup[0x81],
            "DART0 device and mapper child unexpectedly conflated")


def pmgr_entries(raw: bytes) -> dict[int, str]:
    """49? No: each original S8000 PMGR ADT device record is 48 bytes."""
    require(len(raw) == 4944 and len(raw) % 48 == 0,
            "Original PMGR device table extent mismatch")
    result = {}
    for idx in range(0, len(raw), 48):
        record = raw[idx:idx+48]
        ident = record[3]              # high byte of first little-endian u32
        require(ident not in result, "PMGR hardware device-ID collision")
        try:
            name = record[32:48].split(b"\0", 1)[0].decode("ascii")
        except UnicodeDecodeError as e:
            raise UnsafeSource("Malformed PMGR device identifier") from e
        require(name and all(32 <= ord(ch) <= 126 for ch in name),
                "Malformed PMGR device name")
        result[ident] = name
    return result

def check_not_pmgr_ids(raw: bytes) -> None:
    parsed = pmgr_entries(raw)
    # Critical proven distinction: 0x80 in the callback's two-word
    # descriptor is NOT an ordinary Apple PMGR device index.
    require(parsed.get(0x80) == "VENC_ME0",
            "PMGR device 0x80 no longer matches the original S8000 source")
    require(0x82 not in parsed,
            "PMGR unexpectedly contains callback selector 0x82")

def pin_words(code: bytes, words: dict[int, int]) -> None:
    require(len(code) >= max(words)+4, "Truncated Apple original KEXT text")
    for pos, expected in words.items():
        actual = struct.unpack_from("<I", code, pos)[0]
        require(actual == expected,
                "Original Apple callback instruction identity changed")

def audit(kernelcache: bytes, adt: bytes) -> None:
    # FANOUT verifies original Mach-O segment bounds, authentic KEXT
    # constructors and exact root/port vtable provenance independently.
    _main, portmods, _rootmods = FANOUT.original_port_vtable(kernelcache)
    require(len(portmods["shared"]["code"]) == 18552, "S800x text length mismatch")
    require(len(portmods["embedded"]["code"]) == 46924, "EmbeddedPCIE text mismatch")
    pin_words(portmods["shared"]["code"], S800X_WORDS)
    pin_words(portmods["embedded"]["code"], EMBEDDED_WORDS)
    nodes = ADT.parse_adt(adt)
    bridge = nodes.get(ADT.ROOT+"apcie/pci-bridge0")
    pmgr = nodes.get(ADT.ROOT+"pmgr")
    require(isinstance(bridge, dict) and isinstance(pmgr, dict),
            "Original N71 storage bridge and PMGR ADT nodes missing")
    check_callback_properties(bridge)
    resolve_fact_phandle_graph(nodes)
    check_not_pmgr_ids(pmgr.get("devices", b""))

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernelcache", type=Path)
    parser.add_argument("original_adt", type=Path)
    args = parser.parse_args()
    try:
        audit(args.kernelcache.read_bytes(), args.original_adt.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error) as err:
        # Never print raw file paths, original data or private register values.
        print("N71_STOCK_STORAGE_CALLBACK_SOURCE_GATE=REJECTED")
        raise SystemExit(1) from None
    print("N71_STOCK_S8000_STORAGE_CALLBACK_SOURCE_GATE=PASS")
    print("N71_APPLE_DART0_NVMMU0_FUNCTION_DESCRIPTORS_DISTINCT=YES")
    print("N71_STOCK_CALL_ORDER_DART_THEN_NVMMU_FOR_BOTH_STATES=YES")
    print("N71_STOCK_CALLBACK_STATE_WORDS_0_AND_1_PROVEN=YES")
    print("N71_CALLBACK_0X80_IS_NOT_PMGR_STORAGE_DEVICE=YES")
    print("N71_FACT_ACTION_IDS_ARE_REAL_APPLE_IOTREE_PHANDLES=YES")
    print("N71_STORAGE_DART0_TARGET=0X80_MAPPER=0X81_NVMMU_TARGET=0X82")
    print("N71_WIFI_DART1_TARGET=0X83_MAPPER=0X84")
    print("N71_BASEBAND_DART2_TARGET=0X85_MAPPER=0X86")
    print("N71_DART0_NVMMU0_PHYSICAL_ENABLE_SEQUENCE_QUALIFIED=NO")
    print("N71_STORAGE_PHYSICAL_MMIO_DMA_OR_NAND_OPERATION=NO")

if __name__ == "__main__":
    main()
