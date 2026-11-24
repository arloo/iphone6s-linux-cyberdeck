/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_LBA0_READ_RUNTIME_H
#define N71_S3E_LBA0_READ_RUNTIME_H
#include <linux/random.h>
#include "n71_s3e_lba0_read_once_core.h"
static struct {
    bool staged,prepared,attempted,submitted,cqe_seen,cqe_valid,cq_acked;
    bool data_arrived,guard_ok,quarantined;
    unsigned int cq_polls,data_polls,observed_status,changed_words;
    u64 witness_seed;
    struct n71_s3e_admin_cqe_fields cqe;
} n71_lba0_memory;
/* Unlike the stable live qualifier, an in-progress pre-BME invalidate may
 * show bit16 at NVMMU+4. Every other owner/root/CC/BME condition stays exact.
 * No inherited root or GPIO is changed, and no epoch has started. */
static int n71_lba0_invalidate_owned(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    if (!m || !ans_lba0_read_once || !ans_io_queue_once ||
        !n71_io_queue_memory.prepared || !n71_io_queue_memory.mapped ||
        !n71_admin_memory.prepared || !n71_admin_memory.dart_mapped ||
        !n71_ro_io_dma_memory.ready || n71_ro_io_dma_memory.quarantined ||
        READ_ONCE(n71_admin_dma_epoch_latched) || n71_unreleased ||
        !m->nvmmu || !n71_nvme_mmio || !n71_nvmmu_memory.dev ||
        !n71_nvmmu_memory.mapped[0] || !n71_nvmmu_memory.mapped[1] ||
        !n71_hmb_memory.page || !n71_hmb_memory.mapped ||
        !n71_storage_endpoint_ready(ctx)) return 0;
    return (n71_storage_root_read(ctx,4)&0xffffU)==2U &&
        (n71_storage_endpoint_read(ctx,4)&0xffffU)==2U &&
        !n71_admin_reg(0x14) && !n71_admin_reg(0x1c) &&
        readl(m->nvmmu)==1 &&
        n71_lba0_invalidate_value_valid(readl((u8 __iomem *)m->nvmmu+4)) &&
        readl((u8 __iomem *)m->nvmmu+8)==lower_32_bits(n71_nvmmu_memory.dma[0]) &&
        readl((u8 __iomem *)m->nvmmu+0x0c)==upper_32_bits(n71_nvmmu_memory.dma[0]) &&
        readl((u8 __iomem *)m->nvmmu+0x10)==lower_32_bits(n71_nvmmu_memory.dma[1]) &&
        readl((u8 __iomem *)m->nvmmu+0x14)==upper_32_bits(n71_nvmmu_memory.dma[1]) &&
        readl((u8 __iomem *)m->nvmmu+0x20)==1 &&
        readl((u8 __iomem *)m->nvmmu+0x24)==0xbc000000U &&
        readl((u8 __iomem *)m->nvmmu+0x28)==0xbc700000U &&
        readl((u8 __iomem *)m->nvmmu+0x2c)==(n71_hmb_memory.dma>>20) &&
        n71_admin_reg(0x1810)==0xbc000000U && !n71_admin_reg(0x1814) &&
        n71_admin_reg(0x1818)==SZ_8M;
}
static int n71_lba0_invalidate_pre_bme(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int i,value;
    if (!n71_lba0_invalidate_owned(ctx) ||
        readl((u8 __iomem *)m->nvmmu+4)) return -EPERM;
    /* Source-verified invalidate bit/offset; no root, control or SART write. */
    writel(0x10000U,(u8 __iomem *)m->nvmmu+4);
    for (i=0;i<1000;i++) {
        if (!n71_lba0_invalidate_owned(ctx)) return -3;
        value=readl((u8 __iomem *)m->nvmmu+4);
        if (!value) return n71_io_pre_bme(ctx) ? 0 : -3;
        if (value!=0x10000U) return -3;
        usleep_range(1000,1100);
    }
    return -3;
}
/* Only CPU shadow pages are temporary. All live DMA backing remains owned.
 * Stage tag1 before the first possible DMA epoch; never alter tag0. */
