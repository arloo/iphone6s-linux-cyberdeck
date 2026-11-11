"""A9 Wi-Fi alternate kernel image/package gate: synthetic safety tests only."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_wifi_alternate_kernel_gate.py"
sp=importlib.util.spec_from_file_location("n71_alt_wifi",SCRIPT)
g=importlib.util.module_from_spec(sp)
assert sp and sp.loader
sp.loader.exec_module(g)

class TestN71AlternateLinuxKernelGate(unittest.TestCase):
    def test_known_good_baseline_gate_is_reused(self):
        s=SCRIPT.read_text()
        self.assertIn("CFG.verify(",s)
        self.assertIn("n71_wifi_kernel_baseline_gate.py",s)

    def test_four_components_included(self):
        self.assertEqual(len(g.MODULE_PATHS),4)
        for wanted in ("cfg80211.ko","brcmutil.ko",
                       "brcmfmac.ko","gpio-apple-pmic.ko"):
            self.assertTrue(any(p.endswith(wanted) for p in g.MODULE_PATHS))

    def test_elf_metadata_inspection_forces_c_locale(self):
        self.assertIn('"LC_ALL":"C"', SCRIPT.read_text())

    def test_correct_original_release_header(self):
        self.assertEqual(g.verify_version_header(
            '#define UTS_RELEASE "7.3.0-rc1-g68aadac820d0-dirty"\n'),
            "7.3.0-rc1-g68aadac820d0-dirty")

    def test_reject_unterminated_release(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.verify_version_header("#define UTS_RELEASE BAD\n")

    def test_reject_injected_release_string(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.verify_version_header('#define UTS_RELEASE "build;whoami"\n')

    def test_reject_differently_versioned_module(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.inspect_module("7.2.0 SMP preempt aarch64",
                             "7.3.0 SMP preempt",
                             "Type: REL\nMachine: AArch64")

    def test_reject_x86_module_even_correct_version(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.inspect_module("7.3.0 SMP preempt aarch64",
                             "7.3.0","Type: REL\nMachine: Advanced Micro Devices")

    def test_reject_executable_instead_of_module(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.inspect_module("7.3.0 SMP preempt aarch64",
                             "7.3.0","Type: EXEC\nMachine: AArch64")

    def test_reject_non_arm_vermagic(self):
        with self.assertRaises(g.UnqualifiedAlternativeKernel):
            g.inspect_module("7.3.0 SMP preempt x86_64",
                             "7.3.0","Type: REL\nMachine: AArch64")

    def test_accept_synthetic_compatible_module_metadata(self):
        g.inspect_module("7.3.0-rc1 SMP preempt aarch64",
                         "7.3.0-rc1","Type: REL\nMachine: AArch64")

    def test_no_identical_known_good_kernel_accepted(self):
        s=SCRIPT.read_text()
        self.assertIn("file_sha256(trusted_image)!=file_sha256(img)",s)

    def test_no_s8000_guard_autoenabled(self):
        s=(ROOT/"tools/n71_wifi_kernel_baseline_gate.py").read_text()
        self.assertIn('new.get("CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD","n")=="n"',s)

    def test_boot_and_wifi_not_claimed(self):
        text=SCRIPT.read_text()
        for needed in ("ALTERNATIVE_KERNEL_BOOTED=NO",
                       "PCIe_S8000_DART1_DMA_WIFI_HARDWARE_VERIFIED=NO",
                       "NO_BOOTABLE_RAM_BUNDLE_ASSEMBLED_NO_DEVICE_ACCESS"):
            self.assertIn(needed,text)

    def test_missing_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            old=root/"trusted"
            old.write_bytes(b"not an image")
            cfg=root/"base.config"
            cfg.write_text("not a valid config")
            result=subprocess.run([sys.executable,str(SCRIPT),
                                   str(old),str(cfg),str(root/"missing")],
                                  text=True,capture_output=True,timeout=8)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("FAIL_CLOSED",result.stderr)

    def test_no_device_write_link_or_remote_commands(self):
        text=SCRIPT.read_text()
        for forbidden in ("write_bytes(","mmap(", "ioremap(", "writel(",
                          "insmod ", "modprobe ", "ssh ", "scp ",
                          "/dev/mem","git push", "subprocess.run("):
            self.assertNotIn(forbidden,text)

if __name__=="__main__":
    unittest.main()
