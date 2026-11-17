#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic regression tests: no private Apple binaries or phone required."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import n71_s8000_storage_force_active_chain_gate as gate

def bridge() -> dict[str, bytes]:
    return {
        "nvme-mode": b"",
        "function-dart_force_active": struct.pack("<II",0x80,gate.FOURCC),
        "function-nvme_mmu_force_active": struct.pack("<II",0x82,gate.FOURCC),
    }

def fake_pmgr_entries() -> bytes:
    raw = bytearray(4944)
    for idx in range(103):
        i = idx*48
        # Only the last row has ID 0x80, deliberately NOT a storage device.
        ident = idx+1 if idx!=102 else 0x80
        raw[i+3] = ident
        name = b"VENC_ME0" if ident==0x80 else f"FAKE_{ident:02X}".encode()
        raw[i+32:i+32+len(name)] = name
    return bytes(raw)

def phandle_graph() -> dict[str, dict[str, bytes]]:
    result = {}
    for number, path in gate.EXPECTED_FORCE_ACTIVE_PHANDLES.items():
        result[gate.ADT.ROOT+path] = {
            "AAPL,phandle": struct.pack("<I",number)}
    for name, functions in gate.EXPECTED_BRIDGE_FACT_ACTIONS.items():
        result[gate.ADT.ROOT+name] = {
            key:struct.pack("<II",value,gate.FOURCC)
            for key,value in functions.items()}
    result[gate.ADT.PORT0] = {
        "iommu-parent": struct.pack("<III",0x81,0x81,0x82)}
    return result


class StorageCallbackGateTests(unittest.TestCase):
    def test_fact_target_phandles_are_real_registry_nodes(self):
        gate.resolve_fact_phandle_graph(phandle_graph())
    def test_renumber_dart0_phandle_must_fail(self):
        graph=phandle_graph()
        graph[gate.ADT.ROOT+"dart-apcie0"]["AAPL,phandle"]=struct.pack("<I",0x90)
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_dart0_controller_and_mapper_must_be_separate(self):
        graph=phandle_graph()
        graph[gate.ADT.ROOT+"dart-apcie0/mapper-apcie0"]["AAPL,phandle"]=struct.pack("<I",0x80)
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_duplicate_phandle_must_fail(self):
        graph=phandle_graph()
        graph[gate.ADT.ROOT+"extra"]= {"AAPL,phandle":struct.pack("<I",0x80)}
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_swapping_wifi_and_storage_fact_callback_fails(self):
        graph=phandle_graph()
        graph[gate.ADT.ROOT+"apcie/pci-bridge1"]["function-dart_force_active"]=struct.pack("<II",0x80,gate.FOURCC)
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_storage_iommu_parent_missing_nvmmu_fails(self):
        graph=phandle_graph()
        graph[gate.ADT.PORT0]["iommu-parent"]=struct.pack("<III",0x81,0x81,0x80)
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_malformed_fact_fourcc_fails(self):
        graph=phandle_graph()
        graph[gate.ADT.ROOT+"apcie/pci-bridge2"]["function-dart_force_active"]=struct.pack("<II",0x85,0x11111111)
        with self.assertRaises(gate.UnsafeSource):
            gate.resolve_fact_phandle_graph(graph)
    def test_valid_descriptors(self):
        gate.check_callback_properties(bridge())
    def test_missing_nvme_mode(self):
        x=bridge(); del x["nvme-mode"]
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_nonempty_nvme_mode(self):
        x=bridge(); x["nvme-mode"]=b"\x01"
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_missing_dart_callback(self):
        x=bridge(); del x["function-dart_force_active"]
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_wrong_nvmmu_callback_id(self):
        x=bridge(); x["function-nvme_mmu_force_active"]=struct.pack("<II",0x80,gate.FOURCC)
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_nonfact_tag(self):
        x=bridge(); x["function-dart_force_active"]=struct.pack("<II",0x80,0x12345678)
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_wrong_descriptor_size(self):
        x=bridge(); x["function-nvme_mmu_force_active"]=b"\0"*12
        with self.assertRaises(gate.UnsafeSource):
            gate.check_callback_properties(x)
    def test_original_pmgr_id_is_not_storage(self):
        x=gate.pmgr_entries(fake_pmgr_entries())
        self.assertEqual(x[0x80],"VENC_ME0")
        self.assertNotIn(0x82,x)
        gate.check_not_pmgr_ids(fake_pmgr_entries())
    def test_reject_callback_as_pmgr_storage_id(self):
        x=bytearray(fake_pmgr_entries())
        x[102*48+32:102*48+40]=b"STORAGE0"
        with self.assertRaises(gate.UnsafeSource):
            gate.check_not_pmgr_ids(bytes(x))
    def test_reject_duplicate_pmgr_id(self):
        x=bytearray(fake_pmgr_entries())
        x[48+3]=x[3]
        with self.assertRaises(gate.UnsafeSource):
            gate.pmgr_entries(bytes(x))
    def test_reject_pmgr_table_truncation(self):
        with self.assertRaises(gate.UnsafeSource):
            gate.pmgr_entries(fake_pmgr_entries()[:-1])
    def test_exact_arm64_source_pins(self):
        words={0:0x11223344,4:0x55667788,8:0x99aabbcc}
        buffer=struct.pack("<III",*words.values())
        gate.pin_words(buffer,words)
        bad=bytearray(buffer);bad[4]^=1
        with self.assertRaises(gate.UnsafeSource):
            gate.pin_words(bytes(bad),words)
    def test_reject_truncated_arm64_source(self):
        with self.assertRaises(gate.UnsafeSource):
            gate.pin_words(b"\0"*4,{4:0})
    def test_callback_state_both_pinned(self):
        self.assertEqual(gate.S800X_WORDS[0x1174],0xb9000fff)
        self.assertEqual(gate.S800X_WORDS[0x132c],0xb9000fe8)
        for x in (0x1178,0x1194,0x1330,0x134c):
            self.assertIn(x,gate.S800X_WORDS)

if __name__ == "__main__":
    unittest.main()
