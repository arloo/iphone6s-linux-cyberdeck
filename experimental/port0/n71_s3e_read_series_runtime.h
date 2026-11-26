/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_READ_SERIES_RUNTIME_H
#define N71_S3E_READ_SERIES_RUNTIME_H
#include "n71_s3e_read_series_core.h"
#if N71_GPT_FULL_PLAN
#include "../storage/n71-gpt-full-core.h"
#endif
/* 0..7: distinct DMA data/SGL pairs. 8..11: CPU-only immutable snapshots.
 * Every allocation is retained through the boot; no post-epoch reuse. */
static struct {
    void *page[N71_READ_SERIES_PAGES];
    dma_addr_t dma[N71_READ_SERIES_DMA_PAGES];
    bool mapped[N71_READ_SERIES_DMA_PAGES];
    bool prepared,staged,attempted,quarantined,stability_failed;
    bool seen[N71_READ_SERIES_COUNT],valid[N71_READ_SERIES_COUNT],acked[N71_READ_SERIES_COUNT],data_arrived[N71_READ_SERIES_COUNT],guard_ok[N71_READ_SERIES_COUNT],snapshot_valid[N71_READ_SERIES_COUNT];
    bool lba0_equal,lba1_equal,series_ok,retained_stable;
#if N71_GPT_FULL_PLAN
    bool gpt_crc_ok;
#endif
    unsigned int issued,completed,cq_polls[N71_READ_SERIES_COUNT],data_polls[N71_READ_SERIES_COUNT],status[N71_READ_SERIES_COUNT],changed[N71_READ_SERIES_COUNT];
    u64 seed[N71_READ_SERIES_COUNT];
    struct n71_s3e_admin_cqe_fields cqe[N71_READ_SERIES_COUNT];
} n71_read_series_memory;
static int n71_read_series_claim(u64 pa,
        const struct n71_s3e_ro_foreign_range *foreign,
        unsigned int count,unsigned int previous)
{
    unsigned int j;
    int rc=n71_ro_io_dma_claim_valid(pa,foreign,count,4);
    if (rc) return rc;
    for (j=0;j<previous;j++) {
        u64 old;
        if (!n71_read_series_memory.page[j]) return -EPERM;
        old=virt_to_phys(n71_read_series_memory.page[j]);
        if (pa<old+PAGE_SIZE && old<pa+PAGE_SIZE) return -EBUSY;
    }
    return 0;
}
static int n71_read_series_prepare(void *ctx)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct n71_s3e_ro_foreign_range foreign[64];
    struct n71_read_series_frames frames;
    unsigned char *shadow[N71_READ_SERIES_COUNT+1U]={0},*sgl[N71_READ_SERIES_COUNT],*live,*slot;
    bool cpu[N71_READ_SERIES_DMA_PAGES]={0},cpu_tcb=false;
    unsigned int count,i,j;
    int rc=-EPERM;
    BUILD_BUG_ON(N71_READ_SERIES_COUNT!=(N71_GPT_FULL_PLAN ? 5U : 4U));
    BUILD_BUG_ON(N71_READ_SERIES_COUNT>=N71_RO_Q_ENTRIES);
    if (!n71_series_enabled() || n71_read_series_memory.staged ||
        n71_read_series_memory.prepared || !n71_io_pre_bme(ctx) ||
        !n71_io_queue_memory.prepared ||
        !n71_read_series_mode_valid(1,n71_series_flags(),ans_identify_once,
            ans_io_queue_once,ans_io_queue_delete_once,ans_io_queue_flags,
            ans_lba0_read_once)) return -EPERM;
    rc=n71_ro_io_dma_foreign_ranges(ctx,foreign,&count);
    if (rc) return rc;
    for (i=0;i<N71_READ_SERIES_PAGES;i++) {
        u64 pa;
        if (n71_read_series_memory.page[i]) {rc=-EPERM;goto out;}
        n71_read_series_memory.page[i]=(void *)__get_free_page(GFP_KERNEL);
        if (!n71_read_series_memory.page[i]) {rc=-ENOMEM;goto out;}
        pa=virt_to_phys(n71_read_series_memory.page[i]);
        rc=n71_read_series_claim(pa,foreign,count,i);
        if (rc) goto out; /* ownership before any zero/write */
        memset(n71_read_series_memory.page[i],0,PAGE_SIZE);
        if (i<N71_READ_SERIES_DMA_PAGES) {
            n71_read_series_memory.dma[i]=dma_map_single(d,
                n71_read_series_memory.page[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
            if (dma_mapping_error(d,n71_read_series_memory.dma[i])) {
                rc=-EIO;goto out;
            }
            n71_read_series_memory.mapped[i]=true;
            if ((u64)n71_read_series_memory.dma[i]!=pa) {rc=-EPERM;goto out;}
        }
    }
    /* Base I/O and admin SQ/CQ are foreign to all new DMA frames. */
    if (count+6U>ARRAY_SIZE(foreign)) {rc=-E2BIG;goto out;}
    for (i=0;i<4;i++) {
        foreign[count+i].pa=n71_ro_io_dma_memory.dma[i];
        foreign[count+i].bytes=PAGE_SIZE;
    }
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        frames.data[i]=n71_read_series_memory.dma[2*i];
        frames.sgl[i]=n71_read_series_memory.dma[2*i+1];
    }
    foreign[count+4].pa=n71_admin_memory.dma[0];
    foreign[count+4].bytes=PAGE_SIZE;
    foreign[count+5].pa=n71_admin_memory.dma[1];
    foreign[count+5].bytes=PAGE_SIZE;
    count+=6;
    for (i=0;i<N71_READ_SERIES_COUNT+1U;i++) {
        u64 pa;
        shadow[i]=(void *)__get_free_page(GFP_KERNEL);
        if (!shadow[i]) {rc=-ENOMEM;goto out;}
        pa=virt_to_phys(shadow[i]);
        rc=n71_read_series_claim(pa,foreign,count,N71_READ_SERIES_PAGES);
        if (rc) goto out;
        for (j=0;j<i;j++)
            if (pa==virt_to_phys(shadow[j])) {rc=-EBUSY;goto out;}
        if (i) {memset(shadow[i],0,PAGE_SIZE);sgl[i-1]=shadow[i];}
    }
    dma_sync_single_for_cpu(d,n71_nvmmu_memory.dma[0],
                           PAGE_SIZE,DMA_BIDIRECTIONAL);
    cpu_tcb=true;live=n71_nvmmu_memory.page[0];
    memcpy(shadow[0],live,PAGE_SIZE);
    rc=n71_read_series_stage(shadow[0],sgl,&frames,foreign,count);
    if (rc) {rc=-EPERM;goto out;}
    for (i=0;i<N71_READ_SERIES_DMA_PAGES;i++) {
        dma_sync_single_for_cpu(d,n71_read_series_memory.dma[i],
                               PAGE_SIZE,DMA_BIDIRECTIONAL);
        cpu[i]=true;
        if (memchr_inv(n71_read_series_memory.page[i],0,PAGE_SIZE)) {
            rc=-EPROTO;goto out;
        }
    }
    /* Preserve tag0 and all unused slots; every selected tag must remain zero. */
    if (!n71_io_pre_bme(ctx) ||
        memcmp(live,shadow[0],N71_RO_TCB_BYTES) ||
        memchr_inv(live+N71_RO_TCB_BYTES,0,N71_READ_SERIES_COUNT*N71_RO_TCB_BYTES) ||
        memcmp(live+(N71_READ_SERIES_COUNT+1U)*N71_RO_TCB_BYTES,shadow[0]+(N71_READ_SERIES_COUNT+1U)*N71_RO_TCB_BYTES,
               PAGE_SIZE-(N71_READ_SERIES_COUNT+1U)*N71_RO_TCB_BYTES)) {rc=-EPERM;goto out;}
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        n71_read_series_memory.seed[i]=get_random_u64();
        if (!n71_read_series_memory.seed[i]) n71_read_series_memory.seed[i]=i+1U;
        n71_lba0_mark(n71_read_series_memory.page[2*i],
                      n71_read_series_memory.seed[i]);
        memcpy(n71_read_series_memory.page[2*i+1],sgl[i],PAGE_SIZE);
    }
    for (i=0;i<N71_READ_SERIES_DMA_PAGES;i++) {
        dma_sync_single_for_device(d,n71_read_series_memory.dma[i],
                                  PAGE_SIZE,DMA_BIDIRECTIONAL);
        cpu[i]=false;
    }
    n71_read_series_memory.staged=true; /* retain from first publication */
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        slot=live+(i+1U)*N71_RO_TCB_BYTES;
        memcpy(slot,shadow[0]+(i+1U)*N71_RO_TCB_BYTES,4);
        memcpy(slot+8,shadow[0]+(i+1U)*N71_RO_TCB_BYTES+8,N71_RO_TCB_BYTES-8);
    }
    dma_wmb();
    for (i=0;i<N71_READ_SERIES_COUNT;i++)
        WRITE_ONCE(*(__le32 *)(live+(i+1U)*N71_RO_TCB_BYTES+4),cpu_to_le32(1));
    dma_sync_single_for_device(d,n71_nvmmu_memory.dma[0],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    cpu_tcb=false;dma_wmb();
    rc=n71_lba0_invalidate_pre_bme(ctx); /* same owned pre-BME flush contract */
    if (rc) goto out;
    n71_read_series_memory.prepared=true;
#if N71_GPT_FULL_PLAN
    pr_info("n71-s3e-p0: GPT_FULL_PREPARED count=5 plan=1,2,3,4,5 tags=1,2,3,4,5 fresh_DMA_pages=10 CPU_snapshots=5 cc_off=1 bme_off=1 tag0_unchanged=YES addresses_redacted=YES\n");
#else
    pr_info("n71-s3e-p0: READ_SERIES_PREPARED count=4 plan=0,1,0,1 tags=1,2,3,4 fresh_DMA_pages=8 CPU_snapshots=4 cc_off=1 bme_off=1 tag0_unchanged=YES addresses_redacted=YES\n");
#endif
out:
    if (cpu_tcb) dma_sync_single_for_device(d,n71_nvmmu_memory.dma[0],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    for (i=0;i<N71_READ_SERIES_DMA_PAGES;i++)
        if (cpu[i]) dma_sync_single_for_device(d,n71_read_series_memory.dma[i],
                              PAGE_SIZE,DMA_BIDIRECTIONAL);
    for (i=0;i<N71_READ_SERIES_COUNT+1U;i++)
        if (shadow[i]) free_page((unsigned long)shadow[i]); /* never DMA mapped */
    if (rc) {
        n71_read_series_memory.quarantined=true;
        n71_ro_io_dma_memory.quarantined=true;n71_unreleased=true;
    }
    return rc;
}
static int n71_read_series_running(void *ctx)
{
    return n71_series_enabled() && n71_series_flags()==N71_LBA0_READ_FLAGS &&
        n71_read_series_memory.prepared && !n71_read_series_memory.quarantined &&
        n71_io_queue_memory.cq_created && n71_io_queue_memory.sq_created &&
        !n71_io_queue_memory.sq_delete_posted &&
        !n71_io_queue_memory.cq_delete_posted && n71_io_queue_qualified(ctx);
}
static int n71_read_series_qualified(void *ctx,unsigned int step)
{
    return step<N71_READ_SERIES_COUNT && step==n71_read_series_memory.issued &&
        step==n71_read_series_memory.completed && n71_read_series_running(ctx);
}
static int n71_read_series_submit(void *ctx,unsigned int step,
        const unsigned char *command)
{
    struct device *d=n71_nvmmu_memory.dev;
    unsigned char *sq;
    struct nvme_completion *cq;
    bool foreign;
    if (!n71_read_series_qualified(ctx,step) ||
        !n71_read_pair_command_valid(command,step,&n71_io_layout,
             n71_admin_memory.nsze,n71_admin_memory.lba_bytes,n71_series_flags(),n71_series_base()))
        return -EPERM;
    sq=(u8 *)n71_ro_io_dma_memory.page[0]+step*64U;
    cq=(struct nvme_completion *)n71_ro_io_dma_memory.page[1]+step;
    dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
    foreign=!!memchr_inv(cq,0,sizeof(*cq));
    dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (foreign) return -EPROTO;
    dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    if (memchr_inv(sq,0,64)) {
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
        return -EPROTO;
    }
    memcpy(sq,command,64);
    dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_wmb();n71_read_series_memory.issued++; /* before the only possible DMA */
    n71_admin_write(0x1008,step+1U);
    return 0;
}
static int n71_read_series_wait_cqe(void *ctx,unsigned int step,
        unsigned int *observed,struct n71_s3e_admin_cqe_fields *v)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct nvme_completion copy,*slot;
    unsigned int i,status=0;
    bool seen=false;
    if (step>=N71_READ_SERIES_COUNT) return -EPERM;
    slot=(struct nvme_completion *)n71_ro_io_dma_memory.page[1]+step;
    for (i=0;i<5000;i++) {
        dma_sync_single_for_cpu(d,n71_ro_io_dma_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        status=le16_to_cpu(READ_ONCE(slot->status));
        if (status&1) {dma_rmb();memcpy(&copy,slot,sizeof(copy));seen=true;}
        dma_sync_single_for_device(d,n71_ro_io_dma_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_read_series_memory.cq_polls[step]++;
        if (seen || n71_admin_csts(ctx)!=1) break;
        usleep_range(1000,1100);
    }
    n71_read_series_memory.status[step]=status;*observed=status;
    if (!seen) return -ETIMEDOUT;
    *v=(struct n71_s3e_admin_cqe_fields){le16_to_cpu(copy.status),
        le16_to_cpu(copy.command_id),le16_to_cpu(copy.sq_id),le16_to_cpu(copy.sq_head)};
    n71_read_series_memory.cqe[step]=*v;n71_read_series_memory.seen[step]=true;
    return n71_admin_csts(ctx)==1 ? 0 : -EIO;
}
static int n71_read_series_ack(void *ctx,unsigned int step)
{
    if (step>=N71_READ_SERIES_COUNT || !n71_read_series_running(ctx) ||
        n71_read_series_memory.acked[step] || !n71_read_series_memory.seen[step] ||
        !n71_read_series_cqe_valid(n71_read_series_memory.status[step],
                                    &n71_read_series_memory.cqe[step],step))
        return -EPROTO;
    n71_read_series_memory.valid[step]=true;
    n71_admin_write(0x100c,step+1U);
    n71_read_series_memory.acked[step]=true;return 0;
}
static int n71_read_series_wait_data(void *ctx,unsigned int step)
{
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i,changed=0;
    int state=-1;
    if (step>=N71_READ_SERIES_COUNT) return -EPERM;
    for (i=0;i<1000;i++) {
        dma_sync_single_for_cpu(d,n71_read_series_memory.dma[2*step],PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_rmb();
        state=n71_lba0_data_state(n71_read_series_memory.page[2*step],
                                  n71_read_series_memory.seed[step],&changed);
        dma_sync_single_for_device(d,n71_read_series_memory.dma[2*step],PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_read_series_memory.data_polls[step]++;
        n71_read_series_memory.changed[step]=changed;
        n71_read_series_memory.guard_ok[step]=state>=0;
        if (state<0) return -EOVERFLOW;
        if (state==1) {n71_read_series_memory.data_arrived[step]=true;return 0;}
        if (n71_admin_csts(ctx)!=1) return -EIO;
        usleep_range(1000,1100);
    }
    return -ENODATA;
}
static int n71_read_series_snapshot(void *ctx,unsigned int step)
{
    struct device *d=n71_nvmmu_memory.dev;
    (void)ctx;
    if (step>=N71_READ_SERIES_COUNT || n71_read_series_memory.snapshot_valid[step] ||
        !n71_read_series_memory.valid[step] || !n71_read_series_memory.acked[step] ||
        !n71_read_series_memory.data_arrived[step] ||
        !n71_read_series_memory.guard_ok[step]) return -EPERM;
    dma_sync_single_for_cpu(d,n71_read_series_memory.dma[2*step],PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_rmb();
    memcpy(n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES+step],
           n71_read_series_memory.page[2*step],N71_RO_BLOCK_BYTES);
    dma_sync_single_for_device(d,n71_read_series_memory.dma[2*step],PAGE_SIZE,DMA_BIDIRECTIONAL);
    n71_read_series_memory.snapshot_valid[step]=true;
    n71_read_series_memory.completed=step+1U;
    pr_info("n71-s3e-p0: READ_SERIES_STEP index=%u lba=%u tag=%u cid=%u sqid=1 head=%u status=%04x cqe_valid=1 data_arrived=1 guard_ok=1 changed_words=%u snapshot_private=YES payload_redacted=YES\n",
        step,n71_read_pair_lba(n71_series_base(),step),step+1U,step+1U,step+1U,
        n71_read_series_memory.status[step],n71_read_series_memory.changed[step]);
    return 0;
}
static int n71_read_series_stable(void *ctx,unsigned int count)
{
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i,changed;
    bool same,guard;
    (void)ctx;
    if (!count || count>N71_READ_SERIES_COUNT || count>n71_read_series_memory.completed) return -EPERM;
    for (i=0;i<count;i++) {
        if (!n71_read_series_memory.snapshot_valid[i]) return -EPERM;
        dma_sync_single_for_cpu(d,n71_read_series_memory.dma[2*i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_rmb();
        same=!memcmp(n71_read_series_memory.page[2*i],
                     n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES+i],N71_RO_BLOCK_BYTES);
        guard=n71_lba0_data_state(n71_read_series_memory.page[2*i],
                                  n71_read_series_memory.seed[i],&changed)==1;
        dma_sync_single_for_device(d,n71_read_series_memory.dma[2*i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        guard=guard && !memchr_inv((u8 *)n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES+i]+N71_RO_BLOCK_BYTES,
                                  0,PAGE_SIZE-N71_RO_BLOCK_BYTES);
        if (!same || !guard) {
            n71_read_series_memory.stability_failed=true;
            return -EUCLEAN;
        }
    }
    return n71_read_series_memory.stability_failed ? -EUCLEAN : 0;
}
static int n71_read_series_compare(void *ctx)
{
    (void)ctx;
    if (n71_read_series_memory.completed!=N71_READ_SERIES_COUNT) return -EPERM;
#if N71_GPT_FULL_PLAN
    {
        const unsigned char *pages[4];unsigned int i;
        for(i=0;i<4;i++)pages[i]=n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES+1U+i];
        n71_read_series_memory.gpt_crc_ok=n71_gpt_full_crc_valid(
            n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES],pages);
        return n71_read_series_memory.gpt_crc_ok ? 0 : -EUCLEAN;
    }
#else
    n71_read_series_memory.lba0_equal=!memcmp(n71_read_series_memory.page[8],
                                n71_read_series_memory.page[10],N71_RO_BLOCK_BYTES);
    n71_read_series_memory.lba1_equal=!memcmp(n71_read_series_memory.page[9],
                                n71_read_series_memory.page[11],N71_RO_BLOCK_BYTES);
    return n71_read_series_memory.lba0_equal && n71_read_series_memory.lba1_equal ?
        0 : -EUCLEAN;
#endif
}
static int n71_read_series_completed_safely(void)
{
    return n71_read_series_memory.series_ok &&
        n71_read_series_memory.completed==N71_READ_SERIES_COUNT &&
        !n71_read_series_memory.stability_failed &&
#if N71_GPT_FULL_PLAN
        n71_read_series_memory.gpt_crc_ok;
#else
        n71_read_series_memory.lba0_equal && n71_read_series_memory.lba1_equal;
#endif
}
static int n71_read_series_once(void *ctx)
{
    const struct n71_read_series_ops ops={
        .qualified=ans_ro_block_once ? n71_ro_block_qualified : n71_read_series_qualified,
        .submit=n71_read_series_submit,
        .wait_cqe=n71_read_series_wait_cqe,.ack_cq=n71_read_series_ack,
        .wait_data=n71_read_series_wait_data,.snapshot=n71_read_series_snapshot,
        .stable=ans_ro_block_once ? n71_ro_block_stable : n71_read_series_stable,
        .compare_pairs=n71_read_series_compare};
    struct n71_read_series_result r={0};
    int rc;
    unsigned int i;
    if (!n71_series_enabled() || n71_read_series_memory.attempted) return -EPERM;
    n71_read_series_memory.attempted=true;
    rc=n71_read_pair_core(&ops,ctx,&n71_io_layout,n71_admin_memory.nsze,
            n71_admin_memory.lba_bytes,n71_series_flags(),&r,n71_series_base());
    n71_read_series_memory.series_ok=!rc;
    for (i=0;i<n71_read_series_memory.issued && i<N71_READ_SERIES_COUNT;i++)
        pr_info("n71-s3e-p0: READ_SERIES_STATUS index=%u lba=%u tag=%u cqe_seen=%u status=%04x cqe_valid=%u cq_acked=%u data_arrived=%u guard_ok=%u changed_words=%u cq_polls=%u data_polls=%u payload_redacted=YES\n",
            i,n71_read_pair_lba(n71_series_base(),i),i+1U,n71_read_series_memory.seen[i],
            n71_read_series_memory.status[i],n71_read_series_memory.valid[i],
            n71_read_series_memory.acked[i],n71_read_series_memory.data_arrived[i],
            n71_read_series_memory.guard_ok[i],n71_read_series_memory.changed[i],
            n71_read_series_memory.cq_polls[i],n71_read_series_memory.data_polls[i]);
    pr_info("n71-s3e-p0: READ_SERIES_ONCE rc=%d issued=%u accepted=%u snapshots=%u stability_checks=%u lba0_equal=%u lba1_equal=%u prior_buffers_unchanged=%u unique_tags=%u no_buffer_reuse=YES flags=%u nvm_write_submitted=NO payload_and_hashes_redacted=YES dma_release_authorized=NO\n",
        rc,n71_read_series_memory.issued,r.accepted,r.snapshotted,r.stability_checks,
        n71_read_series_memory.lba0_equal,n71_read_series_memory.lba1_equal,
        !n71_read_series_memory.stability_failed,N71_READ_SERIES_COUNT,n71_series_flags());
#if N71_GPT_FULL_PLAN
    pr_info("n71-s3e-p0: GPT_FULL_ONCE rc=%d issued=%u accepted=%u snapshots=%u stability_checks=%u header_and_array_crc_ok=%u unique_tags=5 pair_equality_tested=NO no_buffer_reuse=YES writes=NO DMA_release=NO\n",
        rc,n71_read_series_memory.issued,r.accepted,r.snapshotted,r.stability_checks,n71_read_series_memory.gpt_crc_ok);
#endif
    if (rc) n71_read_series_memory.quarantined=true;
    return rc;
}
/* RAM-only after-core witness. No status, doorbell, reset, root or cleanup
 * writes; unchanged samples NEVER prove DMA quiescence or release rights. */
static void n71_read_series_observe_retained_ro(void *ctx)
{
    unsigned int i,samples=0;
    bool unchanged=true;
    if (!n71_series_enabled() || !n71_read_series_memory.completed) return;
    for (i=0;i<5;i++) {
        if (n71_read_series_stable(ctx,n71_read_series_memory.completed)) unchanged=false;
        samples++;
        if (i<4) usleep_range(50000,51000);
    }
    n71_read_series_memory.retained_stable=unchanged &&
        !n71_read_series_memory.stability_failed;
    pr_info("n71-s3e-p0: READ_SERIES_RETAINED_RO samples=%u checked_reads=%u unchanged=%u interval_us=50000 no_hardware_commands=YES dma_quiescence_proven=NO dma_release_authorized=NO\n",
        samples,n71_read_series_memory.completed,n71_read_series_memory.retained_stable);
}
#endif
