"""A9 original four-port root PCIe tunable-collision safety tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_s8000_root_tunables_crossport_impact_gate.py"
spec=importlib.util.spec_from_file_location("n71_crossport_impact",TOOL)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

def row(offset,mask=0x2,value=0x2):
    return {"offset":offset,"width":4,
            "candidate_mask":mask,"candidate_value":value}

def good():
    return {
        "apcie-common-tunables":
            [row(o) for o in (0x100,0x180,0x200,0x280)]+
            [row(0x1000+i*4) for i in range(30)],
        "apcie-phy-tunables":
            [row(0x2000+i*4) for i in range(41)],
        "apcie-config-tunables":
            [row(0x400+i*4) for i in range(6)],
        "pcie-rc-tunables":
            [row(0x500+i*4) for i in range(2)],
    }

class TestN71S8000RootCrossPortImpact(unittest.TestCase):
    def test_original_pattern_classifies_all_ports(self):
        r=M.classify_original_records(good())
        self.assertEqual(r["crossport"],4)
        self.assertEqual(r["protected_ports"],(0,2,3))
        self.assertFalse(r["root_write_safely_isolated"])
        self.assertFalse(r["status_direct"])
    def test_all_four_port_reg2_offsets(self):
        for p in range(4):
            self.assertEqual(M.mapping()[p,2],0x100+0x80*p)
    def test_all_four_port_reg5_offsets(self):
        for p in range(4):
            self.assertEqual(M.mapping()[p,5],0x12c+0x80*p)
    def test_change_storage_port0_address_rejected(self):
        t=good();t["apcie-common-tunables"][0]["offset"]=0x104
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_change_wlan_port1_address_rejected(self):
        t=good();t["apcie-common-tunables"][1]["offset"]=0x184
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_change_baseband_port2_address_rejected(self):
        t=good();t["apcie-common-tunables"][2]["offset"]=0x204
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_change_unknown_port3_address_rejected(self):
        t=good();t["apcie-common-tunables"][3]["offset"]=0x284
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_root_status_2c_direct_write_rejected(self):
        t=good();t["apcie-common-tunables"][4]["offset"]=0x2c
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_port1_status_1ac_direct_write_rejected(self):
        t=good();t["apcie-common-tunables"][4]["offset"]=0x1ac
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_unexpected_other_port_selector_collision_rejected(self):
        t=good();t["apcie-common-tunables"][4]["offset"]=0x114
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_crossport_bit0_mutation_rejected(self):
        t=good();t["apcie-common-tunables"][2]["candidate_mask"]=3
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_zero_crossport_write_mask_rejected(self):
        t=good();t["apcie-common-tunables"][1]["candidate_mask"]=0
        t["apcie-common-tunables"][1]["candidate_value"]=0
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_wide_unbounded_mask_rejected(self):
        t=good();t["apcie-phy-tunables"][0]["candidate_mask"]=1<<40
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_value_outside_mask_rejected(self):
        t=good();t["apcie-phy-tunables"][0]["candidate_value"]=0x8000
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_duplicate_offset_in_bank_rejected(self):
        t=good();t["apcie-phy-tunables"][5]["offset"]=t["apcie-phy-tunables"][4]["offset"]
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_port1_distinct_banks_with_overlap_rejected(self):
        t=good();t["pcie-rc-tunables"][0]["offset"]=0x400
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_zero_record_count_rejected(self):
        t=good();t["apcie-phy-tunables"].pop()
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_unapproved_bank_rejected(self):
        t=good();t["mystery-port4-tunables"]=[]
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_misaligned_offset_rejected(self):
        t=good();t["apcie-phy-tunables"][2]["offset"]+=1
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_wrong_record_width_rejected(self):
        t=good();t["apcie-phy-tunables"][3]["width"]=8
        with self.assertRaises(M.UnqualifiedCrossPortWrite):
            M.classify_original_records(t)
    def test_source_does_not_print_private_mask_or_value(self):
        s=TOOL.read_text()
        for bad in ("print(records)","print(groups)","print(original_adt)",
                    "print(root_plist)","print(port1_plist)","insmod",
                    "writel","ioremap","devmem","setpci","modprobe"):
            self.assertNotIn(bad,s)
        self.assertIn("N71_S8000_SHARED_ROOT_BANK_REPLAY_AS_PORT1_ONLY_SAFE=NO",s)

if __name__=="__main__":
    unittest.main()
