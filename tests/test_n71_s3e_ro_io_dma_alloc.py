# SPDX-License-Identifier: MIT
"""Owner-only N71 real-kernel I/O DMA allocation safety contracts.

Unlike the existing host-native L2 staging test, the allocation functions
call Linux __get_free_page, dma_map_single, dma_unmap_single and free_page.
The proof that these compile is the isolated ARM64 kernel-module build;
these offline tests enforce fail-closed structure, explicit opt-in and
physical-ownership/epoch boundaries without loading the phone module.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental/port0"
SOURCE = (PORT0 / "n71_s3e_ro_io_dma_alloc.h").read_text()
DRIVER = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
PILOT = (PORT0 / "n71_s3e_p0_asserted_reset_rootstart.c").read_text()
DART = (PORT0 / "n71_s3e_ro_io_dart_map.h").read_text()


class PhysicalIOMemoryOwnershipTests(unittest.TestCase):
    def test_actual_kernel_dma_apis_present_and_four_16k_pages(self):
        self.assertIn("N71_RO_IO_DMA_PAGES 4U", SOURCE)
        self.assertIn("frames.read_sgl_pa = n71_ro_io_dma_memory.dma[3]", SOURCE)
        self.assertIn("PAGE_SIZE != SZ_16K", SOURCE)
        self.assertIn("__get_free_page(GFP_KERNEL)", SOURCE)
        self.assertIn("pa = virt_to_phys(n71_ro_io_dma_memory.page[i])", SOURCE)
        self.assertIn("dma_map_single(dev,", SOURCE)
        self.assertIn("PAGE_SIZE, DMA_BIDIRECTIONAL", SOURCE)
        self.assertIn("dma_mapping_error(dev,", SOURCE)
        self.assertIn("n71_ro_io_dma_memory.dma[i] != pa", SOURCE)
        self.assertIn("n71_s3e_ro_verify_ownership(&frames, foreign, foreign_count)", SOURCE)
        self.assertIn("n71_s3e_ro_verify_queue_iova(&layout)", SOURCE)

    def test_excludes_all_physically_preexisting_owners_before_zero(self):
        self.assertIn("m->inherited_nvmmu_pa[i]", SOURCE)
        self.assertIn("m->inherited_dart_pa[i]", SOURCE)
        self.assertIn("n71_hmb_memory.inherited_pa", SOURCE)
        self.assertIn("n71_hmb_memory.dma", SOURCE)
        self.assertIn("n71_nvmmu_memory.dma[i]", SOURCE)
        self.assertIn("n71_tables.dma[i]", SOURCE)
        self.assertIn("n71_admin_memory.dma[i]", SOURCE)
        self.assertIn("if (i >= 2)", SOURCE)  # admin[0]/[1] are already-owned frames
        self.assertIn("pa < admin_pa + PAGE_SIZE && admin_pa < pa + PAGE_SIZE", SOURCE)
        alloc = SOURCE[SOURCE.index("static int __maybe_unused n71_ro_io_dma_alloc_pre_epoch"):]
        self.assertLess(alloc.index("n71_ro_io_dma_claim_valid(pa, foreign, foreign_count, i)"),
                        alloc.index("memset(n71_ro_io_dma_memory.page[i], 0, PAGE_SIZE)"))
        self.assertLess(alloc.index("n71_ro_io_dma_foreign_ranges(ctx, foreign, &foreign_count)"),
                        alloc.index("__get_free_page(GFP_KERNEL)"))
        self.assertLess(alloc.index("n71_ro_io_dma_claim_valid(pa, foreign, foreign_count, i)"),
                        alloc.index("dma_map_single(dev,"))

    def test_pre_bme_required_and_allocator_is_only_in_explicit_runtime(self):
        self.assertIn("READ_ONCE(n71_admin_dma_epoch_latched)", SOURCE)
        self.assertIn("n71_unreleased", SOURCE)
        self.assertIn("dev_is_dma_coherent(dev)", SOURCE)
        self.assertIn("(n71_storage_root_read(ctx, 4) & 0xffffU) != 2", SOURCE)
        self.assertIn("(n71_storage_endpoint_read(ctx, 4) & 0xffffU) != 2", SOURCE)
        self.assertIn("n71_admin_reg(0x14) || n71_admin_reg(0x1c)", SOURCE)
        self.assertIn("!n71_storage_hmb_owned_ready(ctx)", SOURCE)
        self.assertIn('#include "n71_s3e_ro_io_dma_alloc.h"', DRIVER)
        self.assertNotIn("n71_ro_io_dma_alloc_pre_epoch(", DRIVER)
        self.assertNotIn("n71_ro_io_dma_alloc_pre_epoch(", PILOT)
        self.assertNotIn("n71_ro_io_dma_alloc_pre_epoch(", DART)

    def test_pre_epoch_abort_is_the_only_unmap_or_free(self):
        release = SOURCE[SOURCE.index("static int __maybe_unused n71_ro_io_dma_release_pre_epoch"):
                         SOURCE.index("static int n71_ro_io_dma_foreign_ranges")]
        self.assertIn("if (READ_ONCE(n71_admin_dma_epoch_latched))", release)
        self.assertIn("n71_ro_io_dma_memory.quarantined = true;", release)
        self.assertIn("n71_unreleased = true;", release)
        self.assertIn("if (n71_ro_io_dma_memory.quarantined)", release)
        self.assertLess(release.index("READ_ONCE(n71_admin_dma_epoch_latched)"),
                        release.index("dma_unmap_single("))
        self.assertLess(release.index("n71_unreleased = true;"),
                        release.index("free_page("))
        self.assertIn("if (n71_ro_io_dma_release_pre_epoch()) return -3;", SOURCE)
        self.assertEqual(SOURCE.count("dma_unmap_single("), 1)
        self.assertEqual(SOURCE.count("free_page("), 2)  # allocation+release
        self.assertNotIn("writel(", SOURCE)
        self.assertNotIn("writew(", SOURCE)
        self.assertNotIn("pr_info(", SOURCE)
        self.assertNotIn("n71_admin_write(", SOURCE)

    def test_nvmmu_flatdma_read_tag_is_candidate_not_live_map(self):
        self.assertIn("N71_RO_READ_FLATDMA_TAG_CANDIDATE", SOURCE)
        self.assertIn("NOT an active DART", SOURCE)
        self.assertIn("only by the explicit queue trial", SOURCE)
        self.assertNotIn("n71_s3e_ro_stage_io_queue_l2(", SOURCE)
        self.assertNotIn("n71_s3e_ro_encode_one_sector(", SOURCE)
        self.assertNotIn("dma_sync_single_for_device(", SOURCE)

if __name__ == "__main__":
    unittest.main()
