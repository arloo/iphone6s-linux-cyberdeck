/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ADMIN_PROTOCOL_ACCOUNTING_H
#define N71_S3E_ADMIN_PROTOCOL_ACCOUNTING_H

/*
 * Host/kernel-agnostic protocol accounting for the ONE allowed admin
 * Identify command. No field is evidence of independent DMA quiescence.
 * In particular, a CQ phase bit is not a validated completion, and a CQ
 * head doorbell write is not independently confirmed by the device.
 */
struct n71_s3e_admin_protocol_snapshot {
    unsigned int submitted;
    unsigned int completion_observed;
    unsigned int completion_validated;
    unsigned int cq_head_doorbell_written;
    unsigned int data_arrived;
    unsigned int namespace_validated;
    unsigned int shutdown_attempted;
    unsigned int shutdown_complete;
    unsigned int controller_disabled;
    unsigned int master_off;
    unsigned int queues_retained;
    unsigned int admin_epoch_latched;
};

enum n71_s3e_admin_protocol_result {
    N71_S3E_ADMIN_NOT_SUBMITTED = 0,
    N71_S3E_ADMIN_INCOMPLETE = 1,
    N71_S3E_ADMIN_ACCOUNTED_DMA_UNPROVEN = 2
};

static inline enum n71_s3e_admin_protocol_result
n71_s3e_admin_protocol_classify(const struct n71_s3e_admin_protocol_snapshot *s)
{
    if (!s || s->submitted != 1)
        return N71_S3E_ADMIN_NOT_SUBMITTED;
    if (s->completion_observed != 1 ||
        s->completion_validated != 1 ||
        s->cq_head_doorbell_written != 1 ||
        s->data_arrived != 1 ||
        s->namespace_validated != 1 ||
        s->shutdown_attempted != 1 ||
        s->shutdown_complete != 1 ||
        s->controller_disabled != 1 ||
        s->master_off != 1 ||
        s->queues_retained != 1 ||
        s->admin_epoch_latched != 1)
        return N71_S3E_ADMIN_INCOMPLETE;
    return N71_S3E_ADMIN_ACCOUNTED_DMA_UNPROVEN;
}

/* Explicitly non-authoritative; NEVER used as a teardown/free gate. */
static inline int n71_s3e_admin_protocol_dma_release_allowed(
    const struct n71_s3e_admin_protocol_snapshot *s)
{
    (void)s;
    return 0;
}
#endif
