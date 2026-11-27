/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_BLOCK_RUNTIME_H
#define N71_S3E_RO_BLOCK_RUNTIME_H
/* The init thread owns MMIO/context for the whole transaction. The kernel
 * client submits synchronous bios from another thread; submit_bio merely
 * authenticates/queues one bio. No MMIO or sleeping in that callback. */
static struct {
    struct gendisk *disk;
    struct bio *bio[N71_READ_SERIES_COUNT],*pending_bio;
    void *target[N71_READ_SERIES_COUNT]; /* pre-epoch CPU-only, never mapped or in any TCB/SGL */
    struct task_struct *client;
    struct completion request_ready;
    spinlock_t lock;
    struct n71_ro_block_flow flow;
    unsigned int rejected,client_completed;
    int major,client_rc;
    bool prepared,registered,removed,pairs_equal,passed;
#if N71_GPT_FULL_PLAN
    bool gpt_crc_ok;
#endif
} n71_ro_block_memory;
static bool n71_ro_block_content_valid(void)
{
#if N71_GPT_FULL_PLAN
    return n71_ro_block_memory.gpt_crc_ok;
#else
    return n71_ro_block_memory.pairs_equal;
#endif
}
#include "n71_s3e_ro_probe_runtime.h"
static void n71_ro_block_submit_bio(struct bio *bio)
{
    struct n71_ro_block_request r={
        .sector=bio->bi_iter.bi_sector,.is_read=bio_op(bio)==REQ_OP_READ,
        .bytes=bio->bi_iter.bi_size,
    };
    struct bio_vec v;
    struct bvec_iter iter;
    unsigned long irq;
    unsigned int step;
    bool accepted=false;
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    step=n71_ro_block_memory.flow.admitted;
    r.trusted_bio=step<N71_READ_SERIES_COUNT && bio==n71_ro_block_memory.bio[step];
    bio_for_each_segment(v,bio,iter) {
        r.segments++;
        if (r.segments==1U) {
            r.offset=v.bv_offset;
            r.trusted_page=step<N71_READ_SERIES_COUNT && v.bv_len==4096U &&
                v.bv_page==virt_to_page(n71_ro_block_memory.target[step]);
        }
    }
    if (!n71_ro_block_memory.pending_bio &&
        !n71_ro_block_pair_admit(&n71_ro_block_memory.flow,&r,n71_series_base())) {
        n71_ro_block_memory.pending_bio=bio;accepted=true;
    } else n71_ro_block_memory.rejected++;
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
    if (accepted) complete(&n71_ro_block_memory.request_ready);
    else bio_io_error(bio); /* includes every Write/flush/discard/probe */
}
static int n71_ro_block_open(struct gendisk *disk,blk_mode_t mode)
{
    (void)disk;(void)mode;
    return -EACCES; /* no userspace opener, automounter or partition tool */
}
static const struct block_device_operations n71_ro_block_fops={
    .owner=THIS_MODULE,.submit_bio=n71_ro_block_submit_bio,.open=n71_ro_block_open,
};
/* Software objects may be released only after the client is joined and
 * pending bio completed. No DMA/TCB/SGL/snapshot/target frame is freed. */
