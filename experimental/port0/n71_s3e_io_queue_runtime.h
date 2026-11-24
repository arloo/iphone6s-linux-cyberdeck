/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_IO_QUEUE_RUNTIME_H
#define N71_S3E_IO_QUEUE_RUNTIME_H
#include "n71_s3e_io_queue_once_core.h"
static const struct n71_s3e_ro_io_layout n71_io_layout = {
    .admin_sq_iova = N71_ADMIN_SQ_IOVA,
    .admin_cq_iova = N71_ADMIN_CQ_IOVA,
    .io_sq_iova = 0x80012000ULL,
    .io_cq_iova = 0x80013000ULL,
    .data_iova = N71_RO_READ_FLATDMA_TAG_CANDIDATE,
};
static struct {
    bool mapped, prepared, attempted;
    bool cq_posted, cq_created, sq_posted, sq_created;
} n71_io_queue_memory;
static int n71_io_queue_capable(void)
{
    return n71_io_queue_capability_valid(n71_admin_reg(0),
                                        n71_admin_reg(4), n71_admin_reg(8));
}
static int n71_io_pre_bme(void *ctx)
{
    return ans_io_queue_once && ans_identify_once &&
        n71_io_queue_flags_valid(ans_io_queue_flags) && n71_io_queue_capable() &&
        !READ_ONCE(n71_admin_dma_epoch_latched) && !n71_unreleased &&
        !n71_io_queue_memory.attempted && n71_admin_memory.prepared &&
        n71_admin_qualified(ctx) && !n71_admin_reg(0x14) &&
        !n71_admin_reg(0x1c) &&
        (n71_storage_root_read(ctx, 4) & 0xffffU) == 2 &&
        (n71_storage_endpoint_read(ctx, 4) & 0xffffU) == 2;
}
/* Validate/stage FOUR isolated shadow views. Publish to already owned
 * DART0 L2 only with CC/RDY/BME off, before the first possible DMA epoch.
 * Shadow pages are never device-visible. Future I/O backing stays pinned. */
