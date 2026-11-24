# SPDX-License-Identifier: MIT
"""Exercise the actual inert N71 NS1 read-only command encoder on the host.

These checks do NOT establish that ANS/S8000 accepts the generic NVMe
I/O-queue command encoding, vendor flags, DART mapping, or FlatDMA format.
No device is used. Future physical usage needs independently proven queues.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT0 = ROOT / "experimental" / "port0"
HEADER = (PORT0 / "n71_s3e_read_only_io_plan.h").read_text()
PILOT = (PORT0 / "n71_s3e_p0_asserted_reset_rootstart.c").read_text()
KERNEL_NVME_PATH = ROOT.parent / "hoolock/linux/include/linux/nvme.h"
# The full kernel source is outside the public repo; skip this optional
# source correspondence check on isolated CI clones without that checkout.
KERNEL_NVME = KERNEL_NVME_PATH.read_text() if KERNEL_NVME_PATH.is_file() else None

HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71_s3e_read_only_io_plan.h"

static const struct n71_s3e_ro_io_layout good = {
    .admin_sq_iova=0x80010000ULL, .admin_cq_iova=0x80011000ULL,
    .io_sq_iova=0x80012000ULL, .io_cq_iova=0x80013000ULL,
    .data_iova=0x40800000ULL
};

static unsigned long long get64(const unsigned char *p)
{
    unsigned long long n=0;unsigned int i;
    for (i=0;i<8;i++) n|=(unsigned long long)p[i]<<(i*8);
    return n;
}

static void all_other_bytes_zero(const unsigned char *b, int cmdtype)
{
    unsigned int i;unsigned int nonzero_allowed[64]={0};
    if (cmdtype==0) { /* CREATE CQ (admin Q0): cmd 0x05 */
        nonzero_allowed[0]=1;nonzero_allowed[2]=1;
        nonzero_allowed[24]=1;nonzero_allowed[25]=1;nonzero_allowed[26]=1;nonzero_allowed[27]=1;
        nonzero_allowed[40]=1;nonzero_allowed[42]=1;nonzero_allowed[44]=1;
    } else if (cmdtype==1) { /* CREATE SQ (admin Q0): cmd 0x01 */
        nonzero_allowed[0]=1;nonzero_allowed[2]=1;
        nonzero_allowed[24]=1;nonzero_allowed[25]=1;nonzero_allowed[26]=1;nonzero_allowed[27]=1;
        nonzero_allowed[40]=1;nonzero_allowed[42]=1;
        nonzero_allowed[44]=1;nonzero_allowed[46]=1;
    } else { /* READ (I/O Q1): cmd 0x02 */
        nonzero_allowed[0]=1;nonzero_allowed[2]=1;nonzero_allowed[4]=1;
        nonzero_allowed[26]=1;nonzero_allowed[27]=1;
        for(i=40;i<48;i++)nonzero_allowed[i]=1;
    }
    for (i=0;i<64;i++) if (!nonzero_allowed[i]) assert(!b[i]);
}

static void test_exact_wire_formats(void)
{
    unsigned char b[64], prior[64];
    struct n71_s3e_ro_io_layout layout=good;
    unsigned int i;
    assert(!n71_s3e_ro_validate_layout(&layout));
    memset(b,0x5a,sizeof(b));
    assert(!n71_s3e_ro_encode_create_cq(b,&layout));
    assert(b[0]==0x05&&b[2]==2&&get64(b+24)==layout.io_cq_iova);
    assert(b[40]==1&&b[42]==15&&b[44]==1&&b[46]==0);
    all_other_bytes_zero(b,0);
    memset(b,0x5a,sizeof(b));
    assert(!n71_s3e_ro_encode_create_sq(b,&layout));
    assert(b[0]==0x01&&b[2]==3&&get64(b+24)==layout.io_sq_iova);
    assert(b[40]==1&&b[42]==15&&b[44]==1&&b[46]==1);
    all_other_bytes_zero(b,1);

    memset(b,0x5a,sizeof(b));
    assert(!n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0));
    assert(b[0]==0x02&&b[1]==0&&b[2]==1&&b[4]==1);
    assert(get64(b+24)==layout.data_iova&&get64(b+40)==0&&
           b[48]==0&&b[49]==0);
    all_other_bytes_zero(b,2);
    assert(!n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,15624999ULL));
    assert(get64(b+40)==15624999ULL&&get64(b+24)==layout.data_iova);
    all_other_bytes_zero(b,2);
    assert(n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0x11223344556677ULL) == -1); /* invalid LBA */

    /* Every supported invalid request must preserve the full caller buffer. */
    memset(prior,0x91,sizeof(prior));
    for(i=0;i<32;i++){
        unsigned long long bad_lba=15625000ULL+i;
        memcpy(b,prior,64);
        assert(n71_s3e_ro_encode_one_sector(b,&good,15625000ULL,4096U,bad_lba)==-1);
        assert(!memcmp(b,prior,64));
    }
    memcpy(b,prior,64);
    assert(n71_s3e_ro_encode_one_sector(b,&good,15625000ULL,512U,0)==-1);
    assert(!memcmp(b,prior,64));
    memcpy(b,prior,64);
    assert(n71_s3e_ro_encode_one_sector(b,&good,15625001ULL,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    memcpy(b,prior,64);
    assert(n71_s3e_ro_encode_one_sector(b,&good,0,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    layout=good;layout.data_iova=0x40000000ULL;
    memcpy(b,prior,64);
    assert(n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    layout=good;layout.data_iova=0x40001000ULL; /* tag0 + 4KiB is NOT tag1 */
    assert(n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    layout=good;layout.data_iova=0x40801000ULL; /* unqualified offset in tag1 */
    assert(n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    layout=good;layout.data_iova=0x41000000ULL; /* tag2 not allocated */
    assert(n71_s3e_ro_encode_one_sector(b,&layout,15625000ULL,4096U,0)==-1);
    assert(!memcmp(b,prior,64));
    assert(n71_s3e_ro_encode_one_sector(NULL,&good,15625000ULL,4096U,0)==-1);
}

static void test_address_validation(void)
{
    unsigned char b[64], sentinel[64];
    struct n71_s3e_ro_io_layout x;
    unsigned long long *v;
    unsigned int i,j;
    memset(sentinel,0x73,64);
    assert(n71_s3e_ro_validate_layout(NULL)==-1);
    for(i=0;i<5;i++){
        x=good;v=&x.admin_sq_iova;v[i]=0;
        assert(n71_s3e_ro_validate_layout(&x)==-1);
        x=good;v=&x.admin_sq_iova;v[i]=0x80012001ULL;
        assert(n71_s3e_ro_validate_layout(&x)==-1);
        x=good;v=&x.admin_sq_iova;v[i]=1ULL<<36;
        assert(n71_s3e_ro_validate_layout(&x)==-1);
        for(j=0;j<i;j++){
            x=good;v=&x.admin_sq_iova;v[i]=v[j];
            assert(n71_s3e_ro_validate_layout(&x)==-1);
            memcpy(b,sentinel,64);
            assert(n71_s3e_ro_encode_one_sector(b,&x,15625000ULL,4096U,0)==-1);
            assert(!memcmp(b,sentinel,64));
            assert(n71_s3e_ro_encode_create_cq(b,&x)==-1);
            assert(!memcmp(b,sentinel,64));
            assert(n71_s3e_ro_encode_create_sq(b,&x)==-1);
            assert(!memcmp(b,sentinel,64));
        }
    }
    x=good;x.data_iova=(1ULL<<36)-4096ULL;
    assert(!n71_s3e_ro_validate_layout(&x));
    x.data_iova=(1ULL<<36);
    assert(n71_s3e_ro_validate_layout(&x)==-1);
    assert(n71_s3e_ro_encode_create_sq(NULL,&good)==-1);
    assert(n71_s3e_ro_encode_create_cq(NULL,&good)==-1);
}

int main(void)
{
    test_exact_wire_formats();
    test_address_validation();
    printf("N71_S3E_RO_IO_COMMAND_PLAN_PASS one_sector=4096 qid=1 nsze=15625000 queue_entries=16 no_hw_io=YES\n");
    return 0;
}
"""