static void n71_ro_block_release_software(void)
{
    unsigned int i;
    for (i=0;i<N71_READ_SERIES_COUNT;i++)
        if (n71_ro_block_memory.bio[i]) {
            bio_put(n71_ro_block_memory.bio[i]);
            n71_ro_block_memory.bio[i]=NULL;
        }
    if (n71_ro_block_memory.registered && !n71_ro_block_memory.removed) {
        del_gendisk(n71_ro_block_memory.disk);
        n71_ro_block_memory.removed=true;
    }
    if (n71_ro_block_memory.disk) {
        put_disk(n71_ro_block_memory.disk);n71_ro_block_memory.disk=NULL;
    }
    if (n71_ro_block_memory.major>0) {
        unregister_blkdev(n71_ro_block_memory.major,"n71nand_ro");
        n71_ro_block_memory.major=0;
    }
}
static int n71_ro_block_prepare(void *ctx)
{
    struct n71_s3e_ro_foreign_range foreign[64];
    struct queue_limits lim={
        .logical_block_size=4096,.physical_block_size=4096,
        /* This 16KiB-page kernel requires max_hw_sectors>=PAGE_SECTORS.
         * max_dev_sectors and the independent admission cap are 4KiB. */
        .max_hw_sectors=PAGE_SIZE>>9,.max_dev_sectors=8,
        .max_segments=1,.max_segment_size=PAGE_SIZE,
    };
    unsigned int count,i,j;
    int rc=-EPERM;
    if (!ans_ro_block_once || n71_ro_block_memory.prepared ||
        !n71_io_pre_bme(ctx) || !n71_read_series_memory.prepared ||
        n71_read_series_memory.quarantined) return -EPERM;
    spin_lock_init(&n71_ro_block_memory.lock);
    init_completion(&n71_ro_block_memory.request_ready);
    n71_ro_probe_prepare();
    rc=n71_ro_io_dma_foreign_ranges(ctx,foreign,&count);
    if (rc) goto fail;
    if (count+6U>ARRAY_SIZE(foreign)) {rc=-E2BIG;goto fail;}
    for (i=0;i<4U;i++) foreign[count+i]=(struct n71_s3e_ro_foreign_range){
        n71_ro_io_dma_memory.dma[i],PAGE_SIZE};
    for (i=0;i<2U;i++) foreign[count+4U+i]=(struct n71_s3e_ro_foreign_range){
        n71_admin_memory.dma[i],PAGE_SIZE};
    count+=6U;
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        u64 pa;
        n71_ro_block_memory.target[i]=(void *)__get_free_page(GFP_KERNEL);
        if (!n71_ro_block_memory.target[i]) {rc=-ENOMEM;goto fail;}
        pa=virt_to_phys(n71_ro_block_memory.target[i]);
        rc=n71_read_series_claim(pa,foreign,count,N71_READ_SERIES_PAGES);
        if (rc) goto fail;
        for (j=0;j<i;j++)
            if (pa==virt_to_phys(n71_ro_block_memory.target[j])) {
                rc=-EBUSY;goto fail;
            }
        memset(n71_ro_block_memory.target[i],0,PAGE_SIZE);
    }
    n71_ro_block_memory.major=register_blkdev(0,"n71nand_ro");
    if (n71_ro_block_memory.major<0) {rc=n71_ro_block_memory.major;goto fail;}
    n71_ro_block_memory.disk=blk_alloc_disk(&lim,NUMA_NO_NODE);
    if (IS_ERR(n71_ro_block_memory.disk)) {
        rc=PTR_ERR(n71_ro_block_memory.disk);n71_ro_block_memory.disk=NULL;
        goto fail;
    }
    n71_ro_block_memory.disk->major=n71_ro_block_memory.major;
    n71_ro_block_memory.disk->first_minor=0;
    n71_ro_block_memory.disk->minors=1;
    n71_ro_block_memory.disk->flags|=GENHD_FL_NO_PART;
    n71_ro_block_memory.disk->fops=&n71_ro_block_fops;
    strscpy(n71_ro_block_memory.disk->disk_name,"n71nand_ro",DISK_NAME_LEN);
    set_capacity(n71_ro_block_memory.disk,(sector_t)N71_RO_PHYSICAL_NSZE*8ULL);
    set_disk_ro(n71_ro_block_memory.disk,true);
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        struct bio *bio=bio_alloc(n71_ro_block_memory.disk->part0,1,
                                 REQ_OP_READ|REQ_SYNC,GFP_KERNEL);
        if (!bio) {rc=-ENOMEM;goto fail;}
        n71_ro_block_memory.bio[i]=bio;
        bio->bi_iter.bi_sector=8ULL*n71_read_pair_lba(n71_series_base(),i);
        if (bio_add_page(bio,virt_to_page(n71_ro_block_memory.target[i]),
                         4096,0)!=4096) {rc=-EINVAL;goto fail;}
    }
    if (!n71_io_pre_bme(ctx)) {rc=-EPERM;goto fail;}
    n71_ro_block_memory.prepared=true;
    pr_info("n71-s3e-p0: RO_BLOCK_PREPARED capacity_bytes=64000000000 logical_block_bytes=4096 trusted_bios=%u CPU_only_targets=%u cc_off=1 bme_off=1 partition_scan=DISABLED userspace_open=DENIED all_target_frames_retained=YES\n",N71_READ_SERIES_COUNT,N71_READ_SERIES_COUNT);
    return 0;
