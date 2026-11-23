# SPDX-License-Identifier: MIT
"""Host-only fault-injection tests for the S8000 S3E DMA retirement boundary.

No real device, MMIO, Apple firmware, or NAND content is accessed.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental" / "port0"
MAIN = (PORT0 / "n71_s3e_p0_asserted_reset_rootstart.c").read_text()
ADMIN = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
BOUNDARY = (PORT0 / "n71_s3e_dma_retirement_boundary.h").read_text()

HOST_C = r"""
#include <assert.h>
#include <stdio.h>
#include "n71_s3e_dma_retirement_boundary.h"

/* These are simulated software milestones, NOT hardware register states. */
enum stage {
    ALLOCATE_QUEUES, QUALIFY_BME, LATCH_BEFORE_BME, ROOT_BME,
    ENDPOINT_BME, CONTROLLER_ENABLE, QUEUE_DOORBELL, CQ_POLL,
    PAYLOAD_SYNC, REQUEST_SHUTDOWN, DISABLE_CC, DISABLE_BME,
    POST_STOP_SNAPSHOT, RETIRE_RESOURCE, STAGE_COUNT
};

static void attempt_all_four_retires(unsigned configured,
                                      unsigned epoch,
                                      unsigned shutdown_ok,
                                      unsigned forced_proof)
{
    const struct n71_dma_retirement_boundary s = {
        .admin_epoch_started = !!(configured || epoch),
        .controller_shutdown_consistent = shutdown_ok,
        .independent_quiescence_proven = forced_proof
    };
    int stage;
    /* The same gate protects UNPREPARE, NVMMU, DART and queue-config writes. */
    for (stage = 0; stage < 4; ++stage) {
        const int authorized = n71_dma_retire_authorized(&s);
        if (configured || epoch || forced_proof)
            assert(!authorized);
        else
            assert(authorized); /* no active-admin DMA observer cleanup */
    }
}

/* Fail at every point, including between the two BME writes. */
static void simulate_one_fault(unsigned injected_at,
                               unsigned qualified,
                               unsigned shutdown_ok,
                               unsigned forced_proof)
{
    unsigned epoch = 0;
    unsigned root_bme = 0, endpoint_bme = 0;
    unsigned stage;

    for (stage = ALLOCATE_QUEUES; stage < STAGE_COUNT; ++stage) {
        /* Intent is conservatively configured before BME qualification. */
        attempt_all_four_retires(1, epoch, shutdown_ok, forced_proof);

        if (stage == QUALIFY_BME && !qualified)
            break;
        if (stage == LATCH_BEFORE_BME)
            epoch = 1; /* Must precede either BME-capable write. */
        if (stage == ROOT_BME) {
            assert(epoch);
            root_bme = 1;
        }
        if (stage == ENDPOINT_BME) {
            assert(epoch && root_bme);
            endpoint_bme = 1;
        }
        if (stage == DISABLE_BME) {
            root_bme = 0;
            endpoint_bme = 0;
        }
        if (root_bme || endpoint_bme)
            assert(epoch);
        if (injected_at == stage)
            break;

        /* Neither successful shutdown nor BME-off clears ownership. */
        if (stage >= LATCH_BEFORE_BME)
            assert(epoch);
    }
    attempt_all_four_retires(1, epoch, shutdown_ok, forced_proof);
    if (stage >= LATCH_BEFORE_BME)
        assert(epoch);
}

