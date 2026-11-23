# SPDX-License-Identifier: MIT
"""Host-C proof of S8000 FlatDMA tag1 TCB/SGL staging, no device access."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental/port0"
SOURCE = (PORT0 / "n71_s3e_ro_flatdma_tag1_stage.h").read_text()
OWNER = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()

HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_ro_flatdma_tag1_stage.h"

static unsigned char tcb[16384], sgl[16384];
static unsigned char before[16384];
static const struct n71_s3e_ro_io_layout layout={
    .admin_sq_iova=0x80010000ULL,.admin_cq_iova=0x80011000ULL,
    .io_sq_iova=0x80012000ULL,.io_cq_iova=0x80013000ULL,
    .data_iova=0x40800000ULL
};
static const struct n71_s3e_ro_owned_frames frames={
    .admin_sq_pa=0x10000000ULL,.admin_cq_pa=0x10004000ULL,
    .io_sq_pa=0x10008000ULL,.io_cq_pa=0x1000c000ULL,
    .read_data_pa=0x10010000ULL,.read_sgl_pa=0x10014000ULL
};

static void baseline(void)
{
    memset(tcb,0,sizeof(tcb));
    memset(sgl,0,sizeof(sgl));
    n71_ro_le32(tcb,0x200);
    n71_ro_le32(tcb+4,1);
    n71_ro_le32(tcb+8,0x10002000U>>12);
    n71_ro_le64(tcb+16,0x10018000ULL);
    n71_ro_le32(tcb+127*128+32,0xabcddcba);
    memcpy(before,tcb,sizeof(tcb));
}
static void assert_reject_unchanged(
    const struct n71_s3e_ro_owned_frames *f,
    const struct n71_s3e_ro_io_layout *l)
{
    unsigned char saved_tcb[16384],saved_sgl[16384];
    memcpy(saved_tcb,tcb,sizeof(tcb));
    memcpy(saved_sgl,sgl,sizeof(sgl));
    static unsigned int rejection_case;
    int rc = n71_s3e_ro_stage_flatdma_tag1(tcb,sgl,f,l);
    rejection_case++;
    if (rc != -1) fprintf(stderr,"unexpected_accept_case=%u\n",rejection_case);
    assert(rc == -1);
    assert(!memcmp(saved_tcb,tcb,sizeof(tcb)));
    assert(!memcmp(saved_sgl,sgl,sizeof(sgl)));
}

static void test_tag1_exact_staging(void)
{
    unsigned int i;
    baseline();
    assert(!n71_s3e_ro_stage_flatdma_tag1(tcb,sgl,&frames,&layout));
    assert(n71_ro_get_le32(tcb+128)==0x200);
    assert(n71_ro_get_le32(tcb+132)==1);
    assert(n71_ro_get_le32(tcb+136)==(frames.read_data_pa>>12));
    assert(n71_ro_get_le64(tcb+144)==frames.read_sgl_pa);
    assert(n71_ro_get_le32(sgl)==(frames.read_data_pa>>12));
    for(i=0;i<sizeof(tcb);i++){
        if(i>=128&&i<256)continue;
        assert(tcb[i]==before[i]);
    }
    for(i=4;i<sizeof(sgl);i++)assert(sgl[i]==0);
    for(i=128;i<256;i++){
        if ((i>=128&&i<132)||(i>=132&&i<136)||(i>=136&&i<140)||
            (i>=144&&i<152)) continue;
        assert(tcb[i]==0);
    }
    assert_reject_unchanged(&frames,&layout); /* tag1 must never be reused */
}
static void test_fail_atomic(void)
{
    struct n71_s3e_ro_owned_frames f;
    struct n71_s3e_ro_io_layout l;
    baseline();tcb[128]=1;assert_reject_unchanged(&frames,&layout);
    baseline();tcb[255]=1;assert_reject_unchanged(&frames,&layout);
    baseline();sgl[4]=1;assert_reject_unchanged(&frames,&layout);
    baseline();sgl[16383]=1;assert_reject_unchanged(&frames,&layout);
    baseline();memset(tcb,0,4);assert_reject_unchanged(&frames,&layout);
    baseline();tcb[4]=0;assert_reject_unchanged(&frames,&layout);
    baseline();memset(tcb+8,0,4);assert_reject_unchanged(&frames,&layout);
    baseline();memset(tcb+16,0,8);assert_reject_unchanged(&frames,&layout);
    baseline();f=frames;f.read_sgl_pa=f.read_data_pa;
    assert_reject_unchanged(&f,&layout);
    baseline();f=frames;f.read_sgl_pa=0x10014001;
    assert_reject_unchanged(&f,&layout);
    baseline();l=layout;l.data_iova=0x40001000ULL;
    assert_reject_unchanged(&frames,&l);
    baseline();l=layout;l.data_iova=0x40801000ULL;
    assert_reject_unchanged(&frames,&l);
    baseline();l=layout;l.data_iova=0x41000000ULL;
    assert_reject_unchanged(&frames,&l);
    assert(n71_s3e_ro_stage_flatdma_tag1(NULL,sgl,&frames,&layout)==-1);
    assert(n71_s3e_ro_stage_flatdma_tag1(tcb,NULL,&frames,&layout)==-1);
    assert(n71_s3e_ro_stage_flatdma_tag1(tcb,sgl,NULL,&layout)==-1);
    assert(n71_s3e_ro_stage_flatdma_tag1(tcb,sgl,&frames,NULL)==-1);
    /* CPU view of the same table cannot be used for the SGL backing. */
    assert(n71_s3e_ro_stage_flatdma_tag1(tcb,tcb,&frames,&layout)==-1);
}

int main(void)
{
    test_tag1_exact_staging();
    test_fail_atomic();
    puts("N71_S8000_ORIGINAL_STRIDE_TAG1_TCB_SGL_CPU_STAGE_PASS index=1 byte_offset=128 tag_iova=0x40800000 no_hardware_dma=YES");
    return 0;
}
"""


