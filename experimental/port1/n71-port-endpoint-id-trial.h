/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_ENDPOINT_ID_TRIAL_H
#define N71_PORT_ENDPOINT_ID_TRIAL_H
struct n71_endpoint_ops {
    int (*ready)(void *);
    unsigned int (*root_read)(void *, unsigned int);
    void (*root_bus_write)(void *, unsigned int);
    unsigned int (*endpoint_read)(void *, unsigned int);
};
struct n71_endpoint_result { unsigned int id, command, class_rev, saved_bus, restored, reads; };
/* No command/BAR/window writes, enumeration, DMA or driver registration.
 * Assign bus1 only while this port's downstream link and empty DART guard hold.
 */
static int n71_endpoint_id_trial(const struct n71_endpoint_ops *o, void *ctx,
                                struct n71_endpoint_result *r)
{
    unsigned int saved, target, i, words[3] = {0};
    int rc = -1;
    r->id = r->command = r->class_rev = r->saved_bus = r->restored = r->reads = 0;
    if (!o->ready(ctx) || o->root_read(ctx, 0) != 0x1004106bU) return -1;
    saved = o->root_read(ctx, 0x18); r->saved_bus = saved;
    if (saved & 0x00ffffffU) return -1;
    target = (saved & 0xff000000U) | 0x00010100U;
    if (!o->ready(ctx)) return -1;
    o->root_bus_write(ctx, target);
    if (o->root_read(ctx, 0x18) != target) goto restore;
    for (i = 0; i < 3; i++) {
        if (!o->ready(ctx)) goto restore;
        words[i] = o->endpoint_read(ctx, i * 4); r->reads++;
        if (!i && (words[0] & 0xffff) != 0x14e4) { rc = -2; goto restore; }
    }
    rc = o->ready(ctx) ? 0 : -1;
restore:
    r->id = words[0]; r->command = words[1]; r->class_rev = words[2];
    o->root_bus_write(ctx, saved);
    r->restored = o->root_read(ctx, 0x18) == saved;
    return r->restored ? rc : -3;
}
#endif
