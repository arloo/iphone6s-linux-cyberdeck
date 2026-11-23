/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ADMIN_CQE_VALIDATE_H
#define N71_S3E_ADMIN_CQE_VALIDATE_H

/* One-shot Identify NS1 expects CQ phase=1, success, CID 1, SQID 0
 * and SQ head 1. Compare *CPU-synchronized* CQE fields only.
 * This has no device access and never authorizes DMA retirement. */
struct n71_s3e_admin_cqe_fields {
    unsigned int status;
    unsigned int command_id;
    unsigned int sq_id;
    unsigned int sq_head;
};

static inline int n71_s3e_admin_identify_cqe_valid(
    const struct n71_s3e_admin_cqe_fields *v)
{
    return v && v->status == 1U && v->command_id == 1U &&
           v->sq_id == 0U && v->sq_head == 1U;
}
#endif
