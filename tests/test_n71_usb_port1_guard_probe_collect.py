"""Fail-closed regression tests for the physical USB port1 guard collector."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_usb_port1_guard_probe_collect.py"
spec=importlib.util.spec_from_file_location("n71_phys_guard_collector",TOOL)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

def sample(change=None,prompts=2,include_end=True,extra=()):
    fields=dict(M.EXPECTED)
    fields.update(change or {})
    parts=["__N71_PORT1_GUARD_AUDIT_START__"]
    parts.extend(extra)
    parts.extend("~ # "*prompts+f"N71_GUARD_AUDIT_{key}={val}" for key,val in fields.items())
    if include_end:parts.append("__N71_PORT1_GUARD_AUDIT_END__")
    return ("\r\n".join(parts)+"\r\n").encode()

class TestPhysicalN71GuardCollector(unittest.TestCase):
    def test_good_on_device_evidence(self):M.validate_console(sample())
    def test_double_prompt_accepted(self):M.validate_console(sample(prompts=4))
    def test_unrelated_sensitive_line_not_displayed(self):
        M.validate_console(sample(extra=("SECRET_FAKE_INPUT_NEVER_PRINTED",)))
    def test_missing_loaded_module_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"MODULE_SYS":"NO"}))
    def test_missing_proc_module_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"MODULE_PROC":"NO"}))
    def test_bound_hardware_driver_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"DRIVER_BOUND":"YES"}))
    def test_missing_blocked_probe_log_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"REFUSAL_DMESG":"NO"}))
    def test_missing_block_flag_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"HW_BLOCK_FLAG":"NO"}))
    def test_real_pci_endpoint_rejected_for_inert_probe(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"PCI_COUNT":"1"}))
    def test_iommu_group_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"IOMMU_COUNT":"1"}))
    def test_native_wlan_rejected_for_inert_probe(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"WLAN_COUNT":"1"}))
    def test_failed_touch_protocol_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"TOUCH_READY":"NO"}))
    def test_missing_usb_gadget_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample({"USB_NET":"NO"}))
    def test_missing_end_marker_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample(include_end=False))
    def test_duplicate_metric_rejected(self):
        data=sample(extra=("N71_GUARD_AUDIT_MODULE_SYS=YES",))
        with self.assertRaises(M.PhysicalProofUnavailable):M.validate_console(data)
    def test_missing_metric_rejected(self):
        data=sample().replace(b"N71_GUARD_AUDIT_MODULE_SYS=YES\r\n",b"")
        with self.assertRaises(M.PhysicalProofUnavailable):M.validate_console(data)
    def test_large_raw_console_rejected(self):
        with self.assertRaises(M.PhysicalProofUnavailable):
            M.validate_console(sample()+b"a"*65536)
    def test_collector_has_no_active_kernel_operation(self):
        commands="\n".join(M.COMMANDS)
        for forbidden in ("insmod","rmmod","modprobe","devmem","ioremap",
                          "setpci","wpa_supplicant","iw dev ","reboot",
                          "poweroff","dd if=","flash_erase","sync; echo 1"):
            self.assertNotIn(forbidden,commands)
        self.assertIn("N71_PHYSICAL_PCIE_LINK_DART_DMA_REQUESTER_SID_NATIVE_WIFI_PROVEN=NO",TOOL.read_text())

if __name__=="__main__":unittest.main()
