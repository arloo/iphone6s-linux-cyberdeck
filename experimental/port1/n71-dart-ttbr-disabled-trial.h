/* SPDX-License-Identifier: GPL-2.0-only */
/* Hardware-independent sequence; caller supplies bounded MMIO and PERST checks. */
#ifndef N71_DART_TTBR_DISABLED_TRIAL_H
#define N71_DART_TTBR_DISABLED_TRIAL_H
struct n71_dart_trial_ops {
    unsigned int (*read)(void *, unsigned int);
    void (*write)(void *, unsigned int, unsigned int);
    int (*perst_low)(void *);
    void (*hold)(void *);
    void (*tick)(void *); /* one microsecond for bounded command polling */
    int (*active_hold)(void *); /* optional bounded dwell while TCR0=0x80 */
    unsigned int command_change_mask; /* only stream selector bits may differ */
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
        ((o->read(ctx, 0x00) ^ command) & ~o->command_change_mask) != 0 || o->read(ctx, 0x10) != fault) result = -2;
    for (i = 0; i < 16; i++)
        if (o->read(ctx, 0x40 + 4*i) != (i < 4 ? 0 : saved[i])) result = -2;
    if (!result) *zero_pass = 1;
restore:
    /* Never restore valid TTBRs if translation failed to disable. */
    if (o->read(ctx, 0x0c) != 0) return -3;
    /* Always restore only stream0's four cells, including on readback failure. */
    for (i = 0; i < 4; i++) o->write(ctx, 0x40 + 4*i, saved[i]);
    *restore_pass = 1;
    for (i = 0; i < 16; i++)
        if (o->read(ctx, 0x40 + 4*i) != saved[i]) *restore_pass = 0;
    if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0 ||
        ((o->read(ctx, 0x00) ^ command) & ~o->command_change_mask) != 0 || o->read(ctx, 0x10) != fault) *restore_pass = 0;
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
/* The S5L8960X command is SID0_SELECT | INVALIDATE (0x102).
 * Translation must be enabled for invalidation; PERST never leaves LOW.
 * Unlike stages 10/11, this changes command selection and invalidates SID0 TLB.
 * Does not restore the old f02 command: doing so would invalidate other streams.
 */
static int n71_dart_tcr0_flush_roots_trial(const struct n71_dart_trial_ops *o, void *ctx,
                                        const unsigned int roots[4],
                                        unsigned int *last, unsigned int *polls)
{
    unsigned int i, fault;
    int ret = -1;
    *polls = 0;
    *last = o->read(ctx, 0x00);
    if (!o->tick || !o->perst_low(ctx) || o->read(ctx, 0x0c) != 0 ||
        (*last & 8)) return -1;
    fault = o->read(ctx, 0x10);
    if (fault & 0x80000000U) return -1;
    for (i = 0; i < 4; i++) if (o->read(ctx, 0x40 + 4*i) != roots[i]) return -1;
    o->write(ctx, 0x0c, 0x80);
    if (o->read(ctx, 0x0c) != 0x80 || !o->perst_low(ctx)) goto disable;
    o->write(ctx, 0x00, 0x102);
    ret = -2;
    for (i = 0; i < 100; i++) {
        *last = o->read(ctx, 0x00);
        *polls = i + 1;
        if (!o->perst_low(ctx) || o->read(ctx, 0x0c) != 0x80) break;
        if (!(*last & 8)) { ret = *last == 0x102 ? 0 : -1; break; }
        o->tick(ctx);
    }
    if (!ret && o->active_hold) ret = o->active_hold(ctx);
    if (o->read(ctx, 0x10) != fault) ret = -1;
disable:
    /* A release trial must reassert endpoint reset before removing its guard.
     * If reset cannot be observed LOW, retain active roots for quarantine. */
    if (!o->perst_low(ctx)) return -3;
    o->write(ctx, 0x0c, 0);
    if (o->read(ctx, 0x0c) != 0) ret = -3;
    return ret;
}
static int n71_dart_tcr0_flush_trial(const struct n71_dart_trial_ops *o, void *ctx,
                                  unsigned int *last, unsigned int *polls)
{
    const unsigned int roots[4] = {0, 0, 0, 0};
    return n71_dart_tcr0_flush_roots_trial(o, ctx, roots, last, polls);
}
#endif
