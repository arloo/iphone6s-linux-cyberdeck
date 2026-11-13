#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Public, fixture-free checks for S8000 N71 port1 descriptor-only kernel stage.
Hardware source data is pinned as non-private register extents and GPIO indices.
These tests are NOT a substitute for physical PCIe training, DMA or SID proof.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'experimental/port1'
C=(DIR/'pcie-apple-s8000-port1-preflight.c').read_text()
DTS=(DIR/'s8000-n71-port1-preflight.dts').read_text()
EXPECTED=[(0x600000000,0x8000), (0x602000000,0x4000),
          (0x602004000,0x4000), (0x610000000,0x1000000)]

def extract_dts_windows():
    m=re.search(r'\breg\s*=\s*(.*?);',DTS,re.S)
    if not m:raise AssertionError('missing DT resource windows')
    cells=[tuple(int(word,16) for word in line.split())
           for line in re.findall(r'<([^>]+)>',m.group(1))]
    if any(len(c)!=4 for c in cells):raise AssertionError('wrong DT cell width')
    return [((a<<32)|b,(c<<32)|d) for a,b,c,d in cells]

class N71S8000Port1PreflightTests(unittest.TestCase):
    def test_pin_model_matches_original_adt(self):
        self.assertIn('apple,perst-pin = <161>',DTS)
        self.assertIn('apple,clkreq-pin = <165>',DTS)
        self.assertIn('apple,device-wake-pin = <73>',DTS)
        self.assertNotIn('reset-gpios',DTS)
        self.assertNotIn('pinctrl-0',DTS)
        self.assertNotIn('GPIOD_OUT_',C)

    def test_only_port1_index(self):
        self.assertIn('apple,port-index = <1>',DTS)
        self.assertIn('id != N71_PORT1_INDEX',C)
        self.assertIn('#define N71_PORT1_INDEX 1U',C)

    def test_real_resource_extents(self):
        self.assertEqual(extract_dts_windows(),EXPECTED)
        self.assertEqual(len(EXPECTED),4)

    def test_all_resources_disjoint(self):
        for i,(start,size) in enumerate(EXPECTED):
            self.assertGreater(size,0)
            self.assertLessEqual(start+size,1<<64)
            for other_start,other_size in EXPECTED[i+1:]:
                self.assertTrue(start+size<=other_start or
                                other_start+other_size<=start)

    def test_global_config_never_relabelled_as_port_local(self):
        self.assertIn('config-shared',DTS)
        self.assertIn('root-common',DTS)
        self.assertIn('port1-control',DTS)
        self.assertIn('port1-aux',DTS)
        self.assertNotIn('port0-control',DTS)
        self.assertNotIn('port2-control',DTS)

    def test_exact_resource_validation_before_success(self):
        self.assertIn('platform_get_resource_byname',C)
        self.assertIn('res->start != w->start',C)
        self.assertIn('resource_size(res) != w->bytes',C)
        self.assertIn('return dev_err_probe',C)

    def test_no_pcie_activation_or_mmio(self):
        disallowed=['ioremap(', 'readl(', 'writel(', 'memremap(',
                    'pci_host_probe(', 'pci_scan_root_bus(',
                    'gpiod_get(', 'gpiod_set_value(', 'gpio_request(',
                    'request_irq(', 'dma_map_', 'iommu_attach_device(']
        code=C.split('*/',1)[1]
        for token in disallowed:
            with self.subTest(token=token):
                self.assertNotIn(token,code)

    def test_unique_optin_compatible_and_machine_id(self):
        match='apple,n71-s8000-pcie-port1-preflight'
        self.assertIn(match,C)
        self.assertIn(match,DTS)
        self.assertIn('of_machine_is_compatible("apple,n71")',C)
        self.assertIn('of_machine_is_compatible("apple,s8000")',C)
        self.assertIn('apple,observer-only',C)
        self.assertIn('apple,observer-only;',DTS)

    def test_real_wlan_gpio_not_storage_or_baseband(self):
        self.assertTrue({73,161,165}.isdisjoint({160,162,164,166}))

if __name__=='__main__':unittest.main()
