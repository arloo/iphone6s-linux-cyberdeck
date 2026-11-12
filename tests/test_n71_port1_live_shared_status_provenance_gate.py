"""Synthetic regression tests for combined original-code and captured-iOS evidence.

Mock private ORIGINAL audit results rather than shipping Apple code, ADT,
device registry, Wi-Fi OTP, addresses unique to the user or firmware.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_port1_live_shared_status_provenance_gate.py"
spec=importlib.util.spec_from_file_location("s8000_shared_live",TOOL)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def original():
    return {
      "shared_status_register_id":1,
      "shared_status_relative_offset":0x2c,
      "shared_status_bit":4,
      "shared_status_retry_backedge":True,
      "caller_level_timeout_implemented_in_original":False,
    }

def iomem():
    return gate.IOS.HOST_LAYOUT

def model():
    return gate.MODEL.read_text()

class TestA9LiveOriginalConverged(unittest.TestCase):
    def verify(self,original_value=None,mem=None,source=None):
        value=original() if original_value is None else original_value
        ranges=iomem() if mem is None else mem
        program=model() if source is None else source
        with patch.object(gate.RMW,"audit",return_value=value),\
             patch.object(gate.IOS,"compare_private_inputs",
                          return_value=ranges):
            return gate.verify_original_sources(
                b"SYNTHETIC_NO_APPLE_EXECUTABLE",
                b"SYNTHETIC_NO_DEVICE_TREE",
                b"SYNTHETIC_NO_PRIVATE_IOS",
                program)

    def test_real_original_live_crosslink(self):
        actual=self.verify()
        self.assertEqual(actual["provider_index"],9)
        self.assertEqual(actual["address"],0x60000002c)
        self.assertEqual(actual["bit"],4)
        self.assertEqual(actual["resource_count"],11)

    def test_original_register_id_changed(self):
        o=original();o["shared_status_register_id"]=2
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(original_value=o)

    def test_original_register_offset_changed(self):
        o=original();o["shared_status_relative_offset"]=0x24
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(original_value=o)

    def test_original_status_bit_changed(self):
        o=original();o["shared_status_bit"]=0
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(original_value=o)

    def test_original_poll_backedge_changed(self):
        o=original();o["shared_status_retry_backedge"]=False
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(original_value=o)

    def test_original_unbounded_poll_guard_changed(self):
        o=original();o["caller_level_timeout_implemented_in_original"]=True
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(original_value=o)

    def test_adt_order_shift_rejected(self):
        m=list(iomem());m[9],m[10]=m[10],m[9]
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(mem=tuple(m))

    def test_real_root_range_corrupt_rejected(self):
        m=list(iomem());m[9]=(0x600000000,0x7000)
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(mem=tuple(m))

    def test_missing_provider_range_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(mem=iomem()[:-1])

    def test_out_of_bounds_common_register(self):
        self.assertFalse(gate.EXPECTED_OFFSET > gate.EXPECTED_LENGTH-4)
        m=list(iomem());m[9]=(0x600000000,1)
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(mem=tuple(m))

    def test_boolean_resource_address_rejected(self):
        m=list(iomem());m[9]=(True,0x8000)
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(mem=tuple(m))

    def test_c_model_shared_offset_mutation_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model().replace(
                "#define N71_SHARED_ID1_OFFSET            0x2cU",
                "#define N71_SHARED_ID1_OFFSET            0x24U"))

    def test_c_model_phys_base_mutation_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model().replace(
                "UINT64_C(0x600000000)","UINT64_C(0x601000000)"))

    def test_c_model_bit_mask_mutation_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model().replace(
                "#define N71_SHARED_ID1_BIT               4U",
                "#define N71_SHARED_ID1_BIT               0U"))

    def test_c_model_poll_limit_mutation_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model().replace("4096U","0U"))

    def test_c_model_duplicate_constant_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model()+"\n#define N71_SHARED_ID1_BIT 4U\n")

    def test_c_model_accidental_live_mmio_write_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model()+"\nvoid leaked(void){writel(0,0);}\n")

    def test_c_model_accidental_network_function_rejected(self):
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=model()+"\nint bad(void){return socket(0,0,0);}\n")

    def test_model_hardware_authorization_tamper_rejected(self):
        tampered=model().replace(
            "int n71_port1_shared_snapshot_authorizes_hardware(void)\n{\n    return 0;\n}",
            "int n71_port1_shared_snapshot_authorizes_hardware(void)\n{\n    return 1;\n}")
        self.assertNotEqual(tampered,model())
        with self.assertRaises(gate.InvalidProvenance):
            self.verify(source=tampered)

    def test_private_original_disassembly_failure_propagates(self):
        with patch.object(gate.RMW,"audit",side_effect=ValueError("invalid source")):
            with self.assertRaises(ValueError):
                gate.verify_original_sources(b"x",b"y",b"z",model())

    def test_private_ios_provider_failure_propagates(self):
        with patch.object(gate.RMW,"audit",return_value=original()),\
             patch.object(gate.IOS,"compare_private_inputs",
                          side_effect=ValueError("invalid live provider")):
            with self.assertRaises(ValueError):
                gate.verify_original_sources(b"x",b"y",b"z",model())

    def test_private_file_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"original"
            p.write_bytes(b"SYNTHETIC")
            link=Path(t)/"symlink"
            link.symlink_to(p)
            with self.assertRaises(gate.InvalidProvenance):
                gate.private_file(link,2048)

    def test_private_file_input_limit_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"synth"
            p.write_bytes(b"SYNTHETIC"*20)
            with self.assertRaises(gate.InvalidProvenance):
                gate.private_file(p,10)

    def test_bad_private_cli_never_discloses_path_or_content(self):
        secret="SYNTHETIC_SUPER_SECRET_PRIVATE"
        with tempfile.TemporaryDirectory(prefix="n71-gate-private-") as t:
            private=Path(t)/(secret+".bin")
            private.write_bytes(secret.encode())
            proc=subprocess.run([sys.executable,str(TOOL),
                                 str(private),str(private),str(private)],
                                text=True,capture_output=True,timeout=20)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn("FAIL_CLOSED",proc.stderr)
            self.assertNotIn(secret,proc.stdout+proc.stderr)
            self.assertNotIn(str(private),proc.stdout+proc.stderr)

    def test_no_hardware_or_private_material_export_calls_in_gate(self):
        # Inspect executed AST calls, not quoted examples of forbidden APIs.
        import ast
        tree=ast.parse(TOOL.read_text())
        blocked={"ioremap","readl","writel","write_bytes","ioctl",
                 "socket","popen","Popen","run","system","execv"}
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):
                continue
            name=(node.func.id if isinstance(node.func,ast.Name) else
                  node.func.attr if isinstance(node.func,ast.Attribute) else
                  "<unknown>")
            self.assertNotIn(name,blocked)


if __name__=="__main__":
    unittest.main()
