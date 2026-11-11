#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline-only strict S8000/N71 PCIe/DART Apple ADT window consistency gate.

Only reads a local *private* Apple ADT. Never imports, serializes or prints
unknown ADT properties. Output is aggregate hardware metadata only.

Passing does NOT establish any verified PCIe register layout, safe DMA domain,
driver compatibility, bootable Device Tree or Wi-Fi connection.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

ADT_PARSER = Path(__file__).resolve().with_name("adt-pcie-map.py")
SPEC = importlib.util.spec_from_file_location("n71_apple_adt", ADT_PARSER)
assert SPEC and SPEC.loader
ADT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADT)

PFX = "/device-tree/arm-io"
HOST = PFX + "/apcie"
WLAN = HOST + "/pci-bridge1/wlan"
DART_PATHS = {i: PFX + f"/dart-apcie{i}" for i in range(3)}
MAPPER = DART_PATHS[1] + "/mapper-apcie1"
WHITELIST = frozenset({HOST, WLAN, MAPPER, *DART_PATHS.values()})

# Verified by a bounded offline parse of the operator's private A9 Samsung ADT.
# These are hardware fixed physical address ranges, not device-unique serial,
# credentials, calibration or binary firmware. NO code maps or accesses them.
HOST_LAYOUT = (
    (0x610000000, 0x01000000),  # ECAM aperture, shared; UNVERIFIED mapping
    (0x601000000, 0x00004000),  # port 0, storage, NEVER ACTIVATE
    (0x601004000, 0x00004000),
    (0x602000000, 0x00004000),  # port 1, WLAN candidate, still disabled
    (0x602004000, 0x00004000),
    (0x603000000, 0x00004000),  # port 2, baseband, NEVER ACTIVATE
    (0x603004000, 0x00004000),
    (0x604000000, 0x00004000),  # port 3, unknown, NEVER ACTIVATE
    (0x604004000, 0x00004000),
    (0x600000000, 0x00008000),  # global PCIe core
    (0x600008000, 0x00004000),
)
DART_LAYOUT = {
    0: (0x601008000, 0x4000),
    1: (0x602008000, 0x4000),
    2: (0x603008000, 0x4000),
}


class RejectedADT(ValueError):
    pass


def compatible(props: dict[str, bytes]) -> tuple[str, ...]:
    data = props.get("compatible", b"")
    if not data or not data.endswith(b"\x00") or len(data) > 256:
        raise RejectedADT("Missing/inconsistent compatible")
    try:
        values = tuple(x.decode("ascii") for x in data[:-1].split(b"\x00"))
    except UnicodeError as exc:
        raise RejectedADT("Invalid compatible encoding") from exc
    if not all(values):
        raise RejectedADT("Empty compatible")
    return values


def cell32(props: dict[str, bytes], key: str) -> tuple[int, ...]:
    data = props.get(key)
    if data is None or len(data) == 0 or len(data) % 4 or len(data) > 64:
        raise RejectedADT(f"Missing or invalid numeric property {key}")
    return tuple(v[0] for v in struct.iter_unpack("<I", data))


def windows(props: dict[str, bytes], n: int) -> tuple[tuple[int, int], ...]:
    raw = props.get("reg", b"")
    if len(raw) != n * 16:
        raise RejectedADT("Unexpected Apple ADT MMIO window count")
    return tuple(struct.iter_unpack("<QQ", raw))


def must_equal(actual, expected, explanation: str) -> None:
    if actual != expected:
        raise RejectedADT(explanation)


def disjoint(ranges: list[tuple[str, int, int]]) -> None:
    for label, addr, length in ranges:
        if not 0 < length <= 0x10000000 or addr & 0xFFF:
            raise RejectedADT(f"Unaligned/invalid window: {label}")
        if addr + length > (1 << 48):
            raise RejectedADT("Physical window arithmetic overflow")
    for i, (lab, start, size) in enumerate(ranges):
        for other, start2, size2 in ranges[i+1:]:
            if max(start, start2) < min(start+size, start2+size2):
                raise RejectedADT(f"MMIO resource overlap: {lab}/{other}")


