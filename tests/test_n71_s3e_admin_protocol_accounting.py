# SPDX-License-Identifier: MIT
"""S3E single-admin-command protocol accounting (offline only).

All 4096 boolean input combinations are synthetic; no device, NAND, firmware,
or MMIO is accessed. A complete protocol snapshot is never DMA release proof.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental" / "port0"
SOURCE = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
GATE = (PORT0 / "n71_s3e_admin_protocol_accounting.h").read_text()

C = r"""
#include <assert.h>
#include <stdio.h>
#include "n71_s3e_admin_protocol_accounting.h"

int main(void)
{
    struct n71_s3e_admin_protocol_snapshot s;
    unsigned int mask, matches=0, incomplete=0, no_submit=0;
    assert(n71_s3e_admin_protocol_classify(NULL) == N71_S3E_ADMIN_NOT_SUBMITTED);
    assert(!n71_s3e_admin_protocol_dma_release_allowed(NULL));
    for (mask = 0; mask < 4096; ++mask) {
        s = (struct n71_s3e_admin_protocol_snapshot) {
            .submitted = !!(mask & (1U << 0)),
            .completion_observed = !!(mask & (1U << 1)),
            .completion_validated = !!(mask & (1U << 2)),
            .cq_head_doorbell_written = !!(mask & (1U << 3)),
            .data_arrived = !!(mask & (1U << 4)),
            .namespace_validated = !!(mask & (1U << 5)),
            .shutdown_attempted = !!(mask & (1U << 6)),
            .shutdown_complete = !!(mask & (1U << 7)),
            .controller_disabled = !!(mask & (1U << 8)),
            .master_off = !!(mask & (1U << 9)),
            .queues_retained = !!(mask & (1U << 10)),
            .admin_epoch_latched = !!(mask & (1U << 11))
        };
        enum n71_s3e_admin_protocol_result r =
            n71_s3e_admin_protocol_classify(&s);
        assert(!n71_s3e_admin_protocol_dma_release_allowed(&s));
        if (mask == 4095) {
            assert(r == N71_S3E_ADMIN_ACCOUNTED_DMA_UNPROVEN);
            matches++;
        } else if (!(mask & 1U)) {
            assert(r == N71_S3E_ADMIN_NOT_SUBMITTED);
            no_submit++;
        } else {
            assert(r == N71_S3E_ADMIN_INCOMPLETE);
            incomplete++;
        }
    }
    /* Bad/nonboolean inputs must not be treated as true. */
    s.submitted = 2;
    assert(n71_s3e_admin_protocol_classify(&s) ==
           N71_S3E_ADMIN_NOT_SUBMITTED);
    s.submitted = 1;
    s.completion_validated = 2;
    assert(n71_s3e_admin_protocol_classify(&s) ==
           N71_S3E_ADMIN_INCOMPLETE);
    assert(matches == 1 && incomplete == 2047 && no_submit == 2048);
    printf("S3E_PROTOCOL_ACCOUNTING_PASS combinations=4096 release_allowed=NO\n");
    return 0;
}
"""

class S3EProtocolAccountingTests(unittest.TestCase):
    def test_exhaustive_4096_combinations(self):
        with tempfile.TemporaryDirectory(prefix="s3e-protocol-") as work:
            src = Path(work) / "model.c"
            output = Path(work) / "model"
            src.write_text(C)
            compile_run = subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                 "-I", str(PORT0), str(src), "-o", str(output)],
                capture_output=True, text=True
            )
            self.assertEqual(compile_run.returncode, 0, compile_run.stderr)
            run = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("combinations=4096 release_allowed=NO", run.stdout)

    def test_completion_identity_distinct_from_phase_and_payload(self):
        self.assertIn("n71_admin_memory.completed=true;", SOURCE)
        self.assertIn("n71_admin_memory.completion_validated=true;", SOURCE)
        self.assertIn("n71_admin_memory.namespace_validated=true;", SOURCE)
        self.assertIn("n71_admin_memory.cq_head_doorbell_written=true;", SOURCE)
        self.assertLess(SOURCE.index("if (status!=le16_to_cpu(cqe.status) ||"),
                        SOURCE.index("n71_admin_memory.completion_validated=true;"))
        self.assertLess(SOURCE.index("n71_admin_memory.completion_validated=true;"),
                        SOURCE.index("n71_admin_write(0x1004,1);"))
        self.assertLess(SOURCE.index("n71_admin_memory.completion_validated=true;"),
                        SOURCE.index("n71_admin_memory.namespace_validated=true;"))
        self.assertLess(SOURCE.index("nsze>(U64_MAX>>lbads)) return -EPROTO;"),
                        SOURCE.index("n71_admin_memory.namespace_validated=true;"))

    def test_protocol_observer_after_controller_shutdown(self):
        observer = SOURCE.index("ADMIN_PROTOCOL_ACCOUNTING_RO")
        self.assertGreater(observer, SOURCE.index("rc=n71_admin_once_core(&o,ctx,&r);"))
        self.assertLess(observer, SOURCE.index("if (n71_admin_unprepare(ctx))"))
        self.assertIn("dma_release_authorized=NO", SOURCE)
        self.assertIn("n71_s3e_admin_protocol_classify(&snap)", SOURCE)

    def test_observer_header_never_releases_or_writes(self):
        self.assertIn("return 0;", GATE)
        self.assertIn("N71_S3E_ADMIN_ACCOUNTED_DMA_UNPROVEN", GATE)
        for forbidden in ("writel(", "writew(", "dma_unmap_", "free_page(",
                          "n71_admin_write(", "release_allowed = 1"):
            self.assertNotIn(forbidden, GATE)

if __name__ == "__main__":
    unittest.main()
