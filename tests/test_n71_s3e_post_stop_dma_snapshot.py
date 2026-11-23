"""Offline contract checks for diagnostic-only S8000 post-stop snapshot."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "experimental/port0/n71_s3e_admin_identify_once.h").read_text()
CORE = (ROOT / "experimental/port0/n71_s3e_admin_once_core.h").read_text()

class PostStopSnapshotTests(unittest.TestCase):
    def test_snapshot_is_only_after_bus_master_disable(self):
        self.assertIn("if (r.master_off && !r.disable_rc)", SOURCE)
        gate=SOURCE.index("if (r.master_off && !r.disable_rc)")
        self.assertGreater(SOURCE.index("ADMIN_POST_DISABLE_HMB_DESCRIPTOR"), gate)
        self.assertGreater(SOURCE.index("ADMIN_POST_STOP_DMA_SNAPSHOT"), gate)

    def test_hmb_zero_and_queue_indicators_are_disjoint(self):
        self.assertIn("ready && !hmb_lo && !hmb_hi && !hmb_size", SOURCE)
        self.assertIn("unsigned int queues_zero=!(aqa|asq_lo|asq_hi|acq_lo|acq_hi)", SOURCE)
        self.assertIn("queues_owned,n71_admin_memory.dart_mapped", SOURCE)
        self.assertIn("dart_fault,nvmmu_fifo", SOURCE)

    def test_snapshot_does_not_authorize_release(self):
        start=SOURCE.index("/* Post-stop queue/translation snapshot only.")
        end=SOURCE.index("pr_info(\"n71-s3e-p0: ADMIN_STAGE", start)
        block=SOURCE[start:end]
        for forbidden in ("writel(", "writew(", "dma_unmap_", "free_page(",
                          "n71_admin_unprepare(", "n71_storage_admin_free(",
                          "n71_admin_dart_map(ctx,0)", "r->stopped=1"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, block)
        self.assertIn("if (rc==-3) return -3;", SOURCE)
        self.assertIn("r->stopped=shutdown_ok && disable_ok && r->master_off && r->post_disable_qualified;", CORE)
        self.assertIn("r->controller_stop_observed=r->shutdown_attempted==1", CORE)
        self.assertIn("r->shutdown_csts==9", CORE)
        self.assertIn("r->disable_csts==0 && r->master_off==1", CORE)
        self.assertIn("ADMIN_CONTROLLER_STOP_RO controller_stop_observed=%u", SOURCE)
        self.assertIn("dma_quiescence_proven=NO dma_release_authorized=NO", SOURCE)
        stop_obs=SOURCE.index("ADMIN_CONTROLLER_STOP_RO")
        self.assertGreater(stop_obs, SOURCE.index("ADMIN_SHUTDOWN_TRACE"))
        self.assertLess(stop_obs, SOURCE.index("ADMIN_POST_DISABLE_PREDICATES"))

if __name__ == "__main__":
    unittest.main()