def inspect(props_by_path: dict[str, dict[str, bytes]]) -> str:
    if set(props_by_path) != WHITELIST:
        raise RejectedADT("Expected host, three DARTs, WLAN and WLAN mapper nodes")
    host = props_by_path[HOST]
    must_equal(compatible(host), ("apcie,s8000",), "Unexpected host silicon")
    must_equal(cell32(host, "#ports"), (4,), "S8000 port count is not four")
    must_equal(cell32(host, "bus-range"), (0, 8), "Unexpected S8000 bus range")
    must_equal(cell32(host, "interrupts"), (0xF4,0xF7,0xFA,0xFD),
               "Unexpected PCIe host interrupt layout")
    must_equal(cell32(host, "msi-vector-offset"), (0x100,),
               "MSI layout changed")
    must_equal(cell32(host, "clock-gates"), (0x39,0x3A,0x3B,0x3C,0x3D,0x3E),
               "Clock gates changed")
    must_equal(cell32(host, "power-gates"), (0x38,), "Power gate changed")
    win = windows(host, len(HOST_LAYOUT))
    must_equal(win, HOST_LAYOUT, "S8000 host window layout mismatch")
    wlan = props_by_path[WLAN]
    must_equal(compatible(wlan), ("wlan-pcie,bcm4350","wlan-pcie,bcm"),
               "Expected BCM4350 WLAN only")
    iommu_ref = cell32(wlan, "iommu-parent")
    if len(iommu_ref) != 1 or iommu_ref[0] == 0:
        raise RejectedADT("WLAN IOMMU metadata missing/ambiguous")
    mapper = props_by_path[MAPPER]
    must_equal(compatible(mapper), ("iommu-mapper",), "Unrecognized WLAN mapper")
    must_equal(cell32(mapper,"reg"), (0,), "Unexpected WLAN mapper index")
    ranges = [(f"host[{i}]",addr,sz) for i,(addr,sz) in enumerate(win)]
    for num,path in DART_PATHS.items():
        d=props_by_path[path]
        must_equal(compatible(d), ("dart,s8000", "dart,s5l8960x"),
                   "Unsupported DART fallback family")
        must_equal(windows(d,1), (DART_LAYOUT[num],),
                   "DART register window mismatch")
        must_equal(cell32(d,"interrupts"), (0xF5+3*num,),
                   "DART interrupt mismatch")
        ranges.append((f"dart{num}",*DART_LAYOUT[num]))
    disjoint(ranges)
    # In particular, the only Wi-Fi candidate windows must be disjoint
    # from the storage/baseband/global ranges and dedicated port-1 DART.
    return (
        "S8000_ADT_METADATA_GATE_PASS: 11 host windows, 3 DART windows, "
        "4 PCIe ports, WLAN=BCM4350 at port1.\n"
        "PORT1_WINDOWS=0x602000000/0x4000,0x602004000/0x4000 "
        "DART1=0x602008000/0x4000.\n"
        "DART1_FALLBACK=dart,s5l8960x; mapper-index=0; "
        "WLAN_IOMMU_REFERENCE_PRESENT=YES; windows_nonoverlapping=YES.\n"
        "HARDWARE_BLOCKED: no verified PCIe register semantics, MSI/DMA "
        "isolation, A9 controller driver, or physical WLAN enumeration. "
        "DO NOT BOOT OR TOUCH MMIO."
    )


def audit_bytes(blob: bytes) -> str:
    found: dict[str, dict[str, bytes]] = {}
    # On Apple XNU, IOMapper identifies its provider by "iommu-id", or
    # by "AAPL,phandle" if absent. Check the *entire* ADT for duplicate
    # reference IDs; only keep integer IDs and paths, never unknown data.
    ids: dict[int, str] = {}
    def visitor(path: str, props: dict[str, bytes]) -> None:
        phandle = props.get("AAPL,phandle")
        if phandle is not None:
            if len(phandle) != 4:
                raise RejectedADT("Malformed Apple phandle length")
            value = struct.unpack("<I", phandle)[0]
            if value == 0 or value in ids:
                raise RejectedADT("Null or duplicate Apple phandle")
            ids[value] = path
        if path in WHITELIST:
            if path in found:
                raise RejectedADT("Duplicate ADT target node")
            # Retain ONLY hardware metadata needed by strict validations.
            keep = {"compatible", "reg", "interrupts", "iommu-parent",
                    "#ports", "bus-range", "clock-gates", "power-gates",
                    "msi-vector-offset", "AAPL,phandle", "iommu-id",
                    "page-size", "vm-size"}
            found[path] = {k:v for k,v in props.items() if k in keep}
    try:
        parsed = ADT.parse_node(blob, 0, "", visitor=visitor, visit_all=True)
    except (ADT.InvalidADT, UnicodeError, struct.error) as exc:
        raise RejectedADT("Malformed ADT") from exc
    if parsed > len(blob):
        raise RejectedADT("ADT parser overrun")

    # Must succeed *before* we print any "PASS" result.
    # The Apple ADT uses a reference to mapper-apcie1, NOT to DART1
    # itself, and that mapper belongs to the isolated WLAN DART1.
    wlan = found.get(WLAN, {})
    mapper = found.get(MAPPER, {})
    ref = cell32(wlan, "iommu-parent")
    if len(ref) != 1 or ref[0] == 0:
        raise RejectedADT("WLAN has no unique IOMMU parent reference")
    mapper_handle = cell32(mapper, "AAPL,phandle")
    if len(mapper_handle) != 1 or mapper_handle[0] == 0:
        raise RejectedADT("Missing WLAN mapper phandle")
    if "iommu-id" in mapper:
        raise RejectedADT("Unexpected overriding mapper iommu-id requires review")
    if ref[0] != mapper_handle[0] or ids.get(ref[0]) != MAPPER:
        raise RejectedADT("WLAN IOMMU parent does not uniquely target DART1 mapper")

    dart = found.get(DART_PATHS[1], {})
    if cell32(dart, "page-size") != (4096,):
        raise RejectedADT("Unreviewed WLAN DART page size")
    if cell32(dart, "vm-size") != (0x3FFFF000,):
        raise RejectedADT("Unreviewed WLAN DART IOVA window size")
    result = inspect(found)
    return (result + "\n"
            "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED; "
            f"GLOBAL_ADT_PHANDLES_UNIQUE={len(ids)}; "
            "DART1_PAGE_SIZE=4096; "
            "DART1_VM_SIZE=0x3ffff000; "
            "DART1_STREAM_ID_HARDWARE_UNVERIFIED")


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("private_adt", type=Path)
    args=ap.parse_args()
    try:
        if args.private_adt.stat().st_size > ADT.MAX_FILE:
            raise RejectedADT("ADT input too large")
        print(audit_bytes(args.private_adt.read_bytes()))
        return 0
    except (RejectedADT,OSError) as exc:
        print("FAIL_CLOSED:",str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
