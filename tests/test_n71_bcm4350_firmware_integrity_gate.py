"""Read-only N71 BCM4350 original/staged firmware integrity: synthetic tests."""
from pathlib import Path
import importlib.util
import shutil
import stat
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/n71_bcm4350_firmware_integrity_gate.py"
spec=importlib.util.spec_from_file_location("private_wifi_integrity_gate",P)
gate=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)

def fixture(root:Path):
    original=root/"original"
    for family in gate.STAGE.FAMILIES:
        d=original/family
        d.mkdir(parents=True)
        for name in gate.STAGE.COMPONENTS:
            (d/name).write_bytes(("MOCK-ONLY-"+family+name).encode())
        (d/"P-albarossa_M-BLMA_V-m__m-2.1.txt").write_text(
            "synthetic mock radio parameters only\n")
    staged=root/"private-staged"
    gate.STAGE.stage(original,staged)
    return original,staged

class TestBCM4350PrivateIntegrity(unittest.TestCase):
    def inspect(self,source,staged):
        return gate.inspect(source,staged)

    def rejects(self,source,staged):
        with self.assertRaises(gate.UnverifiedFirmware):
            self.inspect(source,staged)

    def test_synthetic_complete_separated_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            r=self.inspect(a,b)
            self.assertEqual(r["firmware_families_checked"],2)
            self.assertEqual(r["total_files_checked"],8)
            self.assertFalse(r["safe_to_auto_install"])
            self.assertFalse(r["brcmfmac_binary_compatibility_proven"])

    def test_changed_staged_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C2/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            p.write_bytes(b"staged-corrupted")
            self.rejects(a,b)

    def test_swapped_radio_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            x=b/"C2/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            y=b/"C5/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            one=x.read_bytes()
            x.write_bytes(y.read_bytes());y.write_bytes(one)
            self.rejects(a,b)

    def test_corrupted_clm_blob_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C5/brcm"/gate.STAGE.COMPONENTS["albarossa.clmb"]
            p.write_bytes(b"changed")
            self.rejects(a,b)

    def test_changed_original_module_profile_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C2/original-profiles/P-albarossa_M-BLMA_V-m__m-2.1.txt"
            p.write_text("other profile")
            self.rejects(a,b)

    def test_missing_clm_blob_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C5/brcm"/gate.STAGE.COMPONENTS["albarossa.clmb"]
            p.unlink()
            self.rejects(a,b)

    def test_missing_revision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            shutil.rmtree(b/"C5")
            self.rejects(a,b)

    def test_extra_revision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            (b/"C3").mkdir()
            self.rejects(a,b)

    def test_extra_unapproved_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            (b/"C2/brcm/extra.bin").write_text("reject")
            self.rejects(a,b)

    def test_symlinked_staged_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C2/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            p.unlink();p.symlink_to("/etc/hosts")
            self.rejects(a,b)

    def test_world_readable_staged_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            p=b/"C2/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            p.chmod(0o644)
            self.rejects(a,b)

    def test_two_revisions_with_identical_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            other=a/"C-4350__s-C5/albarossa.trx"
            same=a/"C-4350__s-C2/albarossa.trx"
            other.write_bytes(same.read_bytes())
            dst=b/"C5/brcm"/gate.STAGE.COMPONENTS["albarossa.trx"]
            dst.write_bytes(same.read_bytes())
            self.rejects(a,b)

    def test_private_git_checkout_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=fixture(Path(tmp))
            with self.assertRaises(gate.UnverifiedFirmware):
                self.inspect(a,ROOT)

    def test_no_network_or_hardware_writer(self):
        text=P.read_text()
        for forbidden in ("write_bytes(","shutil.copy", "socket.",
                          "subprocess.run(", "open('/dev/", "mmap(",
                          "ioremap(", "writel(", "readl(", "git push"):
            self.assertNotIn(forbidden,text)

    def test_output_never_claims_firmware_usable(self):
        s=P.read_text()
        self.assertIn("LINUX_BRCMFMAC_FIRMWARE_FORMAT_RUNTIME_COMPATIBILITY=UNVERIFIED",s)
        self.assertIn("ACTUAL_SILICON_REVISION_AND_BOARD_NVRAM=UNKNOWN",s)
        self.assertIn("NO_AUTO_SELECTION",s)

if __name__=="__main__":
    unittest.main()
