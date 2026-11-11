"""Offline-only S8000 N71 BCM4350 ARM64 radio build safety tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
SCRIPT=REPO/"scripts/build_n71_wifi_objects_offline.sh"

def fake_linux_tree(base:Path):
    source=base/"linux"
    (source/"scripts").mkdir(parents=True)
    (source/"drivers/gpio").mkdir(parents=True)
    (source/"drivers/net/wireless/broadcom/brcm80211/brcmfmac").mkdir(parents=True)
    (source/"Makefile").write_text("all:\n\t@true\n")
    conf=source/"scripts/config"
    conf.write_text("#!/bin/sh\nexit 0\n")
    conf.chmod(0o700)
    (source/"drivers/gpio/gpio-apple-pmic.c").write_text("/* stub */")
    (source/"drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c").write_text(
        "/* stub */")
    cfg=base/"baseline.config"
    cfg.write_text("CONFIG_ARCH_APPLE=y\nCONFIG_MODULES=y\n"
                   "CONFIG_PCI=y\nCONFIG_APPLE_DART=y\n")
    return source,cfg

class TestN71OfflineRadioKernelBuild(unittest.TestCase):
    def run_script(self,*args):
        return subprocess.run(["bash",str(SCRIPT),*[str(a) for a in args]],
                              capture_output=True,text=True,timeout=8)

    def test_bash_syntax(self):
        self.assertEqual(subprocess.run(["bash","-n",str(SCRIPT)],
                         capture_output=True).returncode,0)

    def test_requires_three_args(self):
        r=self.run_script()
        self.assertEqual(r.returncode,2)
        self.assertIn("Usage:",r.stderr)

    def test_nonexistent_source_fails_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            dest=root/"must-not-exist"
            result=self.run_script(root/"does-not-exist",root/"base",dest)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(dest.exists())

    def test_invalid_source_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            src=root/"linux";src.mkdir()
            cfg=root/"cfg";cfg.write_text("CONFIG_ARCH_APPLE=y\n")
            dest=root/"no-build"
            r=self.run_script(src,cfg,dest)
            self.assertEqual(r.returncode,3)
            self.assertFalse(dest.exists())

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,cfg=fake_linux_tree(root)
            dest=root/"existing";dest.mkdir()
            (dest/"sentinel").write_text("unchanged")
            r=self.run_script(src,cfg,dest)
            self.assertEqual(r.returncode,5)
            self.assertEqual((dest/"sentinel").read_text(),"unchanged")

    def test_wrong_architecture_config_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,cfg=fake_linux_tree(root)
            cfg.write_text("CONFIG_ARCH_APPLE=y\nCONFIG_MODULES=y\nCONFIG_PCI=y\n")
            dest=root/"no-build"
            r=self.run_script(src,cfg,dest)
            self.assertEqual(r.returncode,6)
            self.assertFalse(dest.exists())

    def test_public_checkout_not_a_firmware_or_build_target(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,cfg=fake_linux_tree(root)
            r=self.run_script(src,cfg,REPO/"forbidden-build")
            self.assertEqual(r.returncode,4)
            self.assertFalse((REPO/"forbidden-build").exists())

    def test_kconfig_includes_required_wireless_menu_gate(self):
        text=SCRIPT.read_text()
        for expected in ("-e WIRELESS","-e WLAN","-e NETDEVICES",
                         "-m CFG80211","-m BRCMFMAC",
                         "-e BRCMFMAC_PCIE"):
            self.assertIn(expected,text)

    def test_no_unrelated_radio_bus(self):
        text=SCRIPT.read_text()
        self.assertIn("-d BRCMFMAC_SDIO",text)
        self.assertIn("-d BRCMFMAC_USB",text)

    def test_isolated_build_and_cross_compile(self):
        text=SCRIPT.read_text()
        for required in ("olddefconfig","ARCH=arm64",
                         "CROSS_COMPILE=aarch64-linux-gnu-",
                         "AArch64", "O=\"$OUT\"", "prepare"):
            self.assertIn(required,text)

    def test_elf_architecture_check_is_locale_independent(self):
        self.assertIn('LC_ALL=C aarch64-linux-gnu-readelf -h', SCRIPT.read_text())

    def test_all_four_objects_required(self):
        text=SCRIPT.read_text()
        for obj in ("drivers/gpio/gpio-apple-pmic.o",
                    "net/wireless/cfg80211.o",
                    "drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.o",
                    "drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.o"):
            self.assertIn(obj,text)

    def test_no_device_access_or_runtime_driver_install(self):
        text=SCRIPT.read_text()
        for forbidden in ("insmod ","modprobe ","rmmod ","ioremap(",
                          "/dev/mem", "/dev/i2c-", "flash_", "dd if=",
                          "git push", "rsync ", "scp "):
            self.assertNotIn(forbidden,text)

if __name__=="__main__":
    unittest.main()
