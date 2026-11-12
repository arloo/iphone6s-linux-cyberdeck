"""Adversarial tests: live-port1 metadata collector must fail closed."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import struct
import sys
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_usb_port1_descriptor_only_collect.py"
spec=importlib.util.spec_from_file_location("n71_port1_only_collector",TOOL)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

REGS=((0x602000000,0x4000),(0x602004000,0x4000),(0x602008000,0x4000))
BASE={
 "OF_NODE":"YES","COMPAT":"apple,s8000-pcie-research-blocked",
 "STATUS":"okay","REG_NAMES":"port1-reg-a port1-reg-b dart1-reg",
 "REG_HEX":"".join(struct.pack(">QQ",*x).hex() for x in REGS),
 "HW_BLOCK_FLAG":"YES","PLATFORM_DEVICE":"YES","DRIVER_BOUND":"NO",
 "PLATFORM_MATCHES":"1","PCI_DEVICES":"0","IOMMU_GROUPS":"0",
 "WLAN_NETIF":"0","TOUCH_PROTOCOL_READY":"YES",
}

def synth(overrides=None,*,prompts=1,extra_lines=(),end=True):
 d=dict(BASE)
 d.update(overrides or {})
 lines=["__N71_PORT1_DESCRIPTOR_BEGIN__"]
 lines.extend(extra_lines)
 lines.extend(("~ # "*prompts)+f"N71_PORT1_META_{key}={val}" for key,val in d.items())
 if end:lines.append("__N71_PORT1_DESCRIPTOR_END__")
 return ("\r\n".join(lines)+"\r\n").encode()

class TestN71Port1PhysicalCollector(unittest.TestCase):
 def test_original_safe_descriptor_pass(self):
  self.assertEqual(M.validate_readonly_console(synth()),BASE)

 def test_multiple_prompts_from_busybox_shell_pass(self):
  self.assertEqual(M.validate_readonly_console(synth(prompts=4)),BASE)

 def test_harmless_non_allowlisted_console_bytes_not_exposed(self):
  t=M.validate_readonly_console(synth(extra_lines=("PRIVATE_IDENTIFIER_SAMPLE",
      "N71_PORT1_META_UNKNOWN=personal-information")))
  self.assertEqual(t,BASE)
  self.assertNotIn("UNKNOWN",t)

 def test_driver_bound_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"DRIVER_BOUND":"YES"}))

 def test_missing_hardware_block_flag_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"HW_BLOCK_FLAG":"NO"}))

 def test_pcie_endpoint_must_remain_absent(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"PCI_DEVICES":"1"}))

 def test_iommu_group_must_remain_absent(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"IOMMU_GROUPS":"1"}))

 def test_wlan_interface_must_remain_absent_at_this_stage(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"WLAN_NETIF":"1"}))

 def test_no_touch_protocol_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"TOUCH_PROTOCOL_READY":"NO"}))

 def test_wrong_platform_count_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"PLATFORM_MATCHES":"2"}))

 def test_wrong_firmware_binding_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"COMPAT":"apple,pcie"}))

 def test_wrong_phy_status_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"STATUS":"disabled"}))

 def test_changed_dart1_register_rejected(self):
  bad=list(REGS);bad[-1]=(0x601008000,0x4000)
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"REG_HEX":"".join(struct.pack(">QQ",*x).hex() for x in bad)}))

 def test_swapped_port1_windows_rejected(self):
  bad=(REGS[1],REGS[0],REGS[2])
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"REG_HEX":"".join(struct.pack(">QQ",*x).hex() for x in bad)}))

 def test_malformed_reg_hex_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"REG_HEX":"0x602000000"}))

 def test_bad_reg_size_rejected(self):
  bad=(REGS[0],(REGS[1][0],0x8000),REGS[2])
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth({"REG_HEX":"".join(struct.pack(">QQ",*x).hex() for x in bad)}))

 def test_missing_field_rejected(self):
  d=synth().replace(b"N71_PORT1_META_OF_NODE=YES\r\n",b"")
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,d)

 def test_duplicate_field_rejected(self):
  d=synth().replace(b"N71_PORT1_META_OF_NODE=YES",b"N71_PORT1_META_OF_NODE=YES\r\nN71_PORT1_META_OF_NODE=YES")
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,d)

 def test_missing_final_marker_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth(end=False))

 def test_oversized_console_rejected(self):
  self.assertRaises(M.DescriptorNotProven,M.validate_readonly_console,
                    synth()+b"x"*70000)

 def test_no_side_effect_commands_in_live_collector(self):
  src=TOOL.read_text()
  assert "USB_SHELL=\"172.16.42.1\"" in src
  for forbidden in ("devmem","ioremap","modprobe","insmod","reboot",
                    "flash_erase","dd if=","wpa_supplicant","iw dev ",
                    "mkdir /sys","echo 1 >","setpci"):
   self.assertNotIn(forbidden,src)

if __name__=="__main__":
 unittest.main()
