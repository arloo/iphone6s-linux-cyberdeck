#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only Apple Device Tree (ADT) PCIe topology explorer.

Usage: python3 tools/adt-pcie-map.py /path/to/my-private-runtime-adt.bin

Accepts a locally extracted *binary Apple ADT*, not a flattened Linux DTB.
Prints only allow-listed hardware topology and register details. Never prints
MAC addresses, calibration, serials, NVRAM, passwords or arbitrary properties.
Do NOT commit the ADT binary, extracts or raw hardware logs.
"""
from __future__ import annotations
import argparse
import struct
from pathlib import Path

MAX_FILE = 16 * 1024 * 1024
MAX_DEPTH = 40
MAX_PROPS = 4096
MAX_CHILDREN = 4096
MATCH = ("apcie", "pcie", "wlan", "wifi", "dart-apcie", "nvme")


class InvalidADT(ValueError):
    pass


def uint32(blob: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(blob):
        raise InvalidADT("Unexpected end of ADT")
    return struct.unpack_from("<I", blob, offset)[0]


def printable_name(value: bytes) -> str:
    s = value.split(b"\0", 1)[0]
    if not s or len(s) > 128 or any(x < 32 or x > 126 for x in s):
        raise InvalidADT("Invalid node or property name")
    return s.decode("ascii")


def format_u32_array(value: bytes) -> str:
    if len(value) % 4 or len(value) > 128:
        return f"({len(value)} bytes; not displayed)"
    return ", ".join(hex(v[0]) for v in struct.iter_unpack("<I", value))


def format_reg(value: bytes) -> str:
    if len(value) % 16 or len(value) > 16 * 64:
        return f"({len(value)} bytes; not displayed)"
    return "; ".join(
        f"base={hex(addr)}, size={hex(size)}"
        for addr, size in struct.iter_unpack("<QQ", value)
    )


def relevant(path: str) -> bool:
    return any(key in path.lower() for key in MATCH)


def print_hardware_node(path: str, props: dict[str, bytes]) -> None:
    print(f"NODE {path}")
    if "compatible" in props:
        value = props["compatible"]
        # Deliberately suppress non-printable or oversized content.
        tokens = value.strip(b"\0").split(b"\0")
        if len(value) <= 256 and all(
            0 < len(v) <= 100 and all(32 <= c <= 126 for c in v)
            for v in tokens
        ):
            print("  compatible: " + ", ".join(v.decode("ascii") for v in tokens))
    if "reg" in props:
        print("  reg: " + format_reg(props["reg"]))
    for key in ("#ports", "bus-range", "clock-gates", "power-gates",
                "interrupts", "iommu-parent", "msi-vector-offset"):
        if key in props:
            print(f"  {key}: {format_u32_array(props[key])}")


def parse_node(blob: bytes, pos: int, parent: str, depth: int = 0, visitor=None) -> int:
    if depth > MAX_DEPTH:
        raise InvalidADT("Excessive node nesting")
    nprops, nchildren = uint32(blob, pos), uint32(blob, pos + 4)
    if nprops > MAX_PROPS or nchildren > MAX_CHILDREN:
        raise InvalidADT("Implausible ADT counts")
    pos += 8
    props: dict[str, bytes] = {}
    for _ in range(nprops):
        if pos + 36 > len(blob):
            raise InvalidADT("Incomplete property header")
        rawname = blob[pos:pos + 32]
        key = printable_name(rawname)
        length = uint32(blob, pos + 32) & 0x7FFFFFFF
        pos += 36
        if length > len(blob) - pos:
            raise InvalidADT("Incomplete property value")
        if key in ("name", "compatible", "reg", "#ports", "bus-range",
                   "clock-gates", "power-gates", "interrupts",
                   "iommu-parent", "msi-vector-offset"):
            props[key] = blob[pos:pos + length]
        pos = (pos + length + 3) & ~3

    name = printable_name(props.get("name", b""))
    path = parent + "/" + name
    if relevant(path):
        if visitor is not None:
            visitor(path, props)
        else:
            print_hardware_node(path, props)
    for _ in range(nchildren):
        pos = parse_node(blob, pos, path, depth + 1, visitor)
    return pos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adt", type=Path, help="Private read-only Apple ADT binary")
    args = parser.parse_args()
    size = args.adt.stat().st_size
    if not (8 < size <= MAX_FILE):
        parser.error("Invalid Apple ADT file size")
    blob = args.adt.read_bytes()
    try:
        parsed = parse_node(blob, 0, "")
    except InvalidADT as exc:
        parser.error(str(exc))
    print(f"Parsed {parsed} ADT bytes (input {len(blob)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
