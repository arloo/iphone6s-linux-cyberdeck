/* SPDX-License-Identifier: GPL-2.0-only */
/* Hardware-independent sequence; caller supplies bounded MMIO and PERST checks. */
#ifndef N71_DART_TTBR_DISABLED_TRIAL_H
#define N71_DART_TTBR_DISABLED_TRIAL_H
struct n71_dart_trial_ops {
    unsigned int (*read)(void *, unsigned int);
    void (*write)(void *, unsigned int, unsigned int);
    int (*perst_low)(void *);
    void (*hold)(void *);
};
static int n71_dart_disabled_ttbr_trial(const struct n71_dart_trial_ops *o,
                                      void *ctx, unsigned int *zero_pass,
                                      unsigned int *restore_pass)
{
    unsigned int saved[16], command, fault, i;
    int result = 0;
    *zero_pass = *restore_pass = 0;
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0) return -1;
    command = o->read(ctx, 0x00);
    fault = o->read(ctx, 0x10);
    if ((command & 8) || (fault & 0x80000000U)) return -1;
    for (i = 0; i < 16; i++) saved[i] = o->read(ctx, 0x40 + 4*i);
    for (i = 0; i < 4; i++) {
        if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0) { result = -2; goto restore; }
        o->write(ctx, 0x40 + 4*i, 0);
        if (o->read(ctx, 0x40 + 4*i) != 0) { result = -2; goto restore; }
    }
    o->hold(ctx);
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0 ||
        o->read(ctx, 0x00) != command || o->read(ctx, 0x10) != fault) result = -2;
    for (i = 0; i < 16; i++)
        if (o->read(ctx, 0x40 + 4*i) != (i < 4 ? 0 : saved[i])) result = -2;
    if (!result) *zero_pass = 1;
restore:
    /* Always restore only stream0's four cells, including on readback failure. */
    for (i = 0; i < 4; i++) o->write(ctx, 0x40 + 4*i, saved[i]);
    *restore_pass = 1;
    for (i = 0; i < 16; i++)
        if (o->read(ctx, 0x40 + 4*i) != saved[i]) *restore_pass = 0;
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0 ||
        o->read(ctx, 0x00) != command || o->read(ctx, 0x10) != fault) *restore_pass = 0;
    return *restore_pass ? result : -3;
}
/* Register pulse only: no TLB flush and no claim of DMA containment. */
static int n71_dart_tcr0_pulse(const struct n71_dart_trial_ops *o, void *ctx)
{
    unsigned int i;
    int ret = 0;
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0) return -1;
    for (i = 0; i < 4; i++) if (o->read(ctx, 0x40 + 4*i) != 0) return -1;
    o->write(ctx, 0x0c, 0x80);
    if (o->read(ctx, 0x0c) != 0x80 || !o->perst_low(ctx)) ret = -1;
    if (!ret) {
        o->hold(ctx);
        if (o->read(ctx, 0x0c) != 0x80 || !o->perst_low(ctx)) ret = -1;
    }
    o->write(ctx, 0x0c, 0);
    if (o->read(ctx, 0x0c) != 0) ret = -2;
    return ret;
}
#endif