static int n71_lba0_read_prepare(void *ctx)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct n71_s3e_ro_foreign_range foreign[N71_RO_IO_FOREIGN_MAX];
    struct n71_s3e_ro_owned_frames frames;
    unsigned char *shadow_tcb=NULL,*shadow_sgl=NULL,*live_tcb,*slot;
    bool cpu_io[4]={0},cpu_tcb=false;
    unsigned int count,i;
    int rc=-EPERM;
    if (!ans_lba0_read_once || n71_lba0_memory.staged ||
        n71_lba0_memory.prepared || !n71_io_pre_bme(ctx) ||
        !n71_io_queue_memory.prepared ||
        !n71_lba0_mode_valid(1,ans_lba0_read_flags,ans_identify_once,
            ans_io_queue_once,ans_io_queue_delete_once,ans_io_queue_flags))
        return -EPERM;
    rc=n71_ro_io_dma_foreign_ranges(ctx,foreign,&count);
    if (rc) return rc;
    frames=(struct n71_s3e_ro_owned_frames){
        n71_admin_memory.dma[0],n71_admin_memory.dma[1],
        n71_ro_io_dma_memory.dma[0],n71_ro_io_dma_memory.dma[1],
        n71_ro_io_dma_memory.dma[2],n71_ro_io_dma_memory.dma[3]};
    if (n71_s3e_ro_verify_ownership(&frames,foreign,count)) return -EPERM;
    shadow_tcb=(void *)__get_free_page(GFP_KERNEL);
    if (!shadow_tcb) return -ENOMEM;
    rc=n71_ro_io_dma_claim_valid(virt_to_phys(shadow_tcb),foreign,count,4);
    if (rc) goto out;
    shadow_sgl=(void *)__get_free_page(GFP_KERNEL);
    if (!shadow_sgl) {rc=-ENOMEM;goto out;}
    rc=n71_ro_io_dma_claim_valid(virt_to_phys(shadow_sgl),foreign,count,4);
    if (rc || virt_to_phys(shadow_sgl)==virt_to_phys(shadow_tcb)) {
        rc=-EPERM;goto out;
    }
    /* Every four-page preimage must still be untouched before publication. */
    for (i=0;i<4;i++) {
        dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[i],
                               PAGE_SIZE,DMA_BIDIRECTIONAL);
        cpu_io[i]=true;
        if (memchr_inv(n71_ro_io_dma_memory.page[i],0,PAGE_SIZE)) {
            rc=-EPROTO;goto out;
        }
    }
    dma_sync_single_for_cpu(d,n71_nvmmu_memory.dma[0],
                           PAGE_SIZE,DMA_BIDIRECTIONAL);
    cpu_tcb=true;live_tcb=n71_nvmmu_memory.page[0];
    memcpy(shadow_tcb,live_tcb,PAGE_SIZE);
    memset(shadow_sgl,0,PAGE_SIZE);
    rc=n71_s3e_ro_stage_flatdma_tag1(shadow_tcb,shadow_sgl,&frames,&n71_io_layout);
    if (rc) {rc=-EPERM;goto out;}
    slot=live_tcb+N71_RO_TCB_TAG1_OFFSET;
    if (!n71_io_pre_bme(ctx) ||
        memcmp(live_tcb,shadow_tcb,N71_RO_TCB_TAG1_OFFSET) ||
        memchr_inv(slot,0,N71_RO_TCB_BYTES) ||
        memcmp(slot+N71_RO_TCB_BYTES,
               shadow_tcb+N71_RO_TCB_TAG1_OFFSET+N71_RO_TCB_BYTES,
               PAGE_SIZE-N71_RO_TCB_TAG1_OFFSET-N71_RO_TCB_BYTES)) {
        rc=-EPERM;goto out;
    }
    n71_lba0_memory.witness_seed=get_random_u64();
    if (!n71_lba0_memory.witness_seed) n71_lba0_memory.witness_seed=1;
    n71_lba0_mark(n71_ro_io_dma_memory.page[2],n71_lba0_memory.witness_seed);
    memcpy(n71_ro_io_dma_memory.page[3],shadow_sgl,PAGE_SIZE);
    for (i=0;i<4;i++) {
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[i],
                                  PAGE_SIZE,DMA_BIDIRECTIONAL);
        cpu_io[i]=false;
    }
    /* Latch before first device-visible TCB publication; retain on uncertainty. */
    n71_lba0_memory.staged=true;
    memcpy(slot,shadow_tcb+N71_RO_TCB_TAG1_OFFSET,4);
    memcpy(slot+8,shadow_tcb+N71_RO_TCB_TAG1_OFFSET+8,N71_RO_TCB_BYTES-8);
    dma_wmb();
    WRITE_ONCE(*(__le32 *)(slot+4),cpu_to_le32(1)); /* page count LAST */
    dma_sync_single_for_device(d,n71_nvmmu_memory.dma[0],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    cpu_tcb=false;dma_wmb();
    rc=n71_lba0_invalidate_pre_bme(ctx);
    if (rc) goto out;
    n71_lba0_memory.prepared=true;n71_lba0_memory.guard_ok=true;
    pr_info("n71-s3e-p0: LBA0_READ_PREPARED nsid=1 slba=0 blocks=1 bytes=4096 tag=1 flags=32 cc_off=1 bme_off=1 tag0_unchanged=YES payload_and_addresses_redacted=YES\n");
out:
    for (i=0;i<4;i++)
        if (cpu_io[i]) dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[i],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (cpu_tcb) dma_sync_single_for_device(d,n71_nvmmu_memory.dma[0],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (shadow_sgl) free_page((unsigned long)shadow_sgl);
    if (shadow_tcb) free_page((unsigned long)shadow_tcb);
    if (rc && n71_lba0_memory.staged) {
        n71_lba0_memory.quarantined=true;
        n71_ro_io_dma_memory.quarantined=true;n71_unreleased=true;
    }
    return rc;
}
static int n71_lba0_read_qualified(void *ctx)
{
    return ans_lba0_read_once && ans_lba0_read_flags==N71_LBA0_READ_FLAGS &&
        n71_lba0_memory.prepared && !n71_lba0_memory.quarantined &&
        n71_io_queue_memory.cq_created && n71_io_queue_memory.sq_created &&
        !n71_io_queue_memory.sq_delete_posted &&
        !n71_io_queue_memory.cq_delete_posted && n71_io_queue_qualified(ctx);
}
static int n71_lba0_submit(void *ctx,const unsigned char *command)
{
    struct device *d=n71_nvmmu_memory.dev;
    unsigned char *sq=n71_ro_io_dma_memory.page[0];
    unsigned char *cq=n71_ro_io_dma_memory.page[1];
    bool foreign;
    if (!n71_lba0_read_qualified(ctx) || n71_lba0_memory.submitted ||
        !n71_lba0_command_valid(command,&n71_io_layout,n71_admin_memory.nsze,
             n71_admin_memory.lba_bytes,ans_lba0_read_flags)) return -EPERM;
    dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[1],
                           PAGE_SIZE,DMA_BIDIRECTIONAL);
    foreign=!!memchr_inv(cq,0,sizeof(struct nvme_completion));
    dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[1],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (foreign) return -EPROTO; /* never clear a device-owned CQ */
    dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[0],
                           PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (memchr_inv(sq,0,N71_RO_CMD_BYTES)) {
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[0],
                                  PAGE_SIZE,DMA_BIDIRECTIONAL);
        return -EPROTO;
    }
    memcpy(sq,command,N71_RO_CMD_BYTES);
    dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[0],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_wmb();n71_lba0_memory.submitted=true; /* before possible DMA */
    n71_admin_write(0x1008,1); /* I/O QID1 SQ tail; only Read, exactly once */
    return 0;
}
static int n71_lba0_wait_cqe(void *ctx,unsigned int *observed,
        struct n71_s3e_admin_cqe_fields *fields)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct nvme_completion cqe,*slot=n71_ro_io_dma_memory.page[1];
    unsigned int i,status=0;
    bool seen=false;
    for (i=0;i<5000;i++) {
        dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[1],
                               PAGE_SIZE,DMA_BIDIRECTIONAL);
        status=le16_to_cpu(READ_ONCE(slot->status));
        if (status&1) {dma_rmb();memcpy(&cqe,slot,sizeof(cqe));seen=true;}
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[1],
                                  PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_lba0_memory.cq_polls++;
        if (seen || n71_admin_csts(ctx)!=1) break;
        usleep_range(1000,1100);
    }
    n71_lba0_memory.observed_status=status;*observed=status;
    if (!seen) return -ETIMEDOUT;
    *fields=(struct n71_s3e_admin_cqe_fields){
        le16_to_cpu(cqe.status),le16_to_cpu(cqe.command_id),
        le16_to_cpu(cqe.sq_id),le16_to_cpu(cqe.sq_head)};
    n71_lba0_memory.cqe=*fields;n71_lba0_memory.cqe_seen=true;
    return n71_admin_csts(ctx)==1 ? 0 : -EIO;
}
static int n71_lba0_ack_cq(void *ctx)
{
    if (!n71_lba0_read_qualified(ctx) || !n71_lba0_memory.cqe_seen ||
        n71_lba0_memory.cq_acked ||
        !n71_lba0_cqe_valid(n71_lba0_memory.observed_status,&n71_lba0_memory.cqe))
        return -EPROTO;
    n71_lba0_memory.cqe_valid=true;
    n71_admin_write(0x100c,1); /* only a validated I/O QID1 completion */
    n71_lba0_memory.cq_acked=true;
    return 0;
}
static int n71_lba0_wait_data(void *ctx)
{
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i,changed=0;
    int state;
    for (i=0;i<1000;i++) {
        dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[2],
                               PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_rmb();
        state=n71_lba0_data_state(n71_ro_io_dma_memory.page[2],
                                 n71_lba0_memory.witness_seed,&changed);
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[2],
                                  PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_lba0_memory.data_polls++;
        n71_lba0_memory.changed_words=changed;
        n71_lba0_memory.guard_ok=state>=0;
        if (state<0) return -EOVERFLOW;
        if (state==1) {n71_lba0_memory.data_arrived=true;return 0;}
        if (n71_admin_csts(ctx)!=1) return -EIO;
        usleep_range(1000,1100);
    }
    return -ENODATA;
}
static int n71_lba0_completed_safely(void)
{
    return n71_lba0_memory.submitted && n71_lba0_memory.cqe_valid &&
        n71_lba0_memory.cq_acked && n71_lba0_memory.data_arrived &&
        n71_lba0_memory.guard_ok;
}
static int n71_lba0_read_once(void *ctx)
{
    const struct n71_lba0_read_ops ops={
        .qualified=n71_lba0_read_qualified,.submit=n71_lba0_submit,
        .wait_cqe=n71_lba0_wait_cqe,.ack_cq=n71_lba0_ack_cq,.wait_data=n71_lba0_wait_data};
    struct n71_lba0_read_result r={0};
    int rc;
    if (!ans_lba0_read_once || n71_lba0_memory.attempted) return -EPERM;
    n71_lba0_memory.attempted=true;
    rc=n71_lba0_read_once_core(&ops,ctx,&n71_io_layout,n71_admin_memory.nsze,
            n71_admin_memory.lba_bytes,ans_lba0_read_flags,&r);
    pr_info("n71-s3e-p0: LBA0_READ_ONCE rc=%d submitted=%u cqe_seen=%u cqe_valid=%u cq_acked=%u data_arrived=%u guard_ok=%u changed_words=%u expected_words=%u status=%04x cq_polls=%u data_polls=%u nsid=1 slba=0 blocks=1 bytes=4096 io_qid=1 command_flags=%u tag=1 nvm_write_submitted=NO payload_redacted=YES dma_release_authorized=NO\n",
        rc,n71_lba0_memory.submitted,n71_lba0_memory.cqe_seen,r.completion_valid,r.cq_acked,
        r.data_arrived,n71_lba0_memory.guard_ok,n71_lba0_memory.changed_words,
        N71_LBA0_WORDS,n71_lba0_memory.observed_status,n71_lba0_memory.cq_polls,
        n71_lba0_memory.data_polls,ans_lba0_read_flags);
    if (rc) n71_lba0_memory.quarantined=true;
    return rc;
}
#endif
