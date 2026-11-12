"""Offline synthetic N71 S8000 PCIe original/live tunable staging tests.

Never uses or publishes original Apple tunable bytes, private calibration,
Apple kernelcache, phone identifiers or Wi-Fi credentials.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import os
import plistlib
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_s8000_private_pcie_tunable_stage_gate.py"
SPEC=importlib.util.spec_from_file_location("n71_tunables_stager",TOOL)
assert SPEC and SPEC.loader
gate=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

FIX=ROOT/"tests/test_n71_s8000_adt_window_gate.py"
FIXSPEC=importlib.util.spec_from_file_location("n71_synth_reg",FIX)
assert FIXSPEC and FIXSPEC.loader
fixtures=importlib.util.module_from_spec(FIXSPEC)
FIXSPEC.loader.exec_module(fixtures)

def pack_records(count,offset=0x100):
    return b"".join(struct.pack("<IIQQ",offset+4*i,4,0xff,0x52)
                    for i in range(count))

def four():
    return {name:pack_records(count)
            for name,(_,count,_) in gate.PROPS.items()}

def fake_plists(records):
    root={"IORegistry":{"IOPCIConfigured":True,
          **{key:records[key] for key,(path,_,_) in gate.PROPS.items()
             if path==gate.ADT.HOST}}}
    port={"IORegistry":{"IOPCIConfigured":True,"IOPCIResourced":True,
          **{key:records[key] for key,(path,_,_) in gate.PROPS.items()
             if path!=gate.ADT.HOST}}}
    return (plistlib.dumps(root),plistlib.dumps(port))

class TestN71OriginalLiveTunables(unittest.TestCase):
    def test_original_24_byte_candidate_layout(self):
        self.assertEqual(gate.RECORD.size,24)

    def test_pinned_original_arm64_semantics_instruction_model(self):
        source=bytearray(gate.ORIGINAL_EMBEDDED_LENGTH)
        for offset,insn in gate.ORIGINAL_TUNABLE_INSTRUCTIONS.items():
            struct.pack_into("<I",source,offset,insn)
        gate.verify_original_tunable_instruction_words(source)
        for offset in gate.ORIGINAL_TUNABLE_INSTRUCTIONS:
            with self.subTest(instruction_offset=offset):
                altered=bytearray(source)
                altered[offset]^=0x01
                with self.assertRaises(gate.RejectedTunables):
                    gate.verify_original_tunable_instruction_words(altered)

    def test_original_arm64_wrong_executable_size_rejected(self):
        with self.assertRaises(gate.RejectedTunables):
            gate.verify_original_tunable_instruction_words(b"synthetic")

    def test_four_expected_block_counts(self):
        self.assertEqual(gate.REAL_TOTAL,83)
        self.assertEqual(
            [gate.PROPS[x][1] for x in gate.PROPS],[34,41,6,2])

    def test_synthetic_real_24byte_records(self):
        block=gate.decode_record_block(pack_records(6),6,0x4000)
        self.assertEqual(len(block),6)
        self.assertEqual(block[0]["offset"],0x100)
        self.assertEqual(block[-1]["width"],4)
        self.assertEqual(block[0]["candidate_value"],0x52)

    def test_record_bad_width(self):
        data=struct.pack("<IIQQ",0x10,8,0xff,0x10)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_bad_alignment(self):
        data=struct.pack("<IIQQ",0x11,4,0xff,0x10)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_out_of_bounds(self):
        data=struct.pack("<IIQQ",0x4000,4,0xff,0x10)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_high_mask_not_allowed(self):
        data=struct.pack("<IIQQ",0x10,4,0x1000000ff,0x10)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_high_value_not_allowed(self):
        data=struct.pack("<IIQQ",0x10,4,0xffffffffffffffff,0x100000010)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_value_outside_mask(self):
        data=struct.pack("<IIQQ",0x10,4,0x1,0x2)
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(data,1,0x4000)

    def test_record_wrong_length(self):
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(pack_records(2),3,0x4000)

    def test_record_missing(self):
        with self.assertRaises(gate.RejectedTunables):
            gate.decode_record_block(b"",1,0x4000)

    def test_runtime_plists_type_and_presence(self):
        f=four();r,p=fake_plists(f)
        self.assertEqual(gate.captured_ios_tunable_blobs(r,p),f)

    def test_runtime_plist_misconfigured_rejected(self):
        f=four();r,p=fake_plists(f)
        obj=plistlib.loads(p);obj["IORegistry"]["IOPCIResourced"]=False
        with self.assertRaises(gate.RejectedTunables):
            gate.captured_ios_tunable_blobs(r,plistlib.dumps(obj))

    def test_runtime_plist_missing_property_rejected(self):
        f=four();r,p=fake_plists(f)
        obj=plistlib.loads(p)
        obj["IORegistry"].pop("pcie-rc-tunables")
        with self.assertRaises(gate.RejectedTunables):
            gate.captured_ios_tunable_blobs(r,plistlib.dumps(obj))

    def test_corrupt_ios_plist_rejected(self):
        with self.assertRaises(gate.RejectedTunables):
            gate.captured_ios_tunable_blobs(b"wrong",b"wrong")

    def test_extra_adt_properties_opt_in(self):
        original=fixtures.node("wlan",
            [("private-calibration",b"SYNTHETIC_CALIBRATION")])
        seen={}
        gate.ADT.ADT.parse_node(original,0,"",visitor=lambda p,x:seen.update(x),
                                visit_all=True)
        self.assertNotIn("private-calibration",seen)
        gate.ADT.ADT.parse_node(original,0,"",visitor=lambda p,x:seen.update(x),
                visit_all=True,
                extra_props=frozenset({"private-calibration"}))
        self.assertEqual(seen["private-calibration"],b"SYNTHETIC_CALIBRATION")

    def test_extra_adt_default_display_never_prints_private(self):
        import contextlib
        import io
        data=fixtures.node("wlan",
            [("private-calibration",b"VERY_PRIVATE_TEST_STRING")])
        o=io.StringIO()
        with contextlib.redirect_stdout(o):
            gate.ADT.ADT.parse_node(data,0,"")
        self.assertNotIn("VERY_PRIVATE_TEST_STRING",o.getvalue())

    def test_all_original_and_ios_synthetic_blocks_reconcile(self):
        f=four()
        with patch.object(gate,"adt_tunable_blobs",return_value=f),\
             patch.object(gate,"captured_ios_tunable_blobs",return_value=f):
            groups=gate.corroborate(b"FAKE",b"FAKE",b"FAKE")
        self.assertEqual(sum(map(len,groups.values())),83)

    def test_changed_runtime_bytes_rejected(self):
        f=four();bad=dict(f);bad["pcie-rc-tunables"]=pack_records(2,0x160)
        with patch.object(gate,"adt_tunable_blobs",return_value=f),\
             patch.object(gate,"captured_ios_tunable_blobs",return_value=bad):
            with self.assertRaises(gate.RejectedTunables):
                gate.corroborate(b"FAKE",b"FAKE",b"FAKE")

    def test_shared_status_direct_write_fail_closed(self):
        f=four();f["apcie-common-tunables"]=(
            struct.pack("<IIQQ",0x2c,4,0xff,0x10)+f["apcie-common-tunables"][24:])
        with patch.object(gate,"adt_tunable_blobs",return_value=f),\
             patch.object(gate,"captured_ios_tunable_blobs",return_value=f):
            with self.assertRaises(gate.RejectedTunables):
                gate.corroborate(b"FAKE",b"FAKE",b"FAKE")

    def test_original_adt_bad_so_c_rejected(self):
        with self.assertRaises(gate.ADT.RejectedADT):
            gate.adt_tunable_blobs(fixtures.fixture(
                host_compat=("apcie,s8003",)))

    def test_original_adt_tunable_missing_rejected(self):
        with self.assertRaises(gate.RejectedTunables):
            gate.adt_tunable_blobs(fixtures.fixture())

    def test_original_private_file_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"owner-test";p.write_bytes(b"synthetic private input")
            q=Path(t)/"symlink";q.symlink_to(p)
            with self.assertRaises(gate.RejectedTunables):
                gate.read_private(q,1234)

    def test_private_manifest_requires_marked_locked_directory(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"private.json"
            with self.assertRaises(gate.RejectedTunables):
                gate.private_stage(path,{})

    def test_private_manifest_rejects_world_readable_parent(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);p.chmod(0o755)
            (p/gate.STAGE_MARKER).touch()
            with self.assertRaises(gate.RejectedTunables):
                gate.private_stage(p/"private.json",{})

    def test_private_manifest_staging_data_only(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);p.chmod(0o700)
            (p/gate.STAGE_MARKER).touch()
            groups={k:gate.decode_record_block(v,gate.PROPS[k][1],
                     gate.PROPS[k][2]) for k,v in four().items()}
            path=p/"owner-private.json"
            gate.private_stage(path,groups)
            obj=json.loads(path.read_text())
            self.assertEqual(sum(len(x) for x in obj["groups"].values()),83)
            self.assertFalse(obj["enable_register_writes"])
            self.assertFalse(obj["enable_dart1_dma"])
            self.assertFalse(obj["enable_pcie_port1_link"])
            self.assertTrue(obj["original_software_masked_rmw_statically_verified"])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            with self.assertRaises(gate.RejectedTunables):
                gate.private_stage(path,groups)

    def test_private_path_not_disclosed_in_invalid_cli(self):
        secret="SYNTHETIC_SECRET_UNKNOWN_DRIVER"
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/(secret+".plist");path.write_bytes(b"bad ADT input")
            done=subprocess.run([sys.executable,str(TOOL),
                    str(path),str(path),str(path),
                    "--original-kernelcache",str(path)],
                    capture_output=True,text=True,timeout=15)
            self.assertNotEqual(done.returncode,0)
            self.assertIn("FAIL_CLOSED",done.stderr)
            self.assertNotIn(secret,done.stderr+done.stdout)
            self.assertNotIn(str(path),done.stderr+done.stdout)

    def test_does_not_expose_hardware_register_or_network_calls(self):
        import ast
        src=TOOL.read_text()
        tree=ast.parse(src)
        blocked={"ioremap","readl","writel","mmap","ioctl","socket",
                 "system","Popen","run","execv","idevicediagnostics"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else (
                    node.func.attr if isinstance(node.func,ast.Attribute) else "")
                self.assertNotIn(name,blocked)

    def test_all_hardware_authorization_explicitly_denied(self):
        text=TOOL.read_text()
        self.assertIn("PCIE_AND_DART_HARDWARE_INITIALIZATION_ALLOWED=NO",text)
        self.assertIn('"enable_register_writes":False',text)
        self.assertIn('"enable_dart1_dma":False',text)
        self.assertIn('"enable_pcie_port1_link":False',text)

if __name__=="__main__":
    unittest.main()
