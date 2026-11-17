/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_DART_ALL_STREAM_OWNED_ROOTS_TRIAL_H
#define N71_DART_ALL_STREAM_OWNED_ROOTS_TRIAL_H
#include "n71-dart-owned-roots-trial.h"

/* Four streams, four 4KiB TTBR roots each, original S5L8960X layout.
 * The caller owns and DMA-synchronizes sixteen distinct empty pages.
 * Default trials hold endpoint reset. An optional active observer must
 * reassert reset before return, or request quarantine with -3.
 * No endpoint DMA-containment claim.
 * Returns -3 if hardware cannot safely release the caller's pages.
 */
static int n71_dart_all_stream_owned_roots_trial(
        const struct n71_dart_trial_ops *o, void *ctx,
        const unsigned int roots[16], unsigned int *last,
        unsigned int *polls)
{
    unsigned int saved[16], fault, i, j;
    int ret=-2, restored=1;
    *last=*polls=0;
    if (!o->tick || !o->perst_low(ctx) || o->read(ctx,0x0c)!=0)
        return -1;
    fault=o->read(ctx,0x10);
    *last=o->read(ctx,0);
    if ((fault & 0x80000000U) || (*last & 8)) return -1;
    for (i=0;i<16;i++) saved[i]=o->read(ctx,0x40+4*i);
    for (i=0;i<16;i++) {
        if ((roots[i] & 0xff000000U)!=0x80000000U) return -1;
        for (j=0;j<i;j++) if (roots[i]==roots[j]) return -1;
    }
    for (i=0;i<16;i++) {
        if (!o->perst_low(ctx) || o->read(ctx,0x0c)!=0) goto restore;
        o->write(ctx,0x40+4*i,roots[i]);
        if (o->read(ctx,0x40+4*i)!=roots[i]) goto restore;
    }
    o->write(ctx,0x0c,0x80808080U);
    if (o->read(ctx,0x0c)!=0x80808080U || !o->perst_low(ctx))
        goto disable;
    /* Select all four exclusive DART0 streams; bounded invalidate. */
    o->write(ctx,0,0x00000f02U);
    for (i=0;i<100;i++) {
        *last=o->read(ctx,0);
        *polls=i+1;
        if (!o->perst_low(ctx) || o->read(ctx,0x0c)!=0x80808080U)
            break;
        if (!(*last & 8)) {
            ret=*last==0xf02 ? 0 : -1;
            break;
        }
        o->tick(ctx);
    }
    if (!ret && o->active_hold) {
        ret=o->active_hold(ctx);
        /* Unsafe observer rollback retains translation and owned roots. */
        if (ret==-3) return -3;
    }
    if (o->read(ctx,0x10)!=fault) ret=-1;
disable:
    if (!o->perst_low(ctx)) return -3;
    o->write(ctx,0x0c,0);
    if (o->read(ctx,0x0c)!=0) return -3;
restore:
    if (!o->perst_low(ctx) || o->read(ctx,0x0c)!=0) return -3;
    /* Restore every stream only after translation is disabled. */
    for (i=0;i<16;i++) o->write(ctx,0x40+4*i,saved[i]);
    for (i=0;i<16;i++)
        if (o->read(ctx,0x40+4*i)!=saved[i]) restored=0;
    if (!restored || !o->perst_low(ctx) || o->read(ctx,0x0c)!=0)
        return -3;
    return ret;
}
#endif