class N71FlatDMASecondTCBTests(unittest.TestCase):
    def test_real_c_tag1_buffer_staging_success_and_atomic_failures(self):
        with tempfile.TemporaryDirectory(prefix="n71-tag1-") as t:
            path = Path(t)
            source = path / "test.c"
            exe = path / "test"
            source.write_text(HARNESS)
            compile_result = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(PORT0), str(source), "-o", str(exe)],
                capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("N71_S8000_ORIGINAL_STRIDE_TAG1_TCB_SGL_CPU_STAGE_PASS",
                          result.stdout)

    def test_selected_fields_and_no_hardware_side_effects(self):
        self.assertIn("N71_RO_TCB_BYTES 128U", SOURCE)
        self.assertIn("N71_RO_TCB_COUNT 128U", SOURCE)
        self.assertIn("N71_RO_TCB_TAG1_OFFSET", SOURCE)
        self.assertIn("slot + 4U, 1U", SOURCE)
        self.assertIn("N71_RO_ONE_PAGE_FROM_DEVICE_CANDIDATE 0x200U", SOURCE)
        self.assertIn("UNQUALIFIED", SOURCE)
        self.assertIn("no register write", SOURCE.lower())
        for call in ("writel(", "writew(", "dma_map_single(",
                     "dma_unmap_single(", "free_page(", "dma_sync_single_for_device("):
            self.assertNotIn(call, SOURCE)
        self.assertNotIn("n71_s3e_ro_stage_flatdma_tag1(", OWNER)
        self.assertIn('#include "n71_s3e_ro_flatdma_tag1_stage.h"', OWNER)
        self.assertIn("BUILD_BUG_ON(N71_RO_READ_FLATDMA_TAG_CANDIDATE != 0x40800000ULL)", OWNER)

if __name__ == "__main__":
    unittest.main()
