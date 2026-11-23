# SPDX-License-Identifier: MIT
"""Host-only CQE ownership validation for the one-shot S3E Identify NS1.

No real hardware, Apple firmware, device commands, NAND, or MMIO is accessed.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental" / "port0"
HEADER = (PORT0 / "n71_s3e_admin_cqe_validate.h").read_text()
ADMIN = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
BOUNDARY = (PORT0 / "n71_s3e_dma_retirement_boundary.h").read_text()

HOST_C = r"""
#include <assert.h>
#include <stdio.h>
#include "n71_s3e_admin_cqe_validate.h"
#include "n71_s3e_dma_retirement_boundary.h"

int main(void)
{
    struct n71_s3e_admin_cqe_fields v = {1, 1, 0, 1};
    struct n71_dma_retirement_boundary epoch = {1, 1, 0};
    unsigned int i;
    assert(!n71_s3e_admin_identify_cqe_valid(NULL));
    assert(n71_s3e_admin_identify_cqe_valid(&v));
    assert(!n71_dma_retire_authorized(&epoch));

    /* Only status == 1 is accepted: phase=1 with no status error bits. */
    for (i=0; i<65536; ++i) {
        v.status = i;
        assert(!!n71_s3e_admin_identify_cqe_valid(&v) == (i==1));
    }
    v.status=1;

    /* CID, SQID, and SQ head must match the one-shot admin command. */
    for (i=0; i<65536; ++i) {
        v.command_id=i;
        assert(!!n71_s3e_admin_identify_cqe_valid(&v) == (i==1));
    }
    v.command_id=1;
    for (i=0; i<65536; ++i) {
        v.sq_id=i;
        assert(!!n71_s3e_admin_identify_cqe_valid(&v) == (i==0));
    }
    v.sq_id=0;
    for (i=0; i<65536; ++i) {
        v.sq_head=i;
        assert(!!n71_s3e_admin_identify_cqe_valid(&v) == (i==1));
    }
    v.sq_head=1;

    v.command_id=65536U;
    assert(!n71_s3e_admin_identify_cqe_valid(&v));
    v.command_id=1;
    assert(n71_s3e_admin_identify_cqe_valid(&v));
    /* A perfect CQE cannot imply DMA retirement. */
    assert(!n71_dma_retire_authorized(&epoch));
    puts("N71_S3E_CQE_VALIDATE_PASS synthetic_values=262144 dma_release=DENIED");
    return 0;
}
"""

class N71S3ECQEValidationTests(unittest.TestCase):
    def test_exhaustive_synthetic_status_and_identity(self):
        with tempfile.TemporaryDirectory(prefix="n71-cqe-") as work:
            src = Path(work) / "cqe.c"
            output = Path(work) / "cqe"
            src.write_text(HOST_C)
            build = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(PORT0), str(src), "-o", str(output)],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("synthetic_values=262144 dma_release=DENIED", run.stdout)

    def test_validation_is_a_pure_host_and_kernel_function(self):
        self.assertIn("n71_s3e_admin_identify_cqe_valid(", HEADER)
        for forbidden in ("writel(", "writew(", "dma_unmap_", "free_page(",
                          "dma_sync_", "n71_dma_retire_authorized("):
            self.assertNotIn(forbidden, HEADER)
        self.assertIn("!n71_s3e_admin_identify_cqe_valid(", ADMIN)
        self.assertIn("status!=le16_to_cpu(cqe.status)", ADMIN)
        self.assertIn(".status=le16_to_cpu(cqe.status)", ADMIN)
        self.assertIn("#include \"n71_s3e_admin_cqe_validate.h\"", ADMIN)

    def test_malformed_cqe_rejected_before_head_doorbell(self):
        start = ADMIN.index("static int n71_admin_identify_ns1(")
        end = ADMIN.index("static int n71_admin_prepare(", start)
        block = ADMIN[start:end]
        order = [
            "if (!complete) return -ETIMEDOUT;",
            "n71_admin_memory.completed=true;",
            "if (status!=le16_to_cpu(cqe.status) ||",
            "!n71_s3e_admin_identify_cqe_valid(",
            "IDENTIFY_CQE_REJECTED",
            "return -EIO;",
            "n71_admin_memory.completion_validated=true;",
            "n71_admin_write(0x1004,1);",
            "n71_admin_memory.cq_head_doorbell_written=true;",
            "n71_admin_memory.namespace_validated=true;",
        ]
        offsets = [block.index(v) for v in order]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(block.count("n71_admin_write(0x1004,1);"), 1)
        self.assertIn("no_cq_head_doorbell=YES quarantine=YES", block)
        self.assertNotIn("dma_unmap_", block)
        self.assertNotIn("n71_storage_nvmmu_free(", block)

    def test_cqe_validity_not_retirement(self):
        self.assertIn("if (s->admin_epoch_started) return 0", BOUNDARY)
        self.assertIn("if (s->independent_quiescence_proven) return 0", BOUNDARY)
        self.assertIn("never authorizes DMA retirement", HEADER)

if __name__ == "__main__":
    unittest.main()
