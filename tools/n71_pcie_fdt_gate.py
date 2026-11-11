#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed, OFFLINE-ONLY gate for a nonbootable N71 PCIe port-1 DT scaffold.

No hardware access, kernel module loading, /dev/mem or PCIe writes are possible
through this tool. Passing validates only the isolation *shape* of a compiled
FDT, NOT register values, IOMMU/DMA isolation or hardware readiness.

Usage:
    dtc -I dts -O dtb -o /tmp/n71-pcie-port1.dtb examples/n71-pcie-port1/port1-disabled.dts
    python3 tools/n71_pcie_fdt_gate.py /tmp/n71-pcie-port1.dtb
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import struct

MAGIC = 0xD00DFEED
MAX_BYTES = 1024 * 1024
MAX_NODES = 1024
MAX_DEPTH = 32
FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9

HOST_COMPAT = "apple,s8000-pcie-unimplemented"
DART_COMPAT = "apple,s8000-dart-unimplemented"
WLAN_COMPAT = "wlan-pcie,bcm4350"

# No physical addresses or MMIO/interrupt/DMA accesses are permitted in the
# safety scaffold. These will require a separate independently reviewed patch.
UNREVIEWED_RESOURCES = frozenset({
    "ranges", "dma-ranges", "iommus", "msi-parent", "interrupts",
    "interrupt-map", "interrupt-parent", "power-domains", "clocks",
    "resets", "reset-gpios", "phys", "phy-names", "reg-names",
    "bus-range", "memory-region", "regulator-supplies", "regulators",
})


class UnsafeTree(ValueError):
    pass


@dataclass
class Node:
    name: str
    path: str
    props: dict[str, bytes] = field(default_factory=dict)


def _within(offset: int, length: int, limit: int) -> bool:
    return offset >= 0 and length >= 0 and offset <= limit and length <= limit - offset


def _aligned4(value: int) -> int:
    return (value + 3) & ~3


def _c_string(data: bytes, start: int, end: int) -> tuple[str, int]:
    if start < 0 or end > len(data) or start >= end:
        raise UnsafeTree("Invalid FDT string position")
    stop = data.find(b"\0", start, end)
    if stop < 0:
        raise UnsafeTree("Unterminated FDT string")
    raw = data[start:stop]
    if not raw or len(raw) > 100 or any(c < 32 or c > 126 for c in raw):
        raise UnsafeTree("Invalid FDT name")
    return raw.decode("ascii"), stop + 1


def parse_fdt(blob: bytes) -> dict[str, Node]:
    if len(blob) < 40 or len(blob) > MAX_BYTES:
        raise UnsafeTree("Invalid DTB byte count")
    (magic, total, off_struct, off_strings, off_rsvmap, version, last_compat,
     _bootcpu, size_strings, size_struct) = struct.unpack_from(">10I", blob)
    if magic != MAGIC or total != len(blob):
        raise UnsafeTree("Not an exact-size FDT blob")
    if version < 17 or last_compat > 17:
        raise UnsafeTree("Unsupported FDT header version")
    if not _within(off_struct, size_struct, total) or not _within(off_strings, size_strings, total):
        raise UnsafeTree("Invalid FDT structural or string region")
    if not _within(off_rsvmap, 16, total):
        raise UnsafeTree("Missing FDT reservation region")
    if max(off_struct, off_strings) < 40:
        raise UnsafeTree("FDT overlaps header")
    start, end = off_struct, off_struct + size_struct
    strings = blob[off_strings:off_strings + size_strings]
    nodes: dict[str, Node] = {}
    stack: list[str] = []
    pos = start
    saw_end = False
    while pos < end:
        if not _within(pos, 4, end):
            raise UnsafeTree("Truncated FDT token")
        op = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if op == FDT_BEGIN_NODE:
            stop = blob.find(b"\0", pos, end)
            if stop < 0:
                raise UnsafeTree("Unterminated node")
            raw = blob[pos:stop]
            if not stack and raw != b"":
                raise UnsafeTree("FDT root must be anonymous")
            if stack and (not raw or len(raw) > 100 or b"/" in raw or
                          any(c < 32 or c > 126 for c in raw)):
                raise UnsafeTree("Invalid child node name")
            name = raw.decode("ascii")
            path = "/" if not stack else (stack[-1].rstrip("/") + "/" + name)
            if len(stack) >= MAX_DEPTH or path in nodes or len(nodes) >= MAX_NODES:
                raise UnsafeTree("FDT node nesting/duplication/limit violation")
            nodes[path] = Node(name=name, path=path)
            stack.append(path)
            pos = _aligned4(stop + 1)
        elif op == FDT_PROP:
            if not stack or not _within(pos, 8, end):
                raise UnsafeTree("Property outside node or truncated")
            length, nameoff = struct.unpack_from(">2I", blob, pos)
            pos += 8
            if not _within(pos, length, end) or not _within(nameoff, 1, len(strings)):
                raise UnsafeTree("Property value/string out of bounds")
            key, _ = _c_string(strings, nameoff, len(strings))
            props = nodes[stack[-1]].props
            if key in props:
                raise UnsafeTree("Duplicate FDT property")
            props[key] = blob[pos:pos + length]
            pos = _aligned4(pos + length)
        elif op == FDT_END_NODE:
            if not stack:
                raise UnsafeTree("FDT stack underflow")
            stack.pop()
        elif op == FDT_NOP:
            continue
        elif op == FDT_END:
            if stack:
                raise UnsafeTree("FDT end while node still open")
            saw_end = True
            break
        else:
            raise UnsafeTree("Unknown FDT token")
    if not saw_end or "/" not in nodes:
        raise UnsafeTree("FDT missing root or end")
    if any(blob[pos:end]):
        raise UnsafeTree("Nonzero trailing structural data")
    return nodes


