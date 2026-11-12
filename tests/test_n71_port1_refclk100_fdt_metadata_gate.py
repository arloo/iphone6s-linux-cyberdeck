"""A9 N71 port1 100-us refclk provenance: fail closed on 0x100 vs 0x64."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import sys
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_port1_refclk100_fdt_metadata_gate.py"
spec=importlib.util.spec_from_file_location("n71_refclk100_gate",TOOL)
assert spec and spec.loader
G=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=G
spec.loader.exec_module(G)

GOOD={
    "compatible":"apple,s8000-pcie-research-blocked",
    "status":"okay",
    "reg":"6 2000000 0 4000 6 2004000 0 4000 6 2008000 0 4000",
    "reg-names":"port1-reg-a port1-reg-b dart1-reg",
    "hardware-block":"YES",
    "research-port":"1",
    "dart-mapper":"0",
    "refclk-us":"64",
}

class TestN71Port1Refclk100Gate(unittest.TestCase):
    def test_correct_100_microseconds_passes(self):
        self.assertTrue(G.validate_snapshot(dict(GOOD)))

    def test_original_real_world_fdtput_hex_100_is_256us_and_rejected(self):
        bad={**GOOD,"refclk-us":"100"}
        self.assertEqual(G.decode_hex_cells("100"),(256,))
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot(bad)

    def test_explicit_hex_64_is_decimal_100us(self):
        self.assertEqual(G.decode_hex_cells("64"),(100,))
        self.assertEqual(G.decode_hex_cells("00000064"),(100,))

    def test_wrong_dart_mapper_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"dart-mapper":"1"})

    def test_wrong_original_port_index_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"research-port":"0"})

    def test_wrong_port1_phy_window_rejected(self):
        bad=GOOD["reg"].replace("2004000","1004000")
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"reg":bad})

    def test_swapped_resource_order_rejected(self):
        cells=GOOD["reg"].split()
        bad=" ".join(cells[4:8]+cells[:4]+cells[8:])
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"reg":bad})

    def test_wrong_hardware_compatible_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"compatible":"apple,pcie"})

    def test_missing_activation_block_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"hardware-block":"NO"})

    def test_wrong_of_status_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"status":"disabled"})

    def test_missing_metadata_rejected(self):
        bad=dict(GOOD)
        del bad["refclk-us"]
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot(bad)

    def test_extra_research_metadata_rejected(self):
        with self.assertRaises(G.UnprovenMetadata):
            G.validate_snapshot({**GOOD,"research,hardware-enabled":"1"})

    def test_malformed_hex_rejected(self):
        for raw in ("0x64","0x100","-1","64 65","0g","", "a"*9):
            with self.subTest(raw=raw):
                if raw=="64 65":
                    self.assertEqual(G.decode_hex_cells(raw),(100,101))
                else:
                    with self.assertRaises(G.UnprovenMetadata):
                        G.decode_hex_cells(raw)

    def test_no_device_actions_in_offline_gate(self):
        source=TOOL.read_text()
        for bad in ("insmod","ioremap","devmem","writel","dd if=","flash_erase","mount -o rw"):
            self.assertNotIn(bad,source)
        self.assertIn("N71_NATIVE_WIFI_FUNCTIONALITY_NOT_PROVEN=YES",source)

if __name__=="__main__":
    unittest.main()
