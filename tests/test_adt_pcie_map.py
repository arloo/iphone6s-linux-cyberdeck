#!/usr/bin/env python3
"""Synthetic ADT parser tests: no real device ADT is loaded in CI."""
from __future__ import annotations
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import struct
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "adt-pcie-map.py"
spec = importlib.util.spec_from_file_location("adt_pcie_map", TOOL)
adt = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(adt)

def prop(name: str, value: bytes) -> bytes:
    return name.encode("ascii").ljust(32, b"\0") + struct.pack("<I", len(value)) + value + b"\0" * (-len(value) % 4)

def node(name: str, children=(), extra=()) -> bytes:
    props = [prop("name", name.encode() + b"\0"), *extra]
    return struct.pack("<II", len(props), len(children)) + b"".join(props) + b"".join(children)

class TestADT(unittest.TestCase):
    def test_synthetic_topology_excludes_private_property(self):
        wlan = node("wlan", extra=[prop("compatible", b"wlan-pcie,bcm4350\0"),
                                   prop("secret-unique-id", b"NEVER_PRINT_ME")])
        host = node("apcie", children=[node("pci-bridge1", children=[wlan])],
                    extra=[prop("#ports", struct.pack("<I", 4))])
        root = node("device-tree", children=[host])
        out = io.StringIO()
        with redirect_stdout(out):
            parsed = adt.parse_node(root, 0, "")
        self.assertEqual(parsed, len(root))
        self.assertIn("/device-tree/apcie/pci-bridge1/wlan", out.getvalue())
        self.assertIn("#ports: 0x4", out.getvalue())
        self.assertNotIn("NEVER_PRINT_ME", out.getvalue())

    def test_truncated_header_rejected(self):
        with self.assertRaises(adt.InvalidADT):
            adt.parse_node(struct.pack("<II", 1, 0) + b"short", 0, "")

    def test_bad_counts_rejected(self):
        with self.assertRaises(adt.InvalidADT):
            adt.parse_node(struct.pack("<II", 99999, 0), 0, "")

if __name__ == "__main__":
    unittest.main()