def string_list(node: Node, key: str) -> tuple[str, ...]:
    data = node.props.get(key)
    if not data or not data.endswith(b"\0"):
        raise UnsafeTree(f"Missing or malformed {key} at {node.path}")
    try:
        entries = tuple(x.decode("ascii") for x in data[:-1].split(b"\0"))
    except UnicodeError as exc:
        raise UnsafeTree("Non-ASCII compatible or status") from exc
    if not all(entries):
        raise UnsafeTree("Empty FDT string value")
    return entries


def disabled(node: Node) -> bool:
    return string_list(node, "status") == ("disabled",)


def be32(node: Node, key: str) -> int:
    data = node.props.get(key)
    if data is None or len(data) != 4:
        raise UnsafeTree(f"Expected exactly one 32-bit {key} cell: {node.path}")
    return struct.unpack(">I", data)[0]


def verify_scaffold(nodes: dict[str, Node]) -> str:
    root = nodes.get("/")
    if root is None or string_list(root, "compatible")[:2] != ("apple,n71", "apple,s8000"):
        raise UnsafeTree("Wrong board; strictly N71/S8000 only")
    hosts = [n for n in nodes.values() if HOST_COMPAT in
             (string_list(n, "compatible") if "compatible" in n.props else ())]
    if len(hosts) != 1:
        raise UnsafeTree("Exactly one UNIMPLEMENTED S8000 host is required")
    host = hosts[0]
    if not disabled(host):
        raise UnsafeTree("The S8000 PCIe host must remain disabled")
    if "reg" in host.props or UNREVIEWED_RESOURCES.intersection(host.props):
        raise UnsafeTree("Unreviewed PCIe host MMIO/clock/DMA/IRQ properties")
    if be32(host, "#address-cells") != 1 or be32(host, "#size-cells") != 0:
        raise UnsafeTree("Wrong scaffold child address-cell format")
    ports = {}
    for node in nodes.values():
        if node.path.startswith(host.path + "/") and node.path.count("/") == host.path.count("/") + 1:
            if not node.name.startswith("port@") or not disabled(node):
                raise UnsafeTree("Unexpected or enabled host child")
            if set(node.props) - {"reg", "status"}:
                raise UnsafeTree("Unexpected PCIe port property")
            reg = be32(node, "reg")
            if reg % 0x800:
                raise UnsafeTree("Unaligned PCIe port index encoding")
            idx = reg >> 11
            if idx not in range(4) or idx in ports or node.name != f"port@{reg:x}":
                raise UnsafeTree("Unreviewed, duplicate or mislabeled port")
            ports[idx] = node
    if set(ports) != set(range(4)):
        raise UnsafeTree("Ports 0,1,2,3 must all be explicitly disabled")
    children = {n.path for n in nodes.values() if n.path.startswith(host.path + "/")}
    if children != {p.path for p in ports.values()}:
        raise UnsafeTree("No endpoint or extra PCIe child may be enabled in scaffold")
    dnodes = [n for n in nodes.values() if DART_COMPAT in
              (string_list(n, "compatible") if "compatible" in n.props else ())]
    if len(dnodes) != 1 or not disabled(dnodes[0]):
        raise UnsafeTree("One explicitly disabled A9 DART placeholder required")
    if "reg" in dnodes[0].props or UNREVIEWED_RESOURCES.intersection(dnodes[0].props):
        raise UnsafeTree("Unreviewed DART resources")
    # No other active PCIe or DART node may sneak into the candidate FDT.
    for node in nodes.values():
        if node is host or node in ports.values() or node is dnodes[0]:
            continue
        if (node.name.startswith(("pcie", "pci@", "dart", "wlan", "wifi")) or
            any(("pcie" in x or "dart" in x or "bcm4350" in x)
                for x in (string_list(node, "compatible") if "compatible" in node.props else ()))):
            raise UnsafeTree("Unknown PCIe, DART or WLAN node outside allowlist")
    return ("OFFLINE_STRUCTURE_PASS: exact N71/S8000, four disabled ports "
            "(0 storage, 1 WLAN candidate, 2 baseband, 3 unknown); DART disabled.\n"
            "HARDWARE_PROBE_BLOCKED: no S8000 PCIe driver/DART register or DMA profile "
            "has been hardware validated. This file MUST NOT be booted.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dtb", type=Path, help="offline compiled nonbootable FDT candidate")
    args = ap.parse_args()
    try:
        blob = args.dtb.read_bytes()
        print(verify_scaffold(parse_fdt(blob)))
    except (UnsafeTree, OSError, struct.error) as exc:
        print("FAIL_CLOSED:", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
