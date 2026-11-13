"""Original N71/S8000 port1 offline, non-activating source integration tests.

Only compiles a standalone *shadow* test (no MMIO, no phone). The actual
ARM64 kernel object is built separately on the owner's authorized Dell.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"experimental/port1/pcie-apple-s8000-port1-offline.c"
HARNESS=ROOT/"experimental/port1/n71_s8000_port1_offline_test.c"

class N71Port1OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=SOURCE.read_text()
        cls.harness=HARNESS.read_text()
    def test_no_physical_hardware_mmio_operations(self):
        for key in ("readl(", "writel(", "ioremap(", "pci_host_probe(",
                    "of_platform_populate(", "devm_platform_", "udelay(", "msleep("):
            with self.subTest(key=key):
                self.assertNotIn(key,self.code)
    def test_no_device_driver_registration(self):
        for key in ("platform_driver_register(", "module_platform_driver(",
                    "module_init(", "module_pci_driver(", "pci_register_driver("):
            self.assertNotIn(key,self.code)
    def test_dangerous_enable_is_hard_refused(self):
        self.assertRegex(self.code,r"int n71_s8000_port1_host_enable\(void\)\s*\{\s*return -EOPNOTSUPP;\s*\}")
    def test_verified_root_port1_offsets(self):
        for off in ("0x180","0x194","0x1a4","0x1ac"):
            self.assertIn(off,self.code)
    def test_status_shared_global_root_is_read_only(self):
        self.assertIn("N71_ROOT_GLOBAL_STATUS = 0x2c",self.code)
        self.assertIn("if (!step || !next || !step->write ||",self.code)
        self.assertNotIn("case N71_ROOT_GLOBAL_STATUS:",self.code)
    def test_source_refclk_perst_is_microseconds(self):
        self.assertIn("N71_REFCLK_PERST_SOURCE_DELAY_US = 100",self.code)
        self.assertIn("N71_ROOT_POLL_INTERVAL_US = 10",self.code)
    def test_bounded_timeout_no_unbounded_loop(self):
        self.assertIn("N71_P1_MAX_POLL_SAMPLES = 1000",self.code)
        self.assertIn("count > N71_P1_MAX_POLL_SAMPLES",self.code)
        self.assertIn("return -ETIMEDOUT;",self.code)
        self.assertNotRegex(self.code,r"while\s*\(\s*1\s*\)")
    def test_global_rmw_masks_must_match_original_source(self):
        for marker in ("step->mask == (1U << 8)", "step->mask == (1U << 20)",
                       "step->mask != 1U", "step->mask != 1U || step->value > 1U"):
            self.assertIn(marker,self.code)
    def test_all_steps_use_only_source_derived_registers(self):
        body=self.code.split("int n71_s8000_port1_plan_step(",1)[1].split(
            "int n71_s8000_port1_shadow_apply(",1)[0]
        for name in ("N71_ROOT_PORT1_ID2","N71_ROOT_PORT1_ID3",
                     "N71_ROOT_PORT1_ID4","N71_ROOT_PORT1_ID5"):
            self.assertIn(name,body)
        self.assertNotIn("N71_ROOT_GLOBAL_STATUS",body)
    def test_optional_id2_bit20_disabled_without_explicit_choice(self):
        self.assertIn("if (!enable_optional)",self.code)
        self.assertIn("return -EOPNOTSUPP;",self.code)
    def test_harness_mutations_and_vectors_remain(self):
        for marker in ("200000", "0xffffffffU",
                       "(1U<<8)|(1U<<20)", "samples[999]",
                       "N71_S8000_PORT1_PHYSICAL_MMIO_ACTIVATION_REFUSED_PASS"):
            self.assertIn(marker,self.harness)
    def test_compile_and_execute_native_synthetic_harness(self):
        cc=shutil.which("cc")
        if cc is None:self.skipTest("No native C compiler available")
        with tempfile.TemporaryDirectory(prefix="n71_offline_") as td:
            target=Path(td)/"shadow"
            cmd=[cc,"-std=c11","-O2","-Wall","-Wextra","-Werror",
                 str(HARNESS),"-o",str(target)]
            subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,
                           timeout=30)
            output=subprocess.run([str(target)],check=True,capture_output=True,
                                  text=True,timeout=15).stdout
        self.assertIn("N71_S8000_PORT1_OFFLINE_SHADOW_RMW_200000_VECTORS_PASS",output)
        self.assertIn("N71_S8000_PORT1_FINITE_POLL_FAIL_CLOSED_PASS",output)
        self.assertIn("N71_S8000_PORT1_PHYSICAL_MMIO_ACTIVATION_REFUSED_PASS",output)

if __name__=="__main__":unittest.main()
