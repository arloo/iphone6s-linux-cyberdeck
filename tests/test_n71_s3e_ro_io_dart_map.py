# SPDX-License-Identifier: MIT
"""Real C L2 page-table staging tests, never hardware DMA/MMIO operations.

Four candidate DART0 stream tables are manipulated in private host RAM only;
preexisting admin leaves must survive and every failure is atomic.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental/port0"
HEADER = (PORT0 / "n71_s3e_ro_io_dart_map.h").read_text()
OWNER = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()

HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_ro_io_dart_map.h"

static unsigned char pages[4][4096];
static unsigned char original[4][4096];
static unsigned char *table[4]={pages[0],pages[1],pages[2],pages[3]};
static const struct n71_s3e_ro_io_layout layout = {
    .admin_sq_iova=0x80010000ULL,
    .admin_cq_iova=0x80011000ULL,
    .io_sq_iova=0x80012000ULL,
    .io_cq_iova=0x80013000ULL,
    .data_iova=0x40001000ULL
};
static const struct n71_s3e_ro_owned_frames frames = {
    .admin_sq_pa=0x10000000ULL,
    .admin_cq_pa=0x10004000ULL,
    .io_sq_pa=0x10008000ULL,
    .io_cq_pa=0x1000c000ULL,
    .read_data_pa=0x10010000ULL
};

static void baseline(void)
{
    unsigned int sid;
    memset(pages,0,sizeof(pages));
    for (sid=0;sid<4;sid++) {
        n71_ro_le64(pages[sid]+16*8, frames.admin_sq_pa|3ULL);
        n71_ro_le64(pages[sid]+17*8, frames.admin_cq_pa|3ULL);
        n71_ro_le64(pages[sid]+20*8, 0x55667788ULL + sid);
        n71_ro_le64(pages[sid]+511*8, 0xabcdef012345ULL+sid);
    }
    memcpy(original,pages,sizeof(pages));
}
static void assert_atomic_reject(
    const struct n71_s3e_ro_io_layout *l,
    const struct n71_s3e_ro_owned_frames *f,
    const struct n71_s3e_ro_foreign_range *foreign,unsigned int n)
{
    unsigned char before[4][4096];
    memcpy(before,pages,sizeof(before));
    assert(n71_s3e_ro_stage_io_queue_l2(table,l,f,foreign,n)==-1);
    assert(!memcmp(before,pages,sizeof(before)));
}
static void successful_four_stream_mapping(void)
{
    unsigned int sid,i;
    baseline();
    assert(!n71_s3e_ro_verify_queue_iova(&layout));
    assert(!n71_s3e_ro_verify_ownership(&frames,NULL,0));
    assert(!n71_s3e_ro_stage_io_queue_l2(table,&layout,&frames,NULL,0));
    for(sid=0;sid<4;sid++) {
        assert(n71_ro_get_le64(pages[sid]+16*8)==(frames.admin_sq_pa|3ULL));
        assert(n71_ro_get_le64(pages[sid]+17*8)==(frames.admin_cq_pa|3ULL));
        assert(n71_ro_get_le64(pages[sid]+18*8)==(frames.io_sq_pa|3ULL));
        assert(n71_ro_get_le64(pages[sid]+19*8)==(frames.io_cq_pa|3ULL));
        assert(n71_ro_get_le64(pages[sid]+20*8)==0x55667788ULL+sid);
        assert(n71_ro_get_le64(pages[sid]+511*8)==0xabcdef012345ULL+sid);
        for(i=0;i<4096;i++) {
            if(i>=18*8 && i<20*8)continue;
            assert(pages[sid][i]==original[sid][i]);
        }
        /* Read data is not a DART queue leaf; it needs FlatDMA/NVMMU. */
        for(i=0;i<4096;i+=8)
            assert(n71_ro_get_le64(pages[sid]+i)!=(frames.read_data_pa|3ULL));
    }
    /* Another stage on already owned leaves must fail, unchanged. */
    assert_atomic_reject(&layout,&frames,NULL,0);
}
static void mixed_stream_rejections_are_atomic(void)
{
    unsigned int sid;
    for(sid=0;sid<4;sid++) {
        baseline();
        n71_ro_le64(pages[sid]+19*8,0xabcULL);
        assert_atomic_reject(&layout,&frames,NULL,0);
        baseline();
        n71_ro_le64(pages[sid]+16*8,0xabcULL);
        assert_atomic_reject(&layout,&frames,NULL,0);
        baseline();
        n71_ro_le64(pages[sid]+17*8,0xabcULL);
        assert_atomic_reject(&layout,&frames,NULL,0);
        baseline();
        n71_ro_le64(pages[sid]+18*8,0xabcULL);
        assert_atomic_reject(&layout,&frames,NULL,0);
    }
    baseline();
    table[2]=NULL;
    assert_atomic_reject(&layout,&frames,NULL,0);
    table[2]=pages[2];
    table[3]=pages[0];
    assert_atomic_reject(&layout,&frames,NULL,0);
    table[3]=pages[3];
    table[1]=pages[0]+8;  /* overlapping 4KiB view */
    assert_atomic_reject(&layout,&frames,NULL,0);
    table[1]=pages[1];
}
static void physical_ownership_rejections(void)
{
    struct n71_s3e_ro_owned_frames f;
    struct n71_s3e_ro_foreign_range r;
    struct n71_s3e_ro_io_layout l;
    unsigned long long *v;
    unsigned int i,j;
    for (i=0;i<5;i++) {
        baseline(); f=frames; v=&f.admin_sq_pa;v[i]=0;
        assert_atomic_reject(&layout,&f,NULL,0);
        f=frames;v=&f.admin_sq_pa;v[i]=0x10000001ULL;
        assert_atomic_reject(&layout,&f,NULL,0);
        f=frames;v=&f.admin_sq_pa;v[i]=(1ULL<<36);
        assert_atomic_reject(&layout,&f,NULL,0);
        for(j=0;j<i;j++) {
            f=frames;v=&f.admin_sq_pa;v[i]=v[j];
            assert_atomic_reject(&layout,&f,NULL,0);
        }
    }
    baseline();
    r.pa=frames.read_data_pa+4096ULL;r.bytes=4096ULL;
    assert_atomic_reject(&layout,&frames,&r,1);
    r.pa=frames.io_sq_pa+8192ULL;
    assert_atomic_reject(&layout,&frames,&r,1);
    r.pa=(1ULL<<36)-1;r.bytes=64ULL;
    assert_atomic_reject(&layout,&frames,&r,1);
    r.pa=frames.io_sq_pa;r.bytes=0;
    assert_atomic_reject(&layout,&frames,&r,1);
    r.pa=0x30000000ULL;r.bytes=4096ULL;
    assert(!n71_s3e_ro_stage_io_queue_l2(table,&layout,&frames,&r,1));
    baseline();
    assert_atomic_reject(&layout,&frames,NULL,1); /* missing exclusion array */
    l=layout;l.io_sq_iova=0x80014000ULL;
    assert_atomic_reject(&l,&frames,NULL,0);
    l=layout;l.data_iova=0x40000000ULL; /* Identify FlatDMA alias */
    assert_atomic_reject(&l,&frames,NULL,0);
    assert(n71_s3e_ro_verify_queue_iova(NULL)==-1);
    assert(n71_s3e_ro_verify_ownership(NULL,NULL,0)==-1);
    assert(n71_s3e_ro_stage_io_queue_l2(NULL,&layout,&frames,NULL,0)==-1);
}
int main(void)
{
    successful_four_stream_mapping();
    mixed_stream_rejections_are_atomic();
    physical_ownership_rejections();
    puts("N71_S3E_IO_DART0_L2_STAGE_PASS streams=4 leaves=18,19 prior=16,17 16KiB_frames=YES no_mmio=YES");
    return 0;
}
"""


