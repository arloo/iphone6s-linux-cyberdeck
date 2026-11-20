# SPDX-License-Identifier: MIT
"""Bounded post-stop DMA-change observer: synthetic/contract tests only.

Tests detect changed owned RAM content; they MUST NOT infer that stable data
means the S8000 NVMe controller is quiescent. Nothing runs on the device.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental" / "port0"
SRC = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
OWNER = (PORT0 / "n71_s3e_p0_asserted_reset_rootstart.c").read_text()
HDR = (PORT0 / "n71_s3e_late_dma_observer.h").read_text()

C = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_late_dma_observer.h"
int main(void)
{
    unsigned char cq[4096], data[4096];
    struct n71_s3e_late_dma_observer s = {0};
    unsigned long long first_cq, first_data;
    int i;
    memset(cq, 0xa5, sizeof(cq));
    memset(data, 0x00, sizeof(data));
    assert(!n71_s3e_late_dma_fingerprint(NULL, 16));
    assert(!n71_s3e_late_dma_fingerprint(data, 0));
    first_cq = n71_s3e_late_dma_fingerprint(cq, sizeof(cq));
    first_data = n71_s3e_late_dma_fingerprint(data, sizeof(data));
    assert(first_cq != first_data);
    assert(!n71_s3e_late_dma_release_allowed(NULL));

    /* Twelve identical samples cannot ever authorize release. */
    for (i = 0; i < 12; ++i) {
        n71_s3e_late_dma_observe(&s, first_cq, first_data);
        assert(!n71_s3e_late_dma_release_allowed(&s));
    }
    assert(s.samples == 12 && !s.ever_changed &&
           !s.cq_changed && !s.data_changed);

    /* Mutate only an unexamined byte: whole-page hash must detect it. */
    cq[3781] ^= 0x40;
    n71_s3e_late_dma_observe(&s,
        n71_s3e_late_dma_fingerprint(cq,sizeof(cq)), first_data);
    assert(s.ever_changed && s.cq_changed == 1 && s.data_changed == 0);
    assert(!n71_s3e_late_dma_release_allowed(&s));

    /* Data buffer changes must be independently counted. */
    data[293] = 0x11;
    n71_s3e_late_dma_observe(&s, first_cq,
        n71_s3e_late_dma_fingerprint(data,sizeof(data)));
    assert(s.samples == 14 && s.cq_changed == 1 &&
           s.data_changed == 1 && s.ever_changed);
    assert(!n71_s3e_late_dma_release_allowed(&s));

    /* Returning to initial bytes cannot erase a prior alert. */
    cq[3781] ^= 0x40;
    data[293] = 0;
    n71_s3e_late_dma_observe(&s, first_cq, first_data);
    assert(s.samples == 15 && s.ever_changed &&
           s.cq_changed == 1 && s.data_changed == 1);
    assert(!n71_s3e_late_dma_release_allowed(&s));

    /* Null observer is a harmless no-op, never authority. */
    n71_s3e_late_dma_observe(NULL, first_cq, first_data);
    puts("S3E_LATE_RAM_WITNESS_PASS samples=15 no_dma_release=YES");
    return 0;
}
"""

class S3ELateRamWitnessTests(unittest.TestCase):
    def test_compiled_fingerprints_and_change_latch(self):
        with tempfile.TemporaryDirectory(prefix="n71-late-dma-") as td:
            src = Path(td) / "trial.c"
            out = Path(td) / "trial"
            src.write_text(C)
            result = subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                 "-I", str(PORT0), str(src), "-o", str(out)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("S3E_LATE_RAM_WITNESS_PASS", result.stdout)

    def test_opt_in_and_no_unsafe_concurrent_observers(self):
        self.assertIn("module_param(ans_late_dma_probe_ro, bool, 0400);", OWNER)
        self.assertIn("ans_late_dma_probe_ro && (!ans_identify_once ||", OWNER)
        self.assertIn("ans_queue_retire_probe || ans_phase_trace_ro", OWNER)
        self.assertIn("n71_admin_late_dma_probe_ro(&r);", SRC)
        self.assertIn("stable_is_not_proof=YES", SRC)
        self.assertIn("release_allowed=NO", SRC)

    def test_hardware_probes_only_owned_dma_pages_after_shutdown(self):
        a = SRC.index("static void n71_admin_late_dma_probe_ro(")
        b = SRC.index("static int n71_storage_admin_identify_once(", a)
        probe = SRC[a:b]
        for field in ("r->shutdown_attempted", "r->shutdown_rc==0",
                      "r->shutdown_csts==9", "r->disable_rc==0",
                      "r->master_off", "n71_admin_memory.dart_mapped",
                      "n71_admin_memory.namespace_validated",
                      "READ_ONCE(n71_admin_dma_epoch_latched)",
                      "n71_admin_memory.mapped[1]",
                      "n71_admin_memory.mapped[2]"):
            self.assertIn(field, probe)
        for forbidden in ("writel(", "writew(", "n71_admin_write(",
                          "dma_unmap_", "free_page(", "dma_free_",
                          "n71_admin_dart_map(", "n71_storage_nvmmu_free("):
            self.assertNotIn(forbidden, probe)
        self.assertIn("for (i=0;i<12;i++)", probe)
        self.assertIn("msleep(50)", probe)
        self.assertIn("dma_sync_single_for_cpu", probe)
        self.assertIn("dma_sync_single_for_device", probe)

    def test_observer_has_no_resource_release_authority(self):
        self.assertIn("return 0;", HDR)
        self.assertIn("n71_s3e_late_dma_release_allowed", HDR)
        for forbidden in ("writew(", "writel(", "dma_unmap_", "free_page(",
                          "kmalloc(", "kfree(", "n71_dma_retire_authorized("):
            self.assertNotIn(forbidden, HDR)

if __name__ == "__main__":
    unittest.main()
