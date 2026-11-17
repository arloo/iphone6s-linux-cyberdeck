"""Offline safety and persistence regression tests for N71 private USB file vault."""
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experimental/storage/n71_usb_file_vault.py"
spec = importlib.util.spec_from_file_location("n71_usb_file_vault", PATH)
vault = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vault)


class FileVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name) / "private-vault"
        self.current = self.base / "current"
        self.root_patch = patch.object(vault, "ROOT", self.base)
        self.current_patch = patch.object(vault, "CURRENT", self.current)
        self.root_patch.start()
        self.current_patch.start()
        vault.initialize()

    def tearDown(self):
        self.current_patch.stop()
        self.root_patch.stop()
        self.temp.cleanup()

    def test_private_categories_and_empty_manifest(self):
        self.assertEqual(len(vault.CATEGORIES), 6)
        self.assertEqual(vault.files_in(), ([], 0))
        self.assertEqual(self.base.stat().st_mode & 0o777, 0o700)

    def test_import_public_mode_source_to_private_vault(self):
        source = Path(self.temp.name) / "example-track.mp3"
        source.write_bytes(b"mocked-audio-fixture" * 6)
        source.chmod(0o644)
        target = vault.ingest(source, "Music")
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(vault.files_in()[1], source.stat().st_size)
        with self.assertRaises(FileExistsError):
            vault.ingest(source, "Music")

    def test_pack_roundtrip_with_subdirectory(self):
        parent = self.current / "Projects" / "Lab"
        parent.mkdir(mode=0o700)
        file = parent / "test.txt"
        file.write_text("HELLO ARM64")
        file.chmod(0o600)
        archive, total = vault.pack_current()
        try:
            self.assertEqual(total, 11)
            self.assertEqual(vault.validate_archive(archive)[0], 1)
            with tarfile.open(archive, "r:gz") as tar:
                self.assertEqual(tar.extractfile("Projects/Lab/test.txt").read(), b"HELLO ARM64")
        finally:
            archive.unlink()

    def test_bad_archive_traversal_is_rejected(self):
        archive = Path(self.temp.name) / "malicious.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            obj = tarfile.TarInfo("Music/../../secret")
            obj.size = 4
            tar.addfile(obj, io.BytesIO(b"EVIL"))
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            vault.validate_archive(archive)

    def test_symlink_refused_in_archive_and_local_folder(self):
        source = Path(self.temp.name) / "secret.txt"
        source.write_text("private")
        (self.current / "Documents" / "external").symlink_to(source)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            vault.files_in()
        archive = Path(self.temp.name) / "symlink.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            obj = tarfile.TarInfo("Music/not-real")
            obj.type = tarfile.SYMTYPE
            obj.linkname = "/etc/passwd"
            tar.addfile(obj)
        with self.assertRaisesRegex(ValueError, "symlink"):
            vault.validate_archive(archive)

    def test_oversized_file_rejected(self):
        source = Path(self.temp.name) / "too-big.bin"
        with source.open("wb") as output:
            output.truncate(vault.MAX_FILE + 1)
        with self.assertRaisesRegex(ValueError, "too large"):
            vault.ingest(source, "Documents")

    def test_device_source_and_privacy_contract(self):
        source = PATH.read_text()
        self.assertIn("/data", source)
        self.assertIn("ssh_args", source)
        self.assertIn("client-config-PRIVATE.json", source)
        self.assertNotIn("sudo mkfs", source)
        self.assertNotIn("/dev/nvme0n1", source)
        self.assertIn("phone_NAND=no", source)


if __name__ == "__main__":
    unittest.main()