class FourStreamDartQueueStageTests(unittest.TestCase):
    def test_real_c_mapping_in_host_memory(self):
        with tempfile.TemporaryDirectory(prefix="n71-io-map-") as dirname:
            path = Path(dirname)
            source = path / "map.c"
            executable = path / "map"
            source.write_text(HARNESS)
            build = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(PORT0), str(source), "-o", str(executable)],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("N71_S3E_IO_DART0_L2_STAGE_PASS", run.stdout)

    def test_separate_data_path_and_dma_quarantine(self):
        self.assertIn("The data page is NOT mapped", HEADER)
        self.assertIn("original-S8000 NVMMU/TCB/SGL qualification", HEADER)
        self.assertIn("N71_RO_DART_IO_SQ_INDEX 18U", HEADER)
        self.assertIn("N71_RO_DART_IO_CQ_INDEX 19U", HEADER)
        self.assertIn("N71_RO_DART_STREAMS 4U", HEADER)
        self.assertIn("N71_RO_HOST_FRAME_BYTES 16384U", HEADER)
        self.assertIn("no_dma_release", OWNER.lower())
        for action in ("writel(", "writew(", "dma_map_single(",
                       "dma_unmap_single(", "dma_sync_single_for_device(",
                       "free_page(", "memcpy("):
            self.assertNotIn(action, HEADER)
        self.assertNotIn("n71_s3e_ro_stage_io_queue_l2(", OWNER)
        self.assertIn('#include "n71_s3e_ro_io_dart_map.h"', OWNER)
        self.assertIn("BUILD_BUG_ON(N71_RO_HOST_FRAME_BYTES!=SZ_16K)", OWNER)
        self.assertIn("N71_RO_DART_IO_CQ_INDEX", OWNER)

if __name__ == "__main__":
    unittest.main()