class N71S3EReadOnlyIOPlanTests(unittest.TestCase):
    def test_real_portable_c_builder_compiles_and_runs(self):
        with tempfile.TemporaryDirectory(prefix="n71-io-plan-") as d:
            source = Path(d) / "plan.c"
            binary = Path(d) / "plan"
            source.write_text(HARNESS)
            cmd = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra",
                   "-Werror", "-I", str(PORT0),
                   str(source), "-o", str(binary)]
            built = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("N71_S3E_RO_IO_COMMAND_PLAN_PASS", result.stdout)

    def test_protocol_names_reconciled_against_running_kernel_nvme_headers(self):
        if KERNEL_NVME is None:
            self.skipTest("Optional external N71 kernel source not installed")
        for phrase in ("nvme_cmd_read", "nvme_admin_create_cq",
                       "nvme_admin_create_sq", "struct nvme_rw_command",
                       "struct nvme_create_cq", "struct nvme_create_sq",
                       "NVME_QUEUE_PHYS_CONTIG"):
            self.assertIn(phrase, KERNEL_NVME)
        for phrase in ("N71_RO_NVM_READ 0x02U",
                       "N71_RO_ADMIN_CREATE_CQ 0x05U",
                       "N71_RO_ADMIN_CREATE_SQ 0x01U",
                       "N71_RO_BLOCK_BYTES 4096U",
                       "N71_RO_PHYSICAL_NSZE 15625000ULL",
                       "N71_RO_IO_FLAG_UNQUALIFIED 0U"):
            self.assertIn(phrase, HEADER)

    def test_header_is_pure_and_nvm_read_remains_unwired(self):
        for forbidden in ("writel(", "writew(", "dma_map_single(",
                          "dma_unmap_single(", "msleep(", "request_mem_region(",
                          "printk(", "pr_info(", "blk_mq_start_request("):
            self.assertNotIn(forbidden, HEADER)
        self.assertIn("This is a pure 64-byte command encoder", HEADER)
        self.assertIn("They MUST", HEADER)
        self.assertIn("S8000 IO", HEADER)
        self.assertNotIn("n71_s3e_ro_encode_one_sector(", PILOT)
        self.assertNotIn("n71_s3e_ro_encode_create_cq(", PILOT)
        self.assertNotIn("n71_s3e_ro_encode_create_sq(", PILOT)
        owner = (PORT0 / "n71_s3e_admin_identify_once.h").read_text()
        self.assertIn('#include "n71_s3e_read_only_io_plan.h"', owner)
        self.assertIn("BUILD_BUG_ON(offsetof(struct nvme_rw_command, slba)!=40)", owner)
        self.assertIn("BUILD_BUG_ON(offsetof(struct nvme_create_sq, cqid)!=46)", owner)
        self.assertNotIn("n71_s3e_ro_encode_one_sector(", owner)
        self.assertNotIn("n71_s3e_ro_encode_create_cq(", owner)

if __name__ == "__main__":
    unittest.main()
