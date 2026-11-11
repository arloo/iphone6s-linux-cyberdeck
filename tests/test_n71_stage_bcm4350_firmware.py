"""Synthetic BCM4350 firmware staging tests. No Apple bits are embedded."""
from pathlib import Path
import importlib.util
import os
import stat
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_stage_bcm4350_firmware.py"
spec=importlib.util.spec_from_file_location("a9_wifi_stage",SCRIPT)
m=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

def fixtures(base:Path):
    original=base/"source"
    for family in m.FAMILIES:
        folder=original/family
        folder.mkdir(parents=True)
        for name in m.COMPONENTS:
            # Deterministic synthetic bytes only; not any Apple data.
            (folder/name).write_bytes(("synthetic-"+family+"-"+name).encode())
        for label in ("BLMA","STBL"):
            (folder/f"P-albarossa_M-{label}_V-m__m-2.1.txt").write_text(
                "test fixture only\n")
    return original

class TestN71WiFiPrivateFirmwareStaging(unittest.TestCase):
    def test_two_families_staged_separately(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td)
            src=fixtures(temp)
            dest=temp/"private-ready"
            self.assertEqual(m.stage(src,dest),{"C2":5,"C5":5})
            a=(dest/"C2"/"brcm"/"brcmfmac4350c2-pcie.apple,albarossa.bin")
            b=(dest/"C5"/"brcm"/"brcmfmac4350c2-pcie.apple,albarossa.bin")
            self.assertNotEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(stat.S_IMODE(a.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(b.stat().st_mode),0o600)

    def test_does_not_merge_profile_families(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp);dest=temp/"stage"
            m.stage(src,dest)
            for version in ("C2","C5"):
                self.assertEqual(len(list((dest/version/"original-profiles").iterdir())),2)

    def test_refuse_existing_destination(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp);dest=temp/"stage";dest.mkdir()
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.stage(src,dest)

    def test_missing_original_variant_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            import shutil
            shutil.rmtree(src/"C-4350__s-C5")
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_missing_clm_blob_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            (src/"C-4350__s-C5"/"albarossa.clmb").unlink()
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_missing_profiles_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            for p in (src/"C-4350__s-C2").glob("P-*"):
                p.unlink()
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_unknown_original_firmware_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            (src/"C-4350__s-C5"/"private-id.txt").write_text("block")
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_symlink_original_component_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            f=src/"C-4350__s-C2"/"albarossa.trx"
            f.unlink();f.symlink_to("/etc/hosts")
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_oversized_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            with (src/"C-4350__s-C5"/"albarossa.txcb").open("wb") as f:
                f.truncate(80_000)
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_no_output_into_public_repository(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.stage(src,ROOT/"never-stage-proprietary-files-here")

    def test_empty_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            (src/"C-4350__s-C5"/"albarossa.trx").write_bytes(b"")
            with self.assertRaises(m.UnsafeFirmwareStaging):
                m.inspect_private_source(src)

    def test_source_file_permissions_never_loosened(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);src=fixtures(temp)
            original=src/"C-4350__s-C5"/"albarossa.trx"
            original.chmod(0o400)
            m.stage(src,temp/"stage")
            self.assertEqual(stat.S_IMODE(original.stat().st_mode),0o400)

    def test_no_hardware_or_network_operations(self):
        contents=SCRIPT.read_text()
        for forbidden in (
            "socket.","subprocess.","requests.", "urllib.request",
            "open('/dev/","ioremap(", "writel(", "readl(", "insmod",
            "modprobe","git push", "print(content","print(firmware"):
            self.assertNotIn(forbidden,contents)

if __name__=="__main__":
    unittest.main()
