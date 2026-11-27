/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_READ_SERIES_CORE_H
#define N71_S3E_READ_SERIES_CORE_H
#include "n71_s3e_lba0_read_once_core.h"
#include "n71_s3e_ro_flatdma_tag1_stage.h"
#ifndef N71_GPT_FULL_PLAN
#define N71_GPT_FULL_PLAN 0
#endif
#if N71_GPT_FULL_PLAN != 0 && N71_GPT_FULL_PLAN != 1
#error Unsupported read qualification plan
#endif
#ifndef N71_CQ_WRAP_PLAN
#define N71_CQ_WRAP_PLAN 0
#endif
#if (N71_CQ_WRAP_PLAN != 0 && N71_CQ_WRAP_PLAN != 1) || (N71_CQ_WRAP_PLAN && N71_GPT_FULL_PLAN)
#error Unsupported or mixed CQ wrap qualification plan
#endif
#define N71_READ_SERIES_COUNT (N71_CQ_WRAP_PLAN ? 17U : N71_GPT_FULL_PLAN ? 5U : 4U)
/* Original bounded arithmetic following standard NVMe queue semantics.
 * Slots/doorbells wrap; tags, CIDs and data/SGL/snapshot frames do not. */
static inline unsigned int n71_read_queue_slot(unsigned int step)
{
    return step % N71_RO_Q_ENTRIES;
}
static inline unsigned int n71_read_queue_next(unsigned int step)
{
    return (step+1U) % N71_RO_Q_ENTRIES;
}
static inline unsigned int n71_read_cq_phase(unsigned int step)
{
    return 1U ^ ((step/N71_RO_Q_ENTRIES)&1U);
}
#define N71_READ_SERIES_DMA_PAGES (2U*N71_READ_SERIES_COUNT)
#define N71_READ_SERIES_PAGES (3U*N71_READ_SERIES_COUNT)
/* One explicit consecutive pair per epoch, within the accepted namespace.
 * Legacy wrappers still bind base0; runtime separately gates new selection. */
