/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_IO_QUEUE_ONCE_CORE_H
#define N71_S3E_IO_QUEUE_ONCE_CORE_H
#include "n71_s3e_ro_io_dart_map.h"
#include "n71_s3e_admin_cqe_validate.h"
#define N71_IO_QUEUE_FLAGS_UNSELECTED (~0U)
/* Explicit experimental queue-command flag selection, not Read qualification. */
static inline int n71_io_queue_flags_valid(unsigned int flags)
{
    return flags == 0U || flags == 0x20U;
}
static inline int n71_io_queue_mode_valid(unsigned int enabled,
        unsigned int identify, unsigned int flags,
        unsigned int retire, unsigned int late)
{
    return enabled ? identify && !retire && !late &&
                     n71_io_queue_flags_valid(flags) :
                     flags == N71_IO_QUEUE_FLAGS_UNSELECTED;
}
/* This pilot uses 16-entry contiguous queues, 4-KiB controller pages,
 * fixed 4-byte doorbell stride, and the observed S8000 NVMe 1.0.1 ABI. */
static inline int n71_io_queue_capability_valid(unsigned int lo,
        unsigned int hi, unsigned int version)
{
    return (lo & 0xFFFFU) >= 15U && (hi & 15U) == 0U &&
           (hi & 0x20U) && !(hi & 0xF0000U) && version == 0x00010001U;
}
/* Live queue submission has a DIFFERENT phase contract from the
 * disabled-controller HMB preparation predicate. Never reuse the latter. */
#define N71_IO_LIVE_MODE 1U
#define N71_IO_LIVE_CAPABILITY 2U
#define N71_IO_LIVE_EPOCH 4U
#define N71_IO_LIVE_BACKING 8U
#define N71_IO_LIVE_IDENTIFY 16U
#define N71_IO_LIVE_OWNER 32U
#define N71_IO_LIVE_ACTIVE 64U
#define N71_IO_LIVE_HMB 128U
struct n71_io_queue_live_snapshot {
    unsigned int enabled, identify, flags, epoch;
    unsigned int mapped, prepared, backing_ready, quarantined;
    unsigned int submitted, completion_valid, cq_head_written;
    unsigned int data_arrived, namespace_valid, lba_bytes;
    unsigned long long nsze;
    unsigned int translation_owned, cap_lo, cap_hi, version;
    unsigned int root_command, endpoint_command, cc, csts, intms;
    unsigned int hmb_low, hmb_high, hmb_bytes;
};
static inline unsigned int n71_io_queue_live_reject(
        const struct n71_io_queue_live_snapshot *s)
{
    unsigned int rejected = 0;
    if (!s) return 0xffU;
    if (!s->enabled || !s->identify || !n71_io_queue_flags_valid(s->flags))
        rejected |= N71_IO_LIVE_MODE;
    if (!n71_io_queue_capability_valid(s->cap_lo,s->cap_hi,s->version))
        rejected |= N71_IO_LIVE_CAPABILITY;
    if (!s->epoch) rejected |= N71_IO_LIVE_EPOCH;
    if (!s->mapped || !s->prepared || !s->backing_ready || s->quarantined)
        rejected |= N71_IO_LIVE_BACKING;
    if (!s->submitted || !s->completion_valid || !s->cq_head_written ||
        !s->data_arrived || !s->namespace_valid ||
        s->nsze != N71_RO_PHYSICAL_NSZE || s->lba_bytes != N71_RO_BLOCK_BYTES)
        rejected |= N71_IO_LIVE_IDENTIFY;
    if (!s->translation_owned) rejected |= N71_IO_LIVE_OWNER;
    if (s->root_command != 6U || s->endpoint_command != 6U ||
        s->cc != 0x460001U || s->csts != 1U || !(s->intms & 1U))
        rejected |= N71_IO_LIVE_ACTIVE;
    if (s->hmb_low != 0xbc000000U || s->hmb_high || s->hmb_bytes != 0x800000U)
        rejected |= N71_IO_LIVE_HMB;
    return rejected;
}
struct n71_io_queue_once_ops {
    int (*qualified)(void *);
    int (*submit_admin)(void *, const unsigned char *, unsigned int);
};
struct n71_io_queue_once_result {
    unsigned int cq_attempted, cq_validated, sq_attempted, sq_validated;
};
/* This trial fixes admin CID/head pairs 2/2 and 3/3 after Identify 1/1.
 * This is not a general NVMe CQE predicate or DMA-drain authority. */
static inline int n71_io_queue_cqe_valid(unsigned int observed_status,
        const struct n71_s3e_admin_cqe_fields *v, unsigned int cid)
{
    return (cid == 2U || cid == 3U) && v && observed_status == 1U &&
           v->status == observed_status && v->command_id == cid &&
           v->sq_id == 0U && v->sq_head == cid;
}
static inline int n71_io_queue_command_valid(const unsigned char *command,
        const struct n71_s3e_ro_io_layout *layout,
        unsigned int flags, unsigned int cid)
{
    unsigned char expected[N71_RO_CMD_BYTES];
    unsigned int i;
    if (!command || !n71_io_queue_flags_valid(flags)) return 0;
    if (cid == 2U) {
        if (n71_s3e_ro_encode_create_cq(expected, layout)) return 0;
    } else if (cid == 3U) {
        if (n71_s3e_ro_encode_create_sq(expected, layout)) return 0;
    } else return 0;
    expected[1] = (unsigned char)flags;
    for (i = 0; i < N71_RO_CMD_BYTES; i++)
        if (command[i] != expected[i]) return 0;
    return 1;
}
/* Only Create CQ then Create SQ, both on ADMIN QID0. No NVM opcode, delete
 * command, cleanup callback, retry or resource release exists here. */
static inline int n71_io_queue_once_core(const struct n71_io_queue_once_ops *o,
        void *ctx, const struct n71_s3e_ro_io_layout *layout,
        unsigned int flags, struct n71_io_queue_once_result *r)
{
    unsigned char command[N71_RO_CMD_BYTES];
    int rc;
    if (!r) return -1;
    r->cq_attempted = r->cq_validated = 0;
    r->sq_attempted = r->sq_validated = 0;
    if (!o || !o->qualified || !o->submit_admin ||
        !n71_io_queue_flags_valid(flags) ||
        n71_s3e_ro_verify_queue_iova(layout) || !o->qualified(ctx)) return -1;
    if (n71_s3e_ro_encode_create_cq(command, layout)) return -1;
    command[1] = (unsigned char)flags;
    r->cq_attempted = 1;
    rc = o->submit_admin(ctx, command, 2U);
    if (rc) return rc;
    r->cq_validated = 1;
    if (!o->qualified(ctx)) return -1;
    if (n71_s3e_ro_encode_create_sq(command, layout)) return -1;
    command[1] = (unsigned char)flags;
    r->sq_attempted = 1;
    rc = o->submit_admin(ctx, command, 3U);
    if (rc) return rc;
    r->sq_validated = 1;
    return 0;
}
#endif
