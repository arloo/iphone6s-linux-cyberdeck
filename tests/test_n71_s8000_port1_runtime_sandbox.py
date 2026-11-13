#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static regressions for RAM-only reversible N71 S8000 DT overlays."""
from pathlib import Path
import re
import subprocess
import unittest

P=Path(__file__).resolve().parents[1]/'experimental/port1'
S=(P/'pcie-apple-s8000-port1-runtime-sandbox.c').read_text()
D=(P/'n71-s8000-port1-runtime-sandbox-overlay.dts').read_text()
H=(P/'n71-s8000-port1-runtime-sandbox-blob.h').read_text()
PD=(P/'n71-s8000-port1-powerstage-runtime-disabled.dts').read_text()
MAKE=(P/'Makefile').read_text()

class N71S8000RuntimeSandboxTests(unittest.TestCase):
    def test_out_of_tree_module_target(self):
        self.assertIn('obj-m += pcie-apple-s8000-port1-runtime-sandbox.o',MAKE)
        self.assertIn('module_exit(n71_runtime_sandbox_exit)',S)

    def test_live_machine_and_original_pcie_block_required(self):
        for marker in ('of_machine_is_compatible("apple,n71")',
                       'of_machine_is_compatible("apple,s8000")',
                       '"apple,s8000-pcie-research-blocked"',
                       '"research,hardware-activation-blocked"'):
            self.assertIn(marker,S)

    def test_sandbox_leaf_disabled_and_resource_free(self):
        self.assertIn('target-path = "/soc";',D)
        self.assertIn('n71-port1-runtime-sandbox {',D)
        self.assertIn('status = "disabled";',D)
        self.assertIn('research,observer-only;',D)
        body=D.split('n71-port1-runtime-sandbox {',1)[1].split('};',1)[0]
        for bad in ('reg =','power-domains =','clocks =','resets =',
                    'iommus =','interrupts =','gpios =', 'status = "okay"'):
            self.assertNotIn(bad,body)

    def test_blob_must_be_fdt_8_byte_aligned(self):
        self.assertIn('__attribute__((aligned(8)))',H)
        self.assertIn('n71_port1_sandbox_dtbo_len = 309;',H)
        self.assertIn('n71_port1_sandbox_dtbo_len != sizeof(n71_port1_sandbox_dtbo)',S)

    def test_header_exactly_matches_generated_synthetic_dts(self):
        compiled=subprocess.check_output(['dtc','-q','-@','-I','dts','-O','dtb',
                                          str(P/'n71-s8000-port1-runtime-sandbox-overlay.dts')])
        actual=bytes(int(h,16) for h in re.findall(r'0x([0-9a-f]{2})',
                        H.split('= {',1)[1].split('};',1)[0]))
        self.assertEqual(actual,compiled)

    def test_overlay_applied_and_reverted(self):
        self.assertIn('of_overlay_fdt_apply(',S)
        self.assertIn('of_overlay_remove(&n71_overlay_id)',S)
        self.assertIn('of_node_put(sandbox)',S)
        self.assertIn('n71_inert_sandbox_node_qualified(sandbox)',S)

    def test_no_hw_register_or_power_domain_code(self):
        impl=S.split('*/',1)[1]
        for token in ('ioremap(', 'readl(', 'writel(', 'memremap(',
                      'gpio_request(', 'gpiod_set_value(',
                      'dev_pm_domain_attach(', 'dev_pm_domain_attach_list(',
                      'pm_runtime_get(', 'pci_host_probe(', 'pci_scan_root_bus(',
                      'dma_map_', 'iommu_attach_device('):
            with self.subTest(token=token):self.assertNotIn(token,impl)

    def test_powerstage_overlay_remains_disabled_and_double_gated(self):
        self.assertIn('status = "disabled";',PD)
        self.assertNotIn('apple,explicit-supervised-power-test;',PD)
        self.assertIn('power-domain-names = "ref", "aux", "link1";',PD)
        self.assertIn('power-domains = <0x3a>, <0x3b>, <0x3c>;',PD)
        self.assertIn('"apple,n71-s8000-pcie-port1-powerstage"',PD)

    def test_samsung_only_resource_windows(self):
        for mmio in ('0x02000000', '0x02004000', '0x10000000'):
            self.assertIn(mmio,PD)
        self.assertIn('apple,port-index = <1>',PD)
        self.assertIn('apple,perst-pin = <161>',PD)
        self.assertIn('apple,clkreq-pin = <165>',PD)
        self.assertIn('apple,device-wake-pin = <73>',PD)

if __name__=='__main__': unittest.main()
