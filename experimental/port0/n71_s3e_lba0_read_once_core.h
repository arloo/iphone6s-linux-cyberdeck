/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_LBA0_READ_ONCE_CORE_H
#define N71_S3E_LBA0_READ_ONCE_CORE_H
#include "n71_s3e_io_queue_once_core.h"
/* Explicit experimental FlatDMA transport, matching working Identify.
 * This is not a claim about the original iOS runtime's flag policy. */
#define N71_LBA0_READ_FLAGS 0x20U
#define N71_LBA0_WORDS (N71_RO_BLOCK_BYTES / 8U)
#define N71_LBA0_GUARD_WORDS (N71_RO_HOST_FRAME_BYTES / 8U)
static inline int n71_lba0_mode_valid(unsigned int enabled,
        unsigned int flags, unsigned int identify, unsigned int queues,
        unsigned int delete_queues, unsigned int queue_flags)
{
    return enabled ? flags==N71_LBA0_READ_FLAGS && identify && queues &&
                     delete_queues && queue_flags==0U :
                     flags==N71_IO_QUEUE_FLAGS_UNSELECTED;
}
static inline int n71_lba0_command(unsigned char *out,
        const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze, unsigned int lba_bytes, unsigned int flags)
{
    unsigned char command[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!out || flags!=N71_LBA0_READ_FLAGS ||
        n71_s3e_ro_verify_queue_iova(layout) ||
        n71_s3e_ro_encode_one_sector(command,layout,nsze,lba_bytes,0ULL))
        return -1;
    command[1]=(unsigned char)flags;
    for (i=0;i<N71_RO_CMD_BYTES;i++) out[i]=command[i];
    return 0;
}
static inline int n71_lba0_command_valid(const unsigned char *command,
        const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze, unsigned int lba_bytes, unsigned int flags)
{
    unsigned char expected[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!command || n71_lba0_command(expected,layout,nsze,lba_bytes,flags))
        return 0;
    for (i=0;i<N71_RO_CMD_BYTES;i++) if (command[i]!=expected[i]) return 0;
    return 1;
}
static inline int n71_lba0_cqe_valid(unsigned int observed,
        const struct n71_s3e_admin_cqe_fields *v)
{
    return v && observed==1U && v->status==observed &&
        v->command_id==1U && v->sq_id==1U && v->sq_head==1U;
}
static inline int n71_lba0_invalidate_value_valid(unsigned int value)
{
    return value==0U || value==0x10000U;
}
static inline unsigned long long n71_lba0_mark_word(
        unsigned long long seed, unsigned int i)
{
    return seed ^ (0x9e3779b97f4a7c15ULL * ((unsigned long long)i+1ULL));
}
static inline void n71_lba0_mark(unsigned char *data, unsigned long long seed)
{
    unsigned int i;
    for (i=0;i<N71_LBA0_GUARD_WORDS;i++)
        n71_ro_le64(data+8U*i,n71_lba0_mark_word(seed,i));
}
/* Return -1 for an owned-frame overrun, 0 while any 64-bit data witness
 * remains, and 1 once every sector witness changes with guard intact.
 * These are transfer witnesses, not payload authentication or DMA drain. */
static inline int n71_lba0_data_state(const unsigned char *data,
        unsigned long long seed, unsigned int *changed)
{
    unsigned int i, n=0;
    if (!data || !changed) return -1;
    for (i=0;i<N71_LBA0_WORDS;i++)
        if (n71_ro_get_le64(data+8U*i)!=n71_lba0_mark_word(seed,i)) n++;
    *changed=n;
    for (i=N71_LBA0_WORDS;i<N71_LBA0_GUARD_WORDS;i++)
        if (n71_ro_get_le64(data+8U*i)!=n71_lba0_mark_word(seed,i)) return -1;
    return n==N71_LBA0_WORDS;
}
struct n71_lba0_read_ops {
    int (*qualified)(void *);
    int (*submit)(void *,const unsigned char *);
    int (*wait_cqe)(void *,unsigned int *,struct n71_s3e_admin_cqe_fields *);
    int (*ack_cq)(void *);
    int (*wait_data)(void *);
};
struct n71_lba0_read_result {
    unsigned int submitted,completion_seen,completion_valid,cq_acked,data_arrived;
};
/* Exactly one NVM Read on I/O QID1: NSID1, SLBA0, NLB0 => 4096 bytes.
 * No retry, alternate flags, arbitrary LBA, write, payload export or release. */
static inline int n71_lba0_read_once_core(const struct n71_lba0_read_ops *o,
        void *ctx, const struct n71_s3e_ro_io_layout *layout,
        unsigned long long nsze, unsigned int lba_bytes, unsigned int flags,
        struct n71_lba0_read_result *r)
{
    unsigned char command[N71_RO_CMD_BYTES];
    struct n71_s3e_admin_cqe_fields cqe={0};
    unsigned int observed=0;
    int rc;
    if (!r) return -1;
    r->submitted=r->completion_seen=r->completion_valid=r->cq_acked=r->data_arrived=0;
    if (!o || !o->qualified || !o->submit || !o->wait_cqe ||
        !o->ack_cq || !o->wait_data ||
        n71_lba0_command(command,layout,nsze,lba_bytes,flags) ||
        !o->qualified(ctx)) return -1;
    rc=o->submit(ctx,command);
    if (rc) return rc;
    r->submitted=1;
    rc=o->wait_cqe(ctx,&observed,&cqe);
    if (rc) return rc;
    r->completion_seen=1;
    if (!n71_lba0_cqe_valid(observed,&cqe)) return -2;
    r->completion_valid=1;
    rc=o->ack_cq(ctx);
    if (rc) return rc;
    r->cq_acked=1;
    rc=o->wait_data(ctx);
    if (rc) return rc;
    r->data_arrived=1;
    return 0;
}
#endif
