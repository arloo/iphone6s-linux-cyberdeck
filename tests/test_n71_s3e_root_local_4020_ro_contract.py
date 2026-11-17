# SPDX-License-Identifier: MIT
"""Offline source safety contract: S8000 shared root per-port reads."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'experimental/port0/n71_s3e_root_local_4020_ro.c'

class ReadOnlyRootPortControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=CODE.read_text()
    def test_unarmed_by_default(self):
        self.assertIn('static bool armed;',self.c)
        self.assertIn('if (!armed)',self.c)
    def test_board_pinned_n71_s8000(self):
        self.assertIn('of_machine_is_compatible("apple,n71")',self.c)
        self.assertIn('of_machine_is_compatible("apple,s8000")',self.c)
    def test_original_stock_root_resource(self):
        self.assertIn('0x600000000ULL',self.c)
        self.assertIn('0x8000U',self.c)
    def test_port_control_registers_are_read_only(self):
        for off in ('0x4020','0x4060','0x40a0','0x40e0'):
            self.assertIn('readl((u8 __iomem *)root+'+off+')',self.c)
    def test_no_register_or_dma_writes(self):
        for operation in ('writel(', 'writeq(', 'regmap_write(',
                          'regmap_update_bits(', 'dma_map(', 'pci_write_config',
                          'gpiod_direction_output(', 'pm_runtime_get('):
            with self.subTest(op=operation):
                self.assertNotIn(operation,self.c)
    def test_real_wifi_reference_gate(self):
        self.assertIn('pci_get_device(0x14e4,0x43a3,NULL)',self.c)
        self.assertIn('id5p1!=1U',self.c)
    def test_port0_off_before_root_reads(self):
        self.assertIn('(p0&0xff)!=0',self.c)
        self.assertIn('ACTUAL(p1)!=15',self.c)
    def test_reference_and_aux_domains_checked(self):
        self.assertIn('ACTUAL(aux)!=15',self.c)
        self.assertIn('ACTUAL(ref)!=15',self.c)
    def test_never_create_block_device(self):
        for text in ('nvme_submit','blk_mq_alloc','blkdev_get'):
            self.assertNotIn(text,self.c)

if __name__=='__main__': unittest.main()
