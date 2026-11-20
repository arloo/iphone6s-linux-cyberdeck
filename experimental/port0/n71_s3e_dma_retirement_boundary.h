/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_DMA_RETIREMENT_BOUNDARY_H
#define N71_S3E_DMA_RETIREMENT_BOUNDARY_H
/* A successful controller shutdown is not a proof of DMA quiescence.
 * Active-admin epochs may have in-flight writes or stale translations.
 * Until independently proven safe, no admin-owned backing resource may be
 * released, regardless of CC/CSTS, BME, or HMB register values. */
struct n71_dma_retirement_boundary {
    unsigned int admin_epoch_started;
    unsigned int controller_shutdown_consistent;
    unsigned int independent_quiescence_proven;
};
static inline int n71_dma_retire_authorized(
    const struct n71_dma_retirement_boundary *s)
{
    if (!s) return 0;
    if (s->admin_epoch_started) return 0;
    if (s->independent_quiescence_proven) return 0; /* unimplemented proof */
    return 1; /* existing no-BME / no-admin observer cleanup only */
}
#endif