fail:
    n71_ro_block_release_software();
    n71_read_series_memory.quarantined=true;
    n71_ro_io_dma_memory.quarantined=true;n71_unreleased=true;
    return rc;
}
static int n71_ro_block_client(void *unused)
{
    unsigned int i;
    int rc=0;
    (void)unused;
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        rc=n71_ro_probe_wait(i);
        if (rc) break;
        if (kthread_should_stop() || READ_ONCE(n71_ro_block_memory.flow.closed)) {
            rc=-ECANCELED;break;
        }
        rc=submit_bio_wait(n71_ro_block_memory.bio[i]);
        if (rc) break;
        if (memchr_inv((u8 *)n71_ro_block_memory.target[i]+4096,0,PAGE_SIZE-4096)) {
            rc=-EOVERFLOW;break;
        }
        n71_ro_block_memory.client_completed++;
#if N71_GPT_FULL_PLAN
        if(i==N71_READ_SERIES_COUNT-1U) {
            const unsigned char *pages[4];unsigned j;
            for(j=0;j<4;j++)pages[j]=n71_ro_block_memory.target[1U+j];
            n71_ro_block_memory.gpt_crc_ok=n71_gpt_full_crc_valid(n71_ro_block_memory.target[0],pages);
            if(!n71_ro_block_memory.gpt_crc_ok){rc=-EUCLEAN;break;}
        }
#elif N71_CQ_WRAP_PLAN
        if(ans_ro_probe_once && i>=2U &&
           memcmp(n71_ro_block_memory.target[i&1U],n71_ro_block_memory.target[i],4096)) {
            rc=-EUCLEAN;break;
        }
#else
        /* The last userspace reply also requires both full-sector pairs. */
        if (ans_ro_probe_once && i==3U &&
            (memcmp(n71_ro_block_memory.target[0],n71_ro_block_memory.target[2],4096) ||
             memcmp(n71_ro_block_memory.target[1],n71_ro_block_memory.target[3],4096))) {
            rc=-EUCLEAN;break;
        }
#endif
        n71_ro_probe_reply(0);
    }
    if (!rc && i==N71_READ_SERIES_COUNT) {
#if N71_GPT_FULL_PLAN
        if(!n71_ro_block_content_valid())rc=-EUCLEAN;
#elif N71_CQ_WRAP_PLAN
        n71_ro_block_memory.pairs_equal=true;
        for(i=2;i<N71_READ_SERIES_COUNT;i++)
            if(memcmp(n71_ro_block_memory.target[i&1U],n71_ro_block_memory.target[i],4096))
                n71_ro_block_memory.pairs_equal=false;
        if(!n71_ro_block_memory.pairs_equal)rc=-EUCLEAN;
#else
        n71_ro_block_memory.pairs_equal=
            !memcmp(n71_ro_block_memory.target[0],n71_ro_block_memory.target[2],4096) &&
            !memcmp(n71_ro_block_memory.target[1],n71_ro_block_memory.target[3],4096);
        if (!n71_ro_block_memory.pairs_equal) rc=-EUCLEAN;
#endif
    }
    rc=n71_ro_probe_finish(rc);
    WRITE_ONCE(n71_ro_block_memory.client_rc,rc);
    /* Keep task alive until its owner joins it; no dangling task pointer. */
    while (!kthread_should_stop()) schedule_timeout_interruptible(HZ);
    return rc;
}
static int n71_ro_block_qualified(void *ctx,unsigned int step)
{
    unsigned long irq;
    bool valid;
    if (step>=N71_READ_SERIES_COUNT || !wait_for_completion_timeout(
            &n71_ro_block_memory.request_ready,msecs_to_jiffies(8000))) return 0;
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    valid=n71_ro_block_memory.pending_bio==n71_ro_block_memory.bio[step] &&
        n71_ro_block_memory.flow.active && !n71_ro_block_memory.flow.closed &&
        n71_ro_block_memory.flow.pending &&
        n71_ro_block_memory.flow.admitted==step+1U &&
        n71_ro_block_memory.flow.delivered==step;
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
    return valid && n71_read_series_qualified(ctx,step);
}
static int n71_ro_block_stable(void *ctx,unsigned int count)
{
    struct bio *bio=NULL;
    unsigned long irq;
    unsigned int step=count-1U;
    int rc=n71_read_series_stable(ctx,count);
    if (rc || !count || count>N71_READ_SERIES_COUNT) return rc ? rc : -EPERM;
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    /* The final all-buffer stability pass must not complete a bio twice. */
    if (n71_ro_block_memory.flow.delivered==count) {
        spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);return 0;
    }
    if (n71_ro_block_memory.pending_bio!=n71_ro_block_memory.bio[step] ||
        !n71_ro_block_memory.flow.active || n71_ro_block_memory.flow.closed ||
        !n71_ro_block_memory.flow.pending ||
        n71_ro_block_memory.flow.delivered!=step ||
        n71_ro_block_memory.flow.admitted!=count) {
        spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);return -EPROTO;
    }
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
    if (memchr_inv(n71_ro_block_memory.target[step],0,PAGE_SIZE)) return -EUCLEAN;
    /* Only validated private CPU snapshot -> trusted CPU bio target.
     * The device never sees this target, nor any bio/request pointer. */
    memcpy(n71_ro_block_memory.target[step],n71_read_series_memory.page[N71_READ_SERIES_DMA_PAGES+step],4096);
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    rc=n71_ro_block_deliver(&n71_ro_block_memory.flow,step);
    if (!rc) {bio=n71_ro_block_memory.pending_bio;n71_ro_block_memory.pending_bio=NULL;}
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
    if (rc) return -EPROTO;
    bio_endio(bio);
    pr_info("n71-s3e-p0: RO_BLOCK_DELIVERED index=%u lba=%u bytes=4096 CQE_data_guard_validated=YES CPU_snapshot_only=YES payload_and_hashes_redacted=YES\n",
            step,n71_read_pair_lba(n71_series_base(),step));
    return 0;
}
static int n71_ro_block_completed_safely(void)
{
    return n71_ro_block_memory.passed && n71_ro_block_memory.removed &&
        n71_read_series_completed_safely();
}
static int n71_ro_block_once(void *ctx)
{
    struct bio *pending;
    unsigned long irq;
    int rc,client_rc=-ECANCELED;
    if (!ans_ro_block_once || !n71_ro_block_memory.prepared ||
        n71_ro_block_memory.registered || !n71_read_series_qualified(ctx,0)) return -EPERM;
    rc=add_disk(n71_ro_block_memory.disk);
    if (rc) {n71_ro_block_release_software();return rc;}
    n71_ro_block_memory.registered=true;
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    n71_ro_block_memory.flow.active=1;
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
#if N71_GPT_FULL_PLAN
    pr_info("n71-s3e-p0: RO_BLOCK_GPT_FULL lbas=1,2,3,4,5 requests=5 no_pair_comparison=YES\n");
#else
    pr_info("n71-s3e-p0: RO_BLOCK_PAIR base_lba=%u pair_count=2 requests=4 tail_selected=%u\n",
        n71_series_base(),ans_ro_block_tail_once);
#endif
    pr_info("n71-s3e-p0: RO_BLOCK_REGISTERED name=n71nand_ro capacity_bytes=64000000000 logical_block_bytes=4096 read_only=1 partition_scan=DISABLED userspace_open=DENIED request_budget=%u\n",N71_READ_SERIES_COUNT);
    rc=n71_ro_probe_start();
    if (rc) goto close;
    n71_ro_block_memory.client=kthread_run(n71_ro_block_client,NULL,"n71-ro-client");
    if (IS_ERR(n71_ro_block_memory.client)) {
        rc=PTR_ERR(n71_ro_block_memory.client);n71_ro_block_memory.client=NULL;
    } else rc=n71_read_series_once(ctx);
close:
    spin_lock_irqsave(&n71_ro_block_memory.lock,irq);
    pending=n71_ro_block_memory.pending_bio;n71_ro_block_memory.pending_bio=NULL;
    n71_ro_block_close(&n71_ro_block_memory.flow,!!rc);
    spin_unlock_irqrestore(&n71_ro_block_memory.lock,irq);
    if (pending) bio_io_error(pending);
    n71_ro_probe_close(!!rc);
    if (n71_ro_block_memory.client) {
        client_rc=kthread_stop(n71_ro_block_memory.client);
        n71_ro_block_memory.client=NULL;
    }
    if (!rc && (client_rc || n71_ro_block_memory.client_completed!=N71_READ_SERIES_COUNT ||
            !n71_ro_block_content_valid() ||
            !n71_ro_block_flow_complete(&n71_ro_block_memory.flow))) rc=-EIO;
    if (rc) n71_read_series_memory.series_ok=false;
    n71_ro_block_release_software();
    n71_ro_block_memory.passed=!rc && n71_ro_block_memory.removed;
    pr_info("n71-s3e-p0: RO_BLOCK_ONCE rc=%d registered=%u removed=%u bios_admitted=%u bios_delivered=%u client_completed=%u client_rc=%d private_pair_equality=%u rejected=%u writes_available=NO userspace_block_access=NO all_DMA_and_target_frames_retained=YES dma_release_authorized=NO payload_and_hashes_redacted=YES\n",
        rc,n71_ro_block_memory.registered,n71_ro_block_memory.removed,
        n71_ro_block_memory.flow.admitted,n71_ro_block_memory.flow.delivered,
        n71_ro_block_memory.client_completed,client_rc,n71_ro_block_memory.pairs_equal,
        n71_ro_block_memory.rejected);
#if N71_GPT_FULL_PLAN
    pr_info("n71-s3e-p0: RO_BLOCK_GPT_CRC kernel_targets_valid=%u pair_equality_tested=NO\n",n71_ro_block_memory.gpt_crc_ok);
#endif
    if (ans_ro_probe_once)
        pr_info("n71-s3e-p0: RO_PROBE_ONCE rc=%d requested=%u copied=%u char_removed=%u sector_payload_logged=NO writes=NO DMA_release=NO\n",
            rc,n71_ro_probe.requested,n71_ro_probe.copied,n71_ro_probe.removed);
    return rc;
}
#endif
