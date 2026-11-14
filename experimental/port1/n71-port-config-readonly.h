/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_CONFIG_READONLY_H
#define N71_PORT_CONFIG_READONLY_H
struct n71_config_ro_ops {
    int (*ready)(void *);
    unsigned int (*read)(void *, unsigned int);
};
struct n71_config_ro_result { unsigned int id, command, class_rev, buses, reads; };
/* Fixed port1 root bridge header only. No config write or downstream request. */
static int n71_port_config_readonly(const struct n71_config_ro_ops *o, void *ctx,
                                   struct n71_config_ro_result *r)
{
    static const unsigned int offsets[] = {0,4,8,0x18};
    unsigned int words[4] = {0}, i;
    r->id = r->command = r->class_rev = r->buses = r->reads = 0;
    for (i = 0; i < 4; i++) {
        if (!o->ready(ctx)) return -1;
        words[i] = o->read(ctx, offsets[i]);
        r->reads++;
        if (!i && words[0] != 0x1004106bU) { r->id = words[0]; return -2; }
    }
    r->id = words[0]; r->command = words[1];
    r->class_rev = words[2]; r->buses = words[3];
    if ((r->class_rev >> 16) != 0x0604) return -2;
    return o->ready(ctx) ? 0 : -1;
}
#endif
