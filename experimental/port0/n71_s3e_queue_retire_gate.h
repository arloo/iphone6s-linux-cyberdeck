/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_QUEUE_RETIRE_GATE_H
#define N71_S3E_QUEUE_RETIRE_GATE_H
/*
 * Pure, fail-closed S8000 diagnostic gate. THIS IS NOT A DMA FREE GATE.
 * It is only a prerequisite for a single opt-in post-shutdown write of
 * the NVMe admin queue configuration registers to zero. All physical
 * DMA/HMB/DART/SART/NVMMU ownership remains quarantined afterward.
 */
struct n71_queue_retire_observation {
    unsigned int shutdown_attempted, shutdown_rc, shutdown_csts;
    unsigned int disable_rc, disable_csts, master_off;
    unsigned int cc, csts, root_command, endpoint_command;
    unsigned int reset_low, prepared, regs_saved, dart_mapped, hmb_owned;
    unsigned int hmb_lo, hmb_hi, hmb_size, intms;
    unsigned int aqa, asq_lo, asq_hi, acq_lo, acq_hi;
};
static int n71_queue_retire_gate(const struct n71_queue_retire_observation *v)
{
    if (!v) return 0;
    return v->shutdown_attempted == 1 && !v->shutdown_rc &&
           v->shutdown_csts == 9 &&
           !v->disable_rc && !v->disable_csts && v->master_off == 1 &&
           !v->cc && !v->csts &&
           v->root_command == 2 && v->endpoint_command == 2 &&
           v->reset_low == 1 && v->prepared == 1 && v->regs_saved == 1 &&
           v->dart_mapped == 1 && v->hmb_owned == 1 &&
           !v->hmb_lo && !v->hmb_hi && !v->hmb_size &&
           (v->intms & 1) &&
           v->aqa == 0x000f000fU &&
           v->asq_lo == 0x80010000U && !v->asq_hi &&
           v->acq_lo == 0x80011000U && !v->acq_hi;
}
#endif
