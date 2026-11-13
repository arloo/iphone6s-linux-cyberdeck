/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PORT_CALIBRATION_TRIAL_H
#define N71_PORT_CALIBRATION_TRIAL_H
#define N71_CALIB_MAX 96
struct n71_calib_record { unsigned int bank, off, mask, value; };
struct n71_calib_ops {
    unsigned int (*read)(void *, unsigned int, unsigned int);
    void (*write)(void *, unsigned int, unsigned int, unsigned int);
    int (*perst_level)(void *);
    int (*dart_ready)(void *);
    int (*run)(void *, unsigned int *, unsigned int *, unsigned int *);
};
static int n71_calib_allowed(const struct n71_calib_record *r)
{
    static const unsigned int common[] = {8,12,16,24,28,40,48,256,260,264,268,272,288,296,304,308,384,400,416,424,432,436,512,528,544,552,560,564,640,656,672,680,688,692};
    static const unsigned int port[] = {0x90,0x130,0x134,0x138,0x13c,0x140};
    unsigned int i;
    if (!r->mask || (r->value & ~r->mask) || (r->off & 3)) return 0;
    if (r->bank == 0) {
        /* Never allow common tunables to toggle another port's enable. */
        if ((r->off == 0x100 || r->off == 0x180 || r->off == 0x200 || r->off == 0x280) && (r->mask & 1)) return 0;
        for (i = 0; i < sizeof(common)/sizeof(common[0]); i++) if (r->off == common[i]) return 1;
        return 0;
    }
    if (r->bank == 1) return r->off < 0x4000;
    if (r->bank == 2) {
        for (i = 0; i < sizeof(port)/sizeof(port[0]); i++) if (r->off == port[i]) return 1;
    }
    return 0;
}
/* Owner-private original records only. Shared tuning is intentionally included,
 * with other PCIe domains OFF. No PCI configuration aperture or endpoint DMA.
 */
static int n71_port_calibration_trial(const struct n71_calib_ops *o, void *ctx,
                                     const struct n71_calib_record *r, unsigned int count,
                                     unsigned int *status, unsigned int *samples,
                                     unsigned int *port_restored, unsigned int *restored,
                                     unsigned int *written)
{
    unsigned int saved[N71_CALIB_MAX], i, j, after;
    int rc = -1;
    *status = *samples = *port_restored = *restored = *written = 0;
    if (!count || count > N71_CALIB_MAX || o->perst_level(ctx) != 0 || !o->dart_ready(ctx)) return -1;
    for (i = 0; i < count; i++) {
        if (!n71_calib_allowed(&r[i])) return -1;
        for (j = 0; j < i; j++) if (r[i].bank == r[j].bank && r[i].off == r[j].off) return -1;
    }
    for (i = 0; i < count; i++) saved[i] = o->read(ctx, r[i].bank, r[i].off);
    for (i = 0; i < count; i++) {
        if (o->perst_level(ctx) != 0 || !o->dart_ready(ctx)) goto restore;
        after = (saved[i] & ~r[i].mask) | r[i].value;
        o->write(ctx, r[i].bank, r[i].off, after);
        *written = i + 1;
        if (o->read(ctx, r[i].bank, r[i].off) != after) goto restore;
    }
    rc = o->run(ctx, status, samples, port_restored);
restore:
    if (o->perst_level(ctx) != 0) return -3;
    *restored = 1;
    for (i = *written; i > 0; i--) {
        j = i - 1;
        after = o->read(ctx, r[j].bank, r[j].off);
        after = (after & ~r[j].mask) | (saved[j] & r[j].mask);
        o->write(ctx, r[j].bank, r[j].off, after);
    }
    for (i = 0; i < count; i++)
        if (o->read(ctx, r[i].bank, r[i].off) != saved[i]) *restored = 0;
    return *restored ? rc : -2;
}
#endif
