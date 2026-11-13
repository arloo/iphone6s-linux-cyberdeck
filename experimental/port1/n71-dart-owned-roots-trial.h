/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_DART_OWNED_ROOTS_TRIAL_H
#define N71_DART_OWNED_ROOTS_TRIAL_H
#include "n71-dart-ttbr-disabled-trial.h"
/* Original S5L8960X: valid bit31, 24-bit page number, 4 KiB alignment. */
static unsigned int n71_dart_owned_ttbr(unsigned long long pa)
{
    if (!pa || (pa & 0xfffULL) || pa >= (1ULL << 36)) return 0;
    return 0x80000000U | (unsigned int)(pa >> 12);
}
/* Caller owns and DMA-synchronizes four distinct all-zero 4 KiB pages.
 * Outer disabled-TTBR transaction supplies/restores the inherited roots.
 * Never touches roots for streams 1..3 or releases endpoint reset.
 */
static int n71_dart_owned_roots_trial(const struct n71_dart_trial_ops *o, void *ctx,
                                    const unsigned int roots[4],
                                    unsigned int *last, unsigned int *polls)
{
    unsigned int i, j;
    int ret = -1;
    *last = *polls = 0;
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0) return -1;
    for (i = 0; i < 4; i++) {
        if ((roots[i] & 0xff000000U) != 0x80000000U ||
            o->read(ctx, 0x40 + 4*i) != 0) return -1;
        for (j = 0; j < i; j++) if (roots[i] == roots[j]) return -1;
    }
    for (i = 0; i < 4; i++) {
        if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0) goto clear;
        o->write(ctx, 0x40 + 4*i, roots[i]);
        if (o->read(ctx, 0x40 + 4*i) != roots[i]) goto clear;
    }
    ret = n71_dart_tcr0_flush_roots_trial(o, ctx, roots, last, polls);
clear:
    /* Never tear down roots while translation remains enabled. */
    if (o->read(ctx, 0x0c) != 0) return -3;
    for (i = 0; i < 4; i++) {
        o->write(ctx, 0x40 + 4*i, 0);
        if (o->read(ctx, 0x40 + 4*i) != 0) ret = -2;
    }
    return ret;
}
#endif
