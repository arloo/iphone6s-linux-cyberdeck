/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_SART_HMB_OWNED_H
#define N71_S3E_SART_HMB_OWNED_H
struct n71_sart_ops {
    int (*ready)(void *);
    unsigned int (*read)(void *,unsigned int);
    void (*write)(void *,unsigned int,unsigned int);
    int (*active_hold)(void *);
};
struct n71_sart_result {
    unsigned int inherited_enabled,installed,restored,stage;
    unsigned int observed[4];
    int inner_rc;
};
/* Caller owns an 8 MiB, 1 MiB aligned direct-physical buffer.
 * S8000 writes low-30-bit VA offsets; readback has bit31 forced high.
 * NAND PERST is low for all SART changes. The callback may release it,
 * but must reassert it before returning. -3 retains the owned mapping.
 */
static int n71_sart_hmb_owned_trial(const struct n71_sart_ops *o,void *ctx,
                         unsigned long long pa,struct n71_sart_result *r)
{
    unsigned int old[4],i;
    int rc=-1;
    r->inherited_enabled=r->installed=r->stage=0;r->restored=1;r->inner_rc=-1;
    for (i=0;i<4;i++) r->observed[i]=0;
    if (!o->ready(ctx) || (pa&0xfffffULL) || pa>((1ULL<<36)-0x800000ULL))
        return -1;
    for (i=0;i<4;i++) old[i]=o->read(ctx,0x20+4*i);
    r->inherited_enabled=old[0];
    if (old[0]>1) return -2;
    r->stage=1;
    o->write(ctx,0x20,0);
    if (o->read(ctx,0x20)) {r->restored=0;return -3;}
    if (!o->ready(ctx)) {r->restored=0;return -3;}
    o->write(ctx,0x24,0x3c000000U);
    o->write(ctx,0x28,0x3c700000U);
    o->write(ctx,0x2c,(unsigned int)(pa>>20));
    r->stage=2;
    for (i=0;i<4;i++) r->observed[i]=o->read(ctx,0x20+4*i);
    if (r->observed[1]!=0xbc000000U || r->observed[2]!=0xbc700000U ||
        r->observed[3]!=(pa>>20)) {rc=-2;goto restore;}
    r->stage=3;
    o->write(ctx,0x20,1);
    for (i=0;i<4;i++) r->observed[i]=o->read(ctx,0x20+4*i);
    if (o->read(ctx,0x20)==1 && o->read(ctx,0x24)==0xbc000000U &&
        o->read(ctx,0x28)==0xbc700000U && o->read(ctx,0x2c)==(pa>>20) &&
        o->ready(ctx)) {
        r->installed=1;r->stage=4;
        rc=r->inner_rc=o->active_hold(ctx);
        if (rc==-3) {r->restored=0;return -3;}
    }
restore:
    if (!o->ready(ctx)) {r->restored=0;return -3;}
    o->write(ctx,0x20,0);
    if (o->read(ctx,0x20)) {r->restored=0;return -3;}
    /* Preserve the complete inherited descriptor, including disabled fields. */
    for (i=1;i<4;i++) o->write(ctx,0x20+4*i,old[i]);
    o->write(ctx,0x20,old[0]);
    for (i=0;i<4;i++)
        if (o->read(ctx,0x20+4*i)!=old[i]) r->restored=0;
    return r->restored ? rc : -3;
}
#endif