int main(void)
{
    unsigned fault, qualified, shutdown_ok, forced_proof;
    unsigned cases = 0;

    assert(!n71_dma_retire_authorized(NULL));
    /* A never-started observer can be cleaned up, with no DMA epoch. */
    attempt_all_four_retires(0, 0, 0, 0);
    attempt_all_four_retires(0, 0, 1, 0);

    /* A latched epoch blocks release even without the opt-in parameter. */
    attempt_all_four_retires(0, 1, 0, 0);
    attempt_all_four_retires(0, 1, 1, 1);
    /* A claimed independent proof is not an implemented release path. */
    attempt_all_four_retires(0, 0, 1, 1);

    for (fault = 0; fault < STAGE_COUNT; ++fault)
      for (qualified = 0; qualified < 2; ++qualified)
        for (shutdown_ok = 0; shutdown_ok < 2; ++shutdown_ok)
          for (forced_proof = 0; forced_proof < 2; ++forced_proof) {
            simulate_one_fault(fault, qualified, shutdown_ok, forced_proof);
            ++cases;
          }

    assert(cases == 112); /* 14 stages x 2 x 2 x 2 */
    printf("S3E_DMA_EPOCH_FAIL_CLOSED_PASS scenarios=%u guarded_resources=4\n", cases);
    return 0;
}
"""


class S3EDMARetirementTests(unittest.TestCase):
    def test_host_fault_injection_matrix(self):
        with tempfile.TemporaryDirectory(prefix="n71-dma-epoch-") as tmp:
            src = Path(tmp) / "faults.c"
            out = Path(tmp) / "faults"
            src.write_text(HOST_C)
            build = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(PORT0), str(src), "-o", str(out)],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            trial = subprocess.run([str(out)], capture_output=True,
                                   text=True, check=False)
            self.assertEqual(trial.returncode, 0, trial.stderr)
            self.assertIn("scenarios=112 guarded_resources=4", trial.stdout)

    def test_latch_precedes_root_and_endpoint_bme(self):
        master = ADMIN[ADMIN.index("static int n71_admin_master("):
                       ADMIN.index("static void n71_admin_cc(")]
        latch = master.index("WRITE_ONCE(n71_admin_dma_epoch_latched, true)")
        qualifier = master.index("if (enable && (!ans_identify_once")
        root_bme = master.index("writew(value,(u8 __iomem *)m->cfg+4)")
        endpoint_bme = master.index("writew(value,(u8 __iomem *)m->endpoint+4)")
        self.assertLess(qualifier, latch)
        self.assertLess(latch, root_bme)
        self.assertLess(latch, endpoint_bme)

    def test_no_unlatch_or_writeable_epoch_flag(self):
        self.assertEqual(MAIN.count("static bool n71_admin_dma_epoch_latched;"), 1)
        self.assertNotIn("WRITE_ONCE(n71_admin_dma_epoch_latched, false)", MAIN + ADMIN)
        self.assertNotRegex(MAIN + ADMIN, r"module_param\(n71_admin_dma_epoch_latched")
        self.assertIn("module_param(ans_identify_once, bool, 0400)", MAIN)

    def test_all_four_retirement_paths_refuse_active_epoch(self):
        actual = (MAIN + "\n" + ADMIN).count(
            ".admin_epoch_started=ans_identify_once || "
            "READ_ONCE(n71_admin_dma_epoch_latched)"
        )
        self.assertEqual(actual, 4)
        for filename, start, end, denied, release in (
            (ADMIN, "static int n71_admin_unprepare(", "static void n71_admin_queue_register_retire_probe(", "stage=UNPREPARE", "n71_admin_dart_map(ctx,0)"),
            (ADMIN, "static void n71_admin_queue_register_retire_probe(", "static int n71_storage_admin_identify_once(", "dma_epoch_no_proof=YES", "n71_admin_write(i,0);"),
            (MAIN, "static int n71_storage_nvmmu_owned_trial(", "static int n71_storage_p0_config_observe(", "stage=NVMMU", "n71_storage_nvmmu_free();"),
            (MAIN, "static int n71_storage_dart_owned_trial(", "static int __init n71_port0_init(", "stage=DART", "n71_owned_free(&n71_tables);"),
        ):
            with self.subTest(stage=denied):
                start_at = filename.find(start)
                self.assertGreaterEqual(start_at, 0, start)
                end_at = filename.find(end, start_at)
                self.assertGreater(end_at, start_at, end)
                block = filename[start_at:end_at]
                self.assertIn(denied, block)
                self.assertLess(block.index("n71_dma_retire_authorized("),
                                block.index(release))
                self.assertIn("independent_quiescence_proven=0", block)

    def test_nvmmu_allocation_failure_never_releases_latched_dma(self):
        trial = MAIN[MAIN.index("static int n71_storage_nvmmu_owned_trial("):
                     MAIN.index("static int n71_storage_p0_config_observe(")]
        self.assertEqual(trial.count("alloc_fail:"), 1)
        cleanup = trial.split("alloc_fail:", 1)[1]
        gate = "if (READ_ONCE(n71_admin_dma_epoch_latched)) {"
        self.assertIn(gate, cleanup)
        self.assertIn("n71_unreleased=true;", cleanup)
        self.assertIn("return -3;", cleanup)
        self.assertIn("NVMMU_ALLOC_FAIL_AFTER_DMA_EPOCH_KEEP_ALL_BACKING", cleanup)
        self.assertLess(cleanup.index(gate), cleanup.index("n71_storage_admin_free();"))
        self.assertLess(cleanup.index("return -3;"), cleanup.index("n71_storage_admin_free();"))
        for name in ("n71_storage_admin_free();", "n71_storage_hmb_free();",
                     "n71_storage_nvmmu_free();"):
            self.assertEqual(cleanup.count(name), 1)
        self.assertIn("return rc;", cleanup)  # no-epoch allocation failure can unwind

    def test_nvmmu_allocation_failure_precedes_device_activation(self):
        trial = MAIN[MAIN.index("static int n71_storage_nvmmu_owned_trial("):
                     MAIN.index("static int n71_storage_p0_config_observe(")]
        # All branches into alloc_fail occur before the NVMMU callback that
        # can release PERST, enable PCIe/BME and latch an admin DMA epoch.
        main = trial.split("alloc_fail:", 1)[0]
        self.assertGreater(main.count("goto alloc_fail;"), 0)
        self.assertLess(main.rindex("goto alloc_fail;"),
                        main.index("rc=n71_nvmmu_owned_tables_trial("))
        self.assertIn("READ_ONCE(n71_admin_dma_epoch_latched)", trial)
        self.assertIn("n71_unreleased=true;", trial)
        self.assertIn("if (n71_unreleased) {", MAIN)
        self.assertIn("__module_get(THIS_MODULE);", MAIN)

    def test_hardware_status_is_not_dma_release_proof(self):
        self.assertIn("if (s->admin_epoch_started) return 0", BOUNDARY)
        self.assertIn("if (s->independent_quiescence_proven) return 0", BOUNDARY)
        self.assertNotIn("controller_shutdown_consistent) return 1", BOUNDARY)
        self.assertNotIn("return 1; /* DMA safe */", BOUNDARY)


if __name__ == "__main__":
    unittest.main()