static inline int n71_read_pair_base_valid(unsigned int base)
{
    return N71_GPT_FULL_PLAN ? base==1U : base<=N71_RO_PHYSICAL_NSZE-2U;
}
static inline unsigned int n71_read_pair_lba(unsigned int base,unsigned int step)
{
    return N71_GPT_FULL_PLAN ? base+step : base+(step&1U);
}
static inline unsigned int n71_read_series_lba(unsigned int step)
{
    return N71_GPT_FULL_PLAN ? 1U+step : step & 1U;
}
static inline unsigned long long n71_read_series_tag(unsigned int step)
{
    return step<N71_READ_SERIES_COUNT ?
        N71_RO_FLATDMA_VBASE | ((unsigned long long)(step+1U)<<23) : 0;
}
static inline int n71_read_series_mode_valid(unsigned int enabled,
        unsigned int flags,unsigned int identify,unsigned int queues,
        unsigned int delete_queues,unsigned int queue_flags,
        unsigned int single_read)
{
    return enabled ? flags==N71_LBA0_READ_FLAGS && identify && queues &&
        delete_queues && queue_flags==0U && !single_read :
        flags==N71_IO_QUEUE_FLAGS_UNSELECTED;
}
static inline int n71_read_pair_command(unsigned char *out,unsigned int step,
        const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags,
        unsigned int base)
{
    unsigned char command[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!n71_read_pair_base_valid(base) || !out || step>=N71_READ_SERIES_COUNT || flags!=N71_LBA0_READ_FLAGS ||
        n71_s3e_ro_verify_queue_iova(layout) ||
        nsze!=N71_RO_PHYSICAL_NSZE || lba_bytes!=N71_RO_BLOCK_BYTES)
        return -1;
    if (n71_s3e_ro_encode_one_sector(command,layout,nsze,lba_bytes,
                                    n71_read_pair_lba(base,step))) return -1;
    command[1]=(unsigned char)flags;
    n71_ro_le16(command+2,step+1U);
    n71_ro_le64(command+24,n71_read_series_tag(step));
    for (i=0;i<N71_RO_CMD_BYTES;i++) out[i]=command[i];
    return 0;
}
static inline int n71_read_series_command(unsigned char *out,unsigned int step,
        const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags)
{
    return n71_read_pair_command(out,step,layout,nsze,lba_bytes,flags,N71_GPT_FULL_PLAN ? 1U : 0U);
}
static inline int n71_read_pair_command_valid(const unsigned char *b,
        unsigned int step,const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags,
        unsigned int base)
{
    unsigned char expected[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!b || n71_read_pair_command(expected,step,layout,nsze,lba_bytes,flags,base))
        return 0;
    for (i=0;i<N71_RO_CMD_BYTES;i++) if (b[i]!=expected[i]) return 0;
    return 1;
}
static inline int n71_read_series_command_valid(const unsigned char *b,
        unsigned int step,const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags)
{
    return n71_read_pair_command_valid(b,step,layout,nsze,lba_bytes,flags,N71_GPT_FULL_PLAN ? 1U : 0U);
}
static inline int n71_read_series_cqe_valid(unsigned int observed,
        const struct n71_s3e_admin_cqe_fields *v,unsigned int step)
{
    return step<N71_READ_SERIES_COUNT && v && observed==n71_read_cq_phase(step) &&
        v->status==observed && v->command_id==step+1U &&
        v->sq_id==1U && v->sq_head==n71_read_queue_next(step);
}
static inline int n71_cq_wrap_mode_valid(unsigned int enabled,unsigned int block,
        unsigned int probe,unsigned int pair,unsigned int base,unsigned int tail,
        unsigned int series,unsigned int single)
{
    return enabled==1U && block==1U && probe==1U && pair==1U &&
        n71_read_pair_base_valid(base) && !tail && !series && !single;
}
struct n71_read_series_frames {
    unsigned long long data[N71_READ_SERIES_COUNT],sgl[N71_READ_SERIES_COUNT];
};
static inline unsigned long long n71_read_series_frame(
        const struct n71_read_series_frames *f,unsigned int i)
{
    return !f || i>=N71_READ_SERIES_DMA_PAGES ? 0 :
        i<N71_READ_SERIES_COUNT ? f->data[i] : f->sgl[i-N71_READ_SERIES_COUNT];
}
static inline int n71_read_series_frames_valid(
        const struct n71_read_series_frames *f,
        const struct n71_s3e_ro_foreign_range *foreign,unsigned int count)
{
    unsigned int i,j;
    if (!f || count>128U || (count&&!foreign)) return 0;
    for (i=0;i<N71_READ_SERIES_DMA_PAGES;i++) {
        unsigned long long pa=n71_read_series_frame(f,i);
        if (!n71_ro_valid_host_frame(pa)) return 0;
        for (j=0;j<i;j++) if (pa==n71_read_series_frame(f,j)) return 0;
        for (j=0;j<count;j++) {
            unsigned long long p=foreign[j].pa,n=foreign[j].bytes;
            if (!n || p>=N71_RO_DMA_ADDRESS_LIMIT ||
                n>N71_RO_DMA_ADDRESS_LIMIT-p ||
                (pa<p+n && p<pa+N71_RO_HOST_FRAME_BYTES)) return 0;
        }
    }
    return 1;
}
/* CPU-only all-or-nothing shadow staging. Selected tags are distinct; tag0 and
 * every other slot remain unchanged. Runtime publishes page counts last. */
