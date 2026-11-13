/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_GATING_TRIAL_H
#define N71_PORT_GATING_TRIAL_H
#include "n71-port-aux-trial.h"
/* Original port vslot1848 -> root1936: clear ID3 bit8 for flag1.
 * Original no-refclk-gating property is absent on owner N71 port1.
 */
static int n71_port_gating_trial(const struct n71_port_trial_ops *p,
                                const struct n71_port_aux_ops *o, void *ctx,
                                unsigned int *status, unsigned int *samples,
                                unsigned int *restored, unsigned int *gating_restored)
{
    unsigned int saved[4], i;
    int rc = -1;
    *gating_restored = *restored = *samples = *status = 0;
    if (p->perst_level(ctx) != 0 || !p->dart_ready(ctx)) return -1;
    for (i = 0; i < 4; i++) saved[i] = o->read(ctx, 0x114 + 0x80*i);
    if (saved[1] != 0x101) return -1;
    o->write(ctx, 0x194, saved[1] & ~0x100U);
    if (o->read(ctx, 0x194) == 1)
        rc = n71_port_local_trial(p, ctx, 1, status, samples, restored);
    if (p->perst_level(ctx) != 0) return -3;
    o->write(ctx, 0x194, saved[1]);
    *gating_restored = 1;
    for (i = 0; i < 4; i++)
        if (o->read(ctx, 0x114 + 0x80*i) != saved[i]) *gating_restored = 0;
    return *gating_restored ? rc : -2;
}
#endif
