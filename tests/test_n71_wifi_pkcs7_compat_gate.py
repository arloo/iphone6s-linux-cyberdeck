"""Synthetic-only N71 ARM64 PKCS7 signed-regdb symbol closure tests."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/n71_wifi_pkcs7_compat_gate.py"
spec=importlib.util.spec_from_file_location("n71_pkcs7_gate",TOOL)
g=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)

def samples():
    base={
        "CONFIG_SYSTEM_DATA_VERIFICATION":"n",
        "CONFIG_ASYMMETRIC_KEY_TYPE":"y",
        "CONFIG_PKCS7_MESSAGE_PARSER":"y",
    }
    cand={
        **base,
        "CONFIG_SYSTEM_DATA_VERIFICATION":"y",
        "CONFIG_CFG80211_REQUIRE_SIGNED_REGDB":"y",
        "CONFIG_CFG80211_USE_KERNEL_REGDB_KEYS":"y",
    }
    return base,cand,{"old_kernel_symbol"},{"verify_pkcs7_signature"},{"verify_pkcs7_signature"}

class TestN71WiFiRegulatoryPKCS7Gate(unittest.TestCase):
    def qualify(self,args):
        return g.qualify_config(*args)

    def reject(self,args):
        with self.assertRaises(g.UnsupportedRegulatoryKernel):
            self.qualify(args)

    def test_new_aarch64_candidate_closure(self):
        state=self.qualify(samples())
        self.assertTrue(state["candidate_source_object_exports_pkcs7"])
        self.assertFalse(state["new_core_linked_and_booted"])

    def test_old_core_must_not_be_modified(self):
        p=list(samples())
        p[0]["CONFIG_SYSTEM_DATA_VERIFICATION"]="y"
        self.reject(p)

    def test_candidate_must_contain_pkcs7(self):
        p=list(samples())
        p[1]["CONFIG_SYSTEM_DATA_VERIFICATION"]="n"
        self.reject(p)

    def test_required_signed_regulatory_policy(self):
        p=list(samples())
        p[1]["CONFIG_CFG80211_REQUIRE_SIGNED_REGDB"]="n"
        self.reject(p)

    def test_required_kernel_trusted_keys(self):
        p=list(samples())
        p[1]["CONFIG_CFG80211_USE_KERNEL_REGDB_KEYS"]="n"
        self.reject(p)

    def test_required_pkcs7_parser(self):
        p=list(samples())
        p[1]["CONFIG_PKCS7_MESSAGE_PARSER"]="n"
        self.reject(p)

    def test_required_asymmetric_keys(self):
        p=list(samples())
        p[1]["CONFIG_ASYMMETRIC_KEY_TYPE"]="n"
        self.reject(p)

    def test_missing_export_in_candidate_fails(self):
        p=list(samples())
        p[3].clear()
        self.reject(p)

    def test_cfg80211_missing_expected_dependency_fails(self):
        p=list(samples())
        p[4].clear()
        self.reject(p)

    def test_old_kernel_export_mismatch_fails(self):
        p=list(samples())
        p[2].add("verify_pkcs7_signature")
        self.reject(p)

    def test_no_live_hardware_or_unsafe_module_link(self):
        s=TOOL.read_text()
        for dangerous in ("modprobe ", "insmod ", "git push", "/dev/mem",
                          "subprocess.run(", "write_bytes(", "ioremap(",
                          "writel(", "mmap(", "ssh ","socket."):
            self.assertNotIn(dangerous,s)

    def test_result_explicitly_not_a_new_boot_image(self):
        s=TOOL.read_text()
        self.assertIn("NEW_VMLINUX_LINKED_OR_BOOTED=NO",s)
        self.assertIn("NO_KERNEL_MODIFY_NO_MODULE_LOAD_NO_HARDWARE_ACCESS",s)

if __name__=="__main__":
    unittest.main()