static inline int n71_read_series_stage(unsigned char *tcb,
        unsigned char *const sgl[N71_READ_SERIES_COUNT],const struct n71_read_series_frames *f,
        const struct n71_s3e_ro_foreign_range *foreign,unsigned int count)
{
    unsigned int i,j,k;
    if (!tcb || !sgl || !n71_read_series_frames_valid(f,foreign,count) ||
        n71_ro_get_le32(tcb)!=0x200U || n71_ro_get_le32(tcb+4)!=1U ||
        !n71_ro_get_le32(tcb+8) || !n71_ro_get_le64(tcb+16)) return -1;
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        unsigned long a,b;
        if (!sgl[i]) return -1;
        a=(unsigned long)sgl[i];b=(unsigned long)tcb;
        if ((a<=b&&b-a<N71_RO_HOST_FRAME_BYTES) ||
            (b<a&&a-b<N71_RO_HOST_FRAME_BYTES)) return -1;
        for (j=0;j<i;j++) {
            b=(unsigned long)sgl[j];
            if ((a<=b&&b-a<N71_RO_HOST_FRAME_BYTES) ||
                (b<a&&a-b<N71_RO_HOST_FRAME_BYTES)) return -1;
        }
        for (k=0;k<N71_RO_TCB_BYTES;k++)
            if (tcb[(i+1U)*N71_RO_TCB_BYTES+k]) return -1;
        for (k=0;k<N71_RO_HOST_FRAME_BYTES;k++) if (sgl[i][k]) return -1;
    }
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        unsigned char *slot=tcb+(i+1U)*N71_RO_TCB_BYTES;
        n71_ro_le32(sgl[i],(unsigned int)(f->data[i]>>12));
        n71_ro_le32(slot,0x200U);
        n71_ro_le32(slot+8,(unsigned int)(f->data[i]>>12));
        n71_ro_le64(slot+16,f->sgl[i]);
        n71_ro_le32(slot+4,1U);
    }
    return 0;
}
struct n71_read_series_ops {
    int (*qualified)(void *,unsigned int);
    int (*submit)(void *,unsigned int,const unsigned char *);
    int (*wait_cqe)(void *,unsigned int,unsigned int *,
                    struct n71_s3e_admin_cqe_fields *);
    int (*ack_cq)(void *,unsigned int);
    int (*wait_data)(void *,unsigned int);
    int (*snapshot)(void *,unsigned int);
    int (*stable)(void *,unsigned int);
    int (*compare_pairs)(void *);
};
struct n71_read_series_result {
    unsigned int submitted,accepted,snapshotted,stability_checks,pairs_valid;
};
/* Compile-time bounded single-sector Reads with distinct tags/data/SGL frames.
 * Only the separately selected 17-Read mode wraps SQ/CQ slots once; it never
 * reuses a data/SGL/target/snapshot frame or authorizes DMA release. */
static inline int n71_read_pair_core(const struct n71_read_series_ops *o,
        void *ctx,const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags,
        struct n71_read_series_result *r,unsigned int base)
{
    unsigned char command[64];
    unsigned int i,observed;
    struct n71_s3e_admin_cqe_fields v;
    int rc;
    if (!r) return -1;
    r->submitted=r->accepted=r->snapshotted=r->stability_checks=r->pairs_valid=0;
    if (!n71_read_pair_base_valid(base) || !o || !o->qualified || !o->submit || !o->wait_cqe || !o->ack_cq ||
        !o->wait_data || !o->snapshot || !o->stable || !o->compare_pairs)
        return -1;
    for (i=0;i<N71_READ_SERIES_COUNT;i++) {
        if (n71_read_pair_command(command,i,layout,nsze,lba_bytes,flags,base) ||
            !o->qualified(ctx,i)) return -1;
        rc=o->submit(ctx,i,command);
        if (rc) return rc;
        r->submitted++;
        observed=0;v=(struct n71_s3e_admin_cqe_fields){0};
        rc=o->wait_cqe(ctx,i,&observed,&v);
        if (rc) return rc;
        if (!n71_read_series_cqe_valid(observed,&v,i)) return -2;
        rc=o->ack_cq(ctx,i);
        if (rc) return rc;
        rc=o->wait_data(ctx,i);
        if (rc) return rc;
        r->accepted++;
        rc=o->snapshot(ctx,i);
        if (rc) return rc;
        r->snapshotted++;
        rc=o->stable(ctx,i+1U);
        if (rc) return rc;
        r->stability_checks++;
    }
    rc=o->compare_pairs(ctx);
    if (rc) return rc;
    r->pairs_valid=1;
    rc=o->stable(ctx,N71_READ_SERIES_COUNT);
    if (rc) return rc;
    r->stability_checks++;
    return 0;
}
static inline int n71_read_series_core(const struct n71_read_series_ops *o,
        void *ctx,const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze,unsigned int lba_bytes,unsigned int flags,
        struct n71_read_series_result *r)
{
    return n71_read_pair_core(o,ctx,layout,nsze,lba_bytes,flags,r,N71_GPT_FULL_PLAN ? 1U : 0U);
}
#endif
