/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_POST_RESET_PROTOCOL_H
#define N71_S3E_POST_RESET_PROTOCOL_H
/*
 * Read-only interpretation of the NVMe CC.EN=1 -> 0 Controller Reset.
 * NVMe reset may clear INTMS and vendor HMB configuration while retaining
 * AQA/ASQ/ACQ. PERST must remain deasserted for valid BAR0 reads.
 *
 * CRITICAL: consistency with controller-reset semantics does NOT establish
 * DMA quiescence, DART/NVMMU release, safe queue writes, NAND access, or
 * permission to unload a quarantined driver.
 */
struct n71_post_reset_protocol_observation {
    unsigned int shutdown_attempted, shutdown_rc, shutdown_csts;
    unsigned int disable_rc, disable_csts, master_off;
    unsigned int cc, csts, root_command, endpoint_command;
    unsigned int intms, perst_high;
    unsigned int hmb_descriptor_zero, queues_owned;
    unsigned int prepared, dart_mapped, hmb_owned;
};
static int n71_post_reset_protocol_consistent(
    const struct n71_post_reset_protocol_observation *p)
{
    if (!p) return 0;
    return p->shutdown_attempted==1 && !p->shutdown_rc &&
           p->shutdown_csts==9 &&
           !p->disable_rc && !p->disable_csts && p->master_off==1 &&
           !p->cc && !p->csts &&
           p->root_command==2 && p->endpoint_command==2 &&
           !(p->intms & 1) && p->perst_high==1 &&
           p->hmb_descriptor_zero==1 && p->queues_owned==1 &&
           p->prepared==1 && p->dart_mapped==1 && p->hmb_owned==1;
}
#endif
