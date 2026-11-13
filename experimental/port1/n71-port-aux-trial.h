/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_AUX_TRIAL_H
#define N71_PORT_AUX_TRIAL_H
#include "n71-port-local-trial.h"
struct n71_port_aux_ops {
    unsigned int (*read)(void *, unsigned int);
    void (*write)(void *, unsigned int, unsigned int);
};
/* Original root vslot2040: write3 at 0x4020 + 0x40*port.
 * Only port1 word is writable; compare all other port words on rollback.
 */
static int n71_port_aux_trial(const struct n71_port_trial_ops *p,
                             const struct n71_port_aux_ops *o, void *ctx,
                             unsigned int *status, unsigned int *samples,
                             unsigned int *restored, unsigned int *aux_restored)
{
    unsigned int saved[4], i;
    int rc = -1;
    *aux_restored = *restored = *samples = *status = 0;
    if (p->perst_level(ctx) != 0 || !p->dart_ready(ctx)) return -1;
    for (i = 0; i < 4; i++) saved[i] = o->read(ctx, 0x4020 + 0x40*i);
    o->write(ctx, 0x4060, 3);
    if (o->read(ctx, 0x4060) == 3)
        rc = n71_port_local_trial(p, ctx, 1, status, samples, restored);
    if (p->perst_level(ctx) != 0) return -3;
    o->write(ctx, 0x4060, saved[1]);
    *aux_restored = 1;
    for (i = 0; i < 4; i++)
        if (o->read(ctx, 0x4020 + 0x40*i) != saved[i]) *aux_restored = 0;
    return *aux_restored ? rc : -2;
}
#endif
