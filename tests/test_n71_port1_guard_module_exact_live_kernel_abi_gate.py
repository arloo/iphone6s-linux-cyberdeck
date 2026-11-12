"""Strict synthetic regression: N71 live-kernel guard-module ABI audit."""
from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_port1_guard_module_exact_live_kernel_abi_gate.py"
sp=importlib.util.spec_from_file_location("n71_guard_abi_gate",TOOL)
assert sp and sp.loader
G=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=G
sp.loader.exec_module(G)

EXPORTED_SAMPLE="\n".join(f"ffffffff00000000 D __ksymtab_{x}" for x in sorted(G.ALLOWED_IMPORTS))
IMPORT_SAMPLE="\n".join(f"                 U {x}" for x in sorted(G.ALLOWED_IMPORTS))
GOOD_SOURCE="""
static bool apple_s8000_regions_overlap() { return false; }
static int apple_s8000_guard_probe(struct platform_device *pdev) {
  if (!of_machine_is_compatible("apple,n71")) return -ENODEV;
  if (!of_property_read_bool(pdev->dev.of_node,"research,hardware-activation-blocked"))
    return -EINVAL;
  platform_get_resource_byname(pdev, IORESOURCE_MEM, "port1-reg-a");
  return -EOPNOTSUPP;
}
static const char *compatible="apple,s8000-pcie-research-blocked";
static const char *port="research,pcie-port-index";
static const char *mapper="research,dart1-mapper-index";
static const unsigned long long windows[]={
 0x602000000ULL,0x602004000ULL,0x602008000ULL
};
"""

class TestS8000KernelExactGuardABI(unittest.TestCase):
 def test_exact_imports_pass(self):
  imports=G.parse_imports_nm(IMPORT_SAMPLE)
  exports=G.parse_kernel_export_symbols(EXPORTED_SAMPLE)
  self.assertEqual(imports,G.ALLOWED_IMPORTS)
  G.verify_imports(imports,exports)

 def test_missing_export_fails_closed(self):
  imports=G.parse_imports_nm(IMPORT_SAMPLE)
  export_names=set(G.ALLOWED_IMPORTS)-{"platform_get_resource"}
  with self.assertRaises(G.GuardABIUnproven):
   G.verify_imports(imports,export_names)

 def test_new_hardware_import_rejected_even_if_exported(self):
  imports=set(G.ALLOWED_IMPORTS)|{"ioremap"}
  with self.assertRaises(G.GuardABIUnproven):
   G.verify_imports(imports,imports)

 def test_missing_required_import_rejected(self):
  imports=set(G.ALLOWED_IMPORTS)-{"of_machine_compatible_match"}
  with self.assertRaises(G.GuardABIUnproven):
   G.verify_imports(imports,set(G.ALLOWED_IMPORTS))

 def test_clean_driver_source_pass(self):
  G.source_guard_gate(GOOD_SOURCE)

 def test_forbid_mmio_function_call(self):
  for name in ("readl","writel","ioremap","devm_ioremap_resource",
               "of_iomap","pci_host_probe"):
   with self.subTest(danger=name):
    with self.assertRaises(G.GuardABIUnproven):
     G.source_guard_gate(GOOD_SOURCE+"\nvoid x(void){ "+name+"(x); }")

 def test_forbid_dma_clock_reset_function_call(self):
  for name in ("dma_map_single","iommu_map","reset_control_deassert",
               "clk_prepare_enable","regulator_enable","pci_scan_root_bus"):
   with self.subTest(danger=name):
    with self.assertRaises(G.GuardABIUnproven):
     G.source_guard_gate(GOOD_SOURCE+"\nvoid x(void){ "+name+"(x); }")

 def test_comments_cannot_trigger_false_positive(self):
  G.source_guard_gate(GOOD_SOURCE+"\n/* ioremap(x); writel(x); */\n")

 def test_missing_final_hardware_block_rejected(self):
  s=GOOD_SOURCE.replace("return -EOPNOTSUPP;","return 0;")
  with self.assertRaises(G.GuardABIUnproven):
   G.source_guard_gate(s)

 def test_missing_explicit_research_block_flag_rejected(self):
  s=GOOD_SOURCE.replace("research,hardware-activation-blocked","research,active")
  with self.assertRaises(G.GuardABIUnproven):
   G.source_guard_gate(s)

 def test_wrong_s8000_port1_window_rejected(self):
  s=GOOD_SOURCE.replace("0x602008000ULL","0x601008000ULL")
  with self.assertRaises(G.GuardABIUnproven):
   G.source_guard_gate(s)

 @staticmethod
 def fake_dtb(n):
  b=bytearray(n);b[:4]=b"\xd0\x0d\xfe\xed";struct.pack_into(">I",b,4,n)
  return bytes(b)

 def test_embedded_kernel_stream_exactly_extracted(self):
  target=b"synthetic-test-N71-ARM64-Image"; gz=gzip.compress(target)
  shell=b"0"*1_150_001
  blob=shell+self.fake_dtb(25000)+self.fake_dtb(27000)+gz+gzip.compress(b"synthetic initramfs")
  self.assertEqual(G.first_embedded_kernel(blob),target)

 def test_bogus_device_tree_rejected(self):
  with self.assertRaises(G.GuardABIUnproven):
   G.first_embedded_kernel(b"garbage")

 def test_truncated_second_dtb_rejected(self):
  data=b"0"*1_150_001+self.fake_dtb(25000)+b"not an FDT"
  with self.assertRaises(G.GuardABIUnproven):
   G.first_embedded_kernel(data)

 def test_raw_user_binary_never_printed_by_gate(self):
  source=TOOL.read_text()
  self.assertNotIn("print(modinfo)",source)
  self.assertNotIn("print(vmlinux)",source)
  self.assertNotIn("print(boot)",source)
  self.assertIn("N71_GUARD_RUN_ON_REAL_IPHONE_YET=NO",source)
  self.assertIn("N71_PCIE_DART1_REAL_DMA_REQUESTER_SID_STILL_UNPROVEN=YES",source)

if __name__=="__main__":
 unittest.main()
