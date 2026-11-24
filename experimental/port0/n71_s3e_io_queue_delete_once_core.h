/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_IO_QUEUE_DELETE_ONCE_CORE_H
#define N71_S3E_IO_QUEUE_DELETE_ONCE_CORE_H
#include "n71_s3e_io_queue_once_core.h"
/* Volatile ADMIN queue deletion only. No namespace data opcode, I/O
 * doorbell, backing release, retry or claim of DMA retirement. */
struct n71_io_queue_delete_result {
    unsigned int sq_attempted, sq_validated, cq_attempted, cq_validated;
};
static inline int n71_io_queue_delete_encode(unsigned char *out,
        unsigned int flags, unsigned int cid)
{
    unsigned char tmp[N71_RO_CMD_BYTES] = {0};
    unsigned int i;
    if (!out || !n71_io_queue_flags_valid(flags) ||
        (cid != 4U && cid != 5U)) return -1;
    tmp[0] = cid == 4U ? 0x00U : 0x04U; /* ADMIN Delete SQ, then Delete CQ */
    tmp[1] = (unsigned char)flags;
    n71_ro_le16(tmp+2,cid);
    n71_ro_le16(tmp+40,N71_RO_QID);
    for (i=0;i<N71_RO_CMD_BYTES;i++) out[i]=tmp[i];
    return 0;
}
static inline int n71_io_queue_delete_command_valid(const unsigned char *b,
        unsigned int flags, unsigned int cid)
{
    unsigned char expected[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!b || n71_io_queue_delete_encode(expected,flags,cid)) return 0;
    for (i=0;i<N71_RO_CMD_BYTES;i++) if (b[i]!=expected[i]) return 0;
    return 1;
}
static inline int n71_io_queue_delete_cqe_valid(unsigned int observed,
        const struct n71_s3e_admin_cqe_fields *v, unsigned int cid)
{
    return (cid==4U || cid==5U) && v && observed==1U &&
        v->status==observed && v->command_id==cid &&
        v->sq_id==0U && v->sq_head==cid;
}
/* The caller must prove empty queues: either no I/O submission, or the
 * sole Read has a validated/acknowledged CQE and independent data witness.
 * Both Create completions must already validate.
 * This mirrors native Linux's SQ-before-CQ order, NOT its memory release. */
static inline int n71_io_queue_delete_once_core(
        const struct n71_io_queue_once_ops *o, void *ctx,
        unsigned int flags, unsigned int both_created,
        struct n71_io_queue_delete_result *r)
{
    unsigned char command[N71_RO_CMD_BYTES];
    int rc;
    if (!r) return -1;
    r->sq_attempted=r->sq_validated=r->cq_attempted=r->cq_validated=0;
    if (!both_created || !n71_io_queue_flags_valid(flags) || !o ||
        !o->qualified || !o->submit_admin || !o->qualified(ctx)) return -1;
    if (n71_io_queue_delete_encode(command,flags,4U)) return -1;
    r->sq_attempted=1;
    rc=o->submit_admin(ctx,command,4U);
    if (rc) return rc;
    r->sq_validated=1;
    if (!o->qualified(ctx)) return -1;
    if (n71_io_queue_delete_encode(command,flags,5U)) return -1;
    r->cq_attempted=1;
    rc=o->submit_admin(ctx,command,5U);
    if (rc) return rc;
    r->cq_validated=1;
    return 0;
}
#endif
