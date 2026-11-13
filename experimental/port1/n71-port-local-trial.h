/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_LOCAL_TRIAL_H
#define N71_PORT_LOCAL_TRIAL_H
struct n71_port_trial_ops {
    unsigned int (*read)(void *, unsigned int);
    void (*write)(void *, unsigned int, unsigned int);
    int (*perst_level)(void *);
    void (*set_perst)(void *, int);
    int (*dart_ready)(void *);
    void (*delay)(void *);
};
/* Exact original port-local control bit; status meaning qualified separately.
 * Cleanup reasserts reset before returning to the enclosing DART transaction.
 */
static int n71_port_local_trial(const struct n71_port_trial_ops *o, void *ctx,
                               int release, unsigned int *status,
                               unsigned int *samples, unsigned int *restored)
{
    unsigned int saved, i;
    int ret = -1, attempted = 0;
    *samples = *restored = 0;
    *status = 0;
    if (o->perst_level(ctx) != 0 || !o->dart_ready(ctx)) return -1;
    saved = o->read(ctx, 0x80);
    if (saved != 0 || (release && !o->set_perst)) return -1;
    o->write(ctx, 0x80, 1);
    if (o->read(ctx, 0x80) != 1 || !o->dart_ready(ctx)) goto restore;
    if (release) {
        attempted = 1;
        o->set_perst(ctx, 1);
        if (o->perst_level(ctx) != 1) goto restore;
    }
    ret = 0;
    for (i = 0; i < 25; i++) {
        o->delay(ctx);
        if (o->perst_level(ctx) != (release ? 1 : 0) ||
            !o->dart_ready(ctx) || o->read(ctx, 0x80) != 1) { ret = -1; break; }
        *status = o->read(ctx, 0x88);
        *samples = i + 1;
    }
restore:
    if (attempted) o->set_perst(ctx, 0);
    if (o->perst_level(ctx) != 0) return -3;
    o->write(ctx, 0x80, saved);
    if (o->read(ctx, 0x80) != saved) return -2;
    *restored = 1;
    return ret;
}
#endif