static int n71_io_queue_prepare(void *ctx)
{
    unsigned char *shadow[4] = {0};
    bool cpu_owned[4] = {0};
    struct n71_s3e_ro_owned_frames frames;
    struct n71_s3e_ro_foreign_range foreign[N71_RO_IO_FOREIGN_MAX];
    struct device *d = n71_nvmmu_memory.dev;
    unsigned int count, sid, j;
    int rc;
    if (!n71_io_pre_bme(ctx) || n71_io_queue_memory.prepared ||
        n71_io_queue_memory.mapped) return -EPERM;
    rc = n71_ro_io_dma_alloc_pre_epoch(ctx);
    if (rc) return rc;
    rc = n71_ro_io_dma_foreign_ranges(ctx, foreign, &count);
    if (rc) return rc;
    frames.admin_sq_pa = n71_admin_memory.dma[0];
    frames.admin_cq_pa = n71_admin_memory.dma[1];
    frames.io_sq_pa = n71_ro_io_dma_memory.dma[0];
    frames.io_cq_pa = n71_ro_io_dma_memory.dma[1];
    frames.read_data_pa = n71_ro_io_dma_memory.dma[2];
    frames.read_sgl_pa = n71_ro_io_dma_memory.dma[3];
    for (sid = 0; sid < 4; sid++) {
        u64 pa;
        shadow[sid] = (void *)__get_free_page(GFP_KERNEL);
        if (!shadow[sid]) { rc = -ENOMEM; goto out; }
        pa = virt_to_phys(shadow[sid]);
        rc = n71_ro_io_dma_claim_valid(pa, foreign, count, 4);
        if (rc) goto out; /* no writes before owner exclusion */
        for (j = 0; j < sid; j++)
            if (pa == virt_to_phys(shadow[j])) { rc = -EBUSY; goto out; }
        dma_sync_single_for_cpu(d, n71_admin_memory.dma[4+sid],
                               PAGE_SIZE, DMA_BIDIRECTIONAL);
        memcpy(shadow[sid], n71_admin_memory.page[4+sid], PAGE_SIZE);
        dma_sync_single_for_device(d, n71_admin_memory.dma[4+sid],
                                  PAGE_SIZE, DMA_BIDIRECTIONAL);
    }
    rc = n71_s3e_ro_stage_io_queue_l2(shadow, &n71_io_layout,
                                     &frames, foreign, count);
    if (rc) { rc = -EPERM; goto out; }
    if (!n71_io_pre_bme(ctx)) { rc = -EPERM; goto out; }
    /* Revalidate all live preimages before the first L2 mutation. */
    for (sid = 0; sid < 4; sid++) {
        unsigned char *live = n71_admin_memory.page[4+sid];
        dma_sync_single_for_cpu(d, n71_admin_memory.dma[4+sid],
                               PAGE_SIZE, DMA_BIDIRECTIONAL);
        cpu_owned[sid] = true;
        if (n71_ro_get_le64(live+8U*16U) != (frames.admin_sq_pa|3ULL) ||
            n71_ro_get_le64(live+8U*17U) != (frames.admin_cq_pa|3ULL) ||
            n71_ro_get_le64(live+8U*18U) || n71_ro_get_le64(live+8U*19U)) {
            rc = -EPERM; goto out;
        }
    }
    /* From the first publish onward, uncertainty MUST retain backing. */
    n71_io_queue_memory.mapped = true;
    for (sid = 0; sid < 4; sid++) {
        memcpy(n71_admin_memory.page[4+sid], shadow[sid], PAGE_SIZE);
        dma_sync_single_for_device(d, n71_admin_memory.dma[4+sid],
                                  PAGE_SIZE, DMA_BIDIRECTIONAL);
        cpu_owned[sid] = false;
    }
    dma_wmb();
    rc = n71_admin_flush(ctx);
    if (rc) {
        n71_ro_io_dma_memory.quarantined = true;
        n71_unreleased = true;
        rc = -3; goto out;
    }
    n71_io_queue_memory.prepared = true;
    pr_info("n71-s3e-p0: IO_QUEUE_PREPARED streams=4 new_pages=4 depth=16 cc_off=1 bme_off=1 cmd_flags=%u data_read_still_disabled=YES addresses_redacted=YES\n",
            ans_io_queue_flags);
out:
    for (sid = 0; sid < 4; sid++) {
        if (cpu_owned[sid])
            dma_sync_single_for_device(d, n71_admin_memory.dma[4+sid],
                                      PAGE_SIZE, DMA_BIDIRECTIONAL);
        /* Only private CPU shadow pages, never mapped for device DMA. */
        if (shadow[sid]) free_page((unsigned long)shadow[sid]);
    }
    return rc;
}
static int n71_io_queue_qualified(void *ctx)
{
    return ans_io_queue_once && ans_identify_once &&
        n71_io_queue_flags_valid(ans_io_queue_flags) && n71_io_queue_capable() &&
        READ_ONCE(n71_admin_dma_epoch_latched) &&
        n71_io_queue_memory.mapped && n71_io_queue_memory.prepared &&
        n71_ro_io_dma_memory.ready && !n71_ro_io_dma_memory.quarantined &&
        n71_admin_memory.submitted && n71_admin_memory.completion_validated &&
        n71_admin_memory.cq_head_doorbell_written &&
        n71_admin_memory.data_arrived && n71_admin_memory.namespace_validated &&
        n71_admin_memory.nsze == N71_RO_PHYSICAL_NSZE &&
        n71_admin_memory.lba_bytes == N71_RO_BLOCK_BYTES &&
        n71_admin_qualified(ctx) && n71_admin_reg(0x14) == 0x460001U &&
        n71_admin_reg(0x1c) == 1 && (n71_admin_reg(0x0c) & 1) &&
        (n71_storage_root_read(ctx, 4) & 0xffffU) == 6 &&
        (n71_storage_endpoint_read(ctx, 4) & 0xffffU) == 6;
}
static int n71_io_queue_submit_admin(void *ctx,
        const unsigned char *command, unsigned int cid)
{
    struct device *d = n71_nvmmu_memory.dev;
    struct nvme_completion cqe, *slot;
    unsigned int i, status = 0;
    bool complete = false;
    if (!n71_io_queue_qualified(ctx) ||
        !n71_io_queue_command_valid(command, &n71_io_layout, ans_io_queue_flags, cid) ||
        (cid == 2 && n71_io_queue_memory.cq_posted) ||
        (cid == 3 && (!n71_io_queue_memory.cq_created || n71_io_queue_memory.sq_posted)))
        return -EPERM;
    slot = (struct nvme_completion *)n71_admin_memory.page[1] + cid-1;
    dma_sync_single_for_cpu(d, n71_admin_memory.dma[1], PAGE_SIZE, DMA_BIDIRECTIONAL);
    complete = !!memchr_inv(slot, 0, sizeof(*slot));
    dma_sync_single_for_device(d, n71_admin_memory.dma[1], PAGE_SIZE, DMA_BIDIRECTIONAL);
    if (complete) return -EPROTO; /* never erase/ack a foreign CQ slot */
    dma_sync_single_for_cpu(d, n71_admin_memory.dma[0], PAGE_SIZE, DMA_BIDIRECTIONAL);
    if (memchr_inv((u8 *)n71_admin_memory.page[0]+(cid-1)*64U, 0, 64U)) {
        dma_sync_single_for_device(d, n71_admin_memory.dma[0], PAGE_SIZE, DMA_BIDIRECTIONAL);
        return -EPROTO;
    }
    memcpy((u8 *)n71_admin_memory.page[0]+(cid-1)*64U, command, 64U);
    dma_sync_single_for_device(d, n71_admin_memory.dma[0], PAGE_SIZE, DMA_BIDIRECTIONAL);
    dma_wmb();
    n71_admin_write(0x1000, cid); /* ADMIN QID0 SQ tail: exactly 2, then 3 */
    if (cid == 2) n71_io_queue_memory.cq_posted = true;
    else n71_io_queue_memory.sq_posted = true;
    complete = false;
    for (i = 0; i < 5000; i++) {
        dma_sync_single_for_cpu(d, n71_admin_memory.dma[1], PAGE_SIZE, DMA_BIDIRECTIONAL);
        status = le16_to_cpu(READ_ONCE(slot->status));
        if (status & 1) { dma_rmb(); memcpy(&cqe, slot, sizeof(cqe)); complete = true; }
        dma_sync_single_for_device(d, n71_admin_memory.dma[1], PAGE_SIZE, DMA_BIDIRECTIONAL);
        if (complete || n71_admin_csts(ctx) != 1) break;
        usleep_range(1000, 1100);
    }
    pr_info("n71-s3e-p0: IO_QUEUE_ADMIN_COMPLETION cid=%u opcode=%u present=%u status=%04x polls=%u admin_qid=0 no_nvm_io=YES\n",
            cid, command[0], complete, status, i+1);
    if (!complete) return -ETIMEDOUT;
    if (n71_admin_csts(ctx) != 1 ||
        !n71_io_queue_cqe_valid(status,
            &(const struct n71_s3e_admin_cqe_fields){
                .status=le16_to_cpu(cqe.status), .command_id=le16_to_cpu(cqe.command_id),
                .sq_id=le16_to_cpu(cqe.sq_id), .sq_head=le16_to_cpu(cqe.sq_head)}, cid)) {
        pr_err("n71-s3e-p0: IO_QUEUE_CQE_REJECTED cid=%u no_cq_head_write=YES quarantine=YES\n", cid);
        return -EIO;
    }
    n71_admin_write(0x1004, cid); /* Ack only the validated ADMIN completion. */
    if (cid == 2) n71_io_queue_memory.cq_created = true;
    else n71_io_queue_memory.sq_created = true;
    return 0;
}
static int n71_io_queue_create_once(void *ctx)
{
    const struct n71_io_queue_once_ops ops = {
        .qualified=n71_io_queue_qualified, .submit_admin=n71_io_queue_submit_admin,
    };
    struct n71_io_queue_once_result r = {0};
    int rc;
    if (!ans_io_queue_once || n71_io_queue_memory.attempted) return -EPERM;
    n71_io_queue_memory.attempted = true;
    rc = n71_io_queue_once_core(&ops, ctx, &n71_io_layout, ans_io_queue_flags, &r);
    pr_info("n71-s3e-p0: IO_QUEUE_ONCE rc=%d cq_attempted=%u cq_posted=%u cq_valid=%u sq_attempted=%u sq_posted=%u sq_valid=%u command_flags=%u nvm_read_submitted=NO nvm_write_submitted=NO dma_release_authorized=NO\n",
            rc,r.cq_attempted,n71_io_queue_memory.cq_posted,r.cq_validated,
            r.sq_attempted,n71_io_queue_memory.sq_posted,r.sq_validated,ans_io_queue_flags);
    return rc;
}
#endif
