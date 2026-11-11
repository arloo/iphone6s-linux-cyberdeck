"""Synthetic-only N71 full offline Wi-Fi kernel build script safety tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FULL=ROOT/"scripts/build_n71_wifi_kernel_full_offline.sh"

class TestFullN71WiFiKernelOfflineBuild(unittest.TestCase):
    def invoke(self,*values):
        return subprocess.run(["bash",str(FULL),*map(str,values)],
                              capture_output=True,text=True,timeout=8)

    def test_bash_syntax(self):
        r=subprocess.run(["bash","-n",str(FULL)],capture_output=True)
        self.assertEqual(r.returncode,0)

    def test_requires_four_inputs(self):
        r=self.invoke()
        self.assertEqual(r.returncode,2)
        self.assertIn("Usage:",r.stderr)

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            r=self.invoke(root/"missing",root/"config",
                          root/"image",root/"out")
            self.assertNotEqual(r.returncode,0)
            self.assertFalse((root/"out").exists())

    def test_existing_destination_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"linux";source.mkdir()
            cfg=root/"cfg";cfg.write_text("synthetic")
            img=root/"img";img.write_text("synthetic")
            out=root/"existing";out.mkdir()
            (out/"sentinel").write_text("intact")
            r=self.invoke(source,cfg,img,out)
            self.assertEqual(r.returncode,4)
            self.assertEqual((out/"sentinel").read_text(),"intact")

    def test_symlinked_baseline_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"linux";source.mkdir()
            cfg=root/"cfg";cfg.write_text("synthetic")
            img=root/"img";img.write_text("synthetic")
            fake=root/"linked";fake.symlink_to(img)
            r=self.invoke(source,cfg,fake,root/"out")
            self.assertEqual(r.returncode,3)

    def test_output_under_source_prohibited(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"linux";source.mkdir()
            cfg=root/"cfg";cfg.write_text("synthetic")
            img=root/"img";img.write_text("synthetic")
            r=self.invoke(source,cfg,img,source/"not-built")
            self.assertEqual(r.returncode,5)

    def test_trusted_image_cannot_be_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"linux";source.mkdir()
            cfg=root/"cfg";cfg.write_text("synthetic")
            img=root/"img";img.write_text("synthetic")
            r=self.invoke(source,cfg,img,root)
            self.assertEqual(r.returncode,4)

    def test_reuses_isolated_object_builder(self):
        text=FULL.read_text()
        self.assertIn("build_n71_wifi_objects_offline.sh",text)

    def test_cross_compile_full_image_and_modules(self):
        text=FULL.read_text()
        for necessary in ("ARCH=arm64","CROSS_COMPILE=aarch64-linux-gnu-",
                          "Image modules","O=\"$OUT\""):
            self.assertIn(necessary,text)

    def test_refuses_alias_to_known_good_vmlinux_object(self):
        text=FULL.read_text()
        self.assertIn('"$OUT/vmlinux.o"',text)
        self.assertIn("cross-build output alias detected",text)

    def test_requires_final_signed_kernel_abi_gate(self):
        text=FULL.read_text()
        self.assertIn("n71_wifi_alternate_kernel_gate.py",text)
        self.assertIn('"$TRUSTED_IMAGE" "$CONFIG" "$OUT"',text)

    def test_not_bootable_and_no_proprietary_contents(self):
        text=FULL.read_text()
        for forbidden in ("flash", "insmod ", "modprobe ",
                          "pongo", "m1n1-linux", "scp ", "ssh ",
                          "/dev/mem","git push", "i2cset "):
            self.assertNotIn(forbidden,text)
        self.assertIn("NO_NEW_BOOTABLE_RAM_BUNDLE_OR_DEVICE_ACCESS",text)

if __name__=="__main__":
    unittest.main()
