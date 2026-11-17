/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_BAR0_SIZE_H
#define N71_S3E_BAR0_SIZE_H
struct n71_s3e_bar_ops {
    int (*ready)(void *);
    unsigned int (*read)(void *,unsigned int);
    void (*write)(void *,unsigned int,unsigned int);
};
struct n71_s3e_bar_result {
    unsigned int lo,hi,mask_lo,mask_hi,is64,restored;
    unsigned long long size;
};
/* Size only BAR0. Memory/I/O decode and bus mastering must already be OFF.
 * A 64-bit BAR pair is always restored high then low, including failures.
 * No command, status, bridge window or NVMe register write.
 */
static int n71_s3e_bar0_size_trial(const struct n71_s3e_bar_ops *o,void *ctx,
                                  struct n71_s3e_bar_result *r)
{
    unsigned int lo,hi=0,ml=0,mh=0xffffffffU,type;
    unsigned long long mask,size;
    int rc=-1;
    r->lo=r->hi=r->mask_lo=r->mask_hi=r->is64=0;
    r->size=0;r->restored=1;
    if (!o->ready(ctx) || (o->read(ctx,4)&0xffffU)) return -1;
    lo=o->read(ctx,0x10);type=(lo>>1)&3;
    r->lo=lo;
    if ((lo&1) || (type!=0 && type!=2)) return -2;
    r->is64=type==2;
    if (r->is64) hi=o->read(ctx,0x14);
    r->hi=hi;
    if (!o->ready(ctx)) return -1;
    o->write(ctx,0x10,~0U);
    if (!o->ready(ctx)) goto restore;
    if (r->is64) {
        o->write(ctx,0x14,~0U);
        if (!o->ready(ctx)) goto restore;
    }
    ml=o->read(ctx,0x10);
    if (!o->ready(ctx)) goto restore;
    if (r->is64) mh=o->read(ctx,0x14);
    r->mask_lo=ml;r->mask_hi=mh;
    mask=((unsigned long long)mh<<32)|(ml&~15U);
    size=~mask+1;
    if ((ml&15)!=(lo&15) || size<0x1000 || size>0x40000000ULL ||
        (size&(size-1))) {rc=-2;goto restore;}
    r->size=size;
    rc=o->ready(ctx) && !(o->read(ctx,4)&0xffffU) ? 0 : -1;
restore:
    /* Never rewrite a live BAR if decode or bus mastering became enabled. */
    if (o->read(ctx,4)&0xffffU) {r->restored=0;return -3;}
    if (r->is64) o->write(ctx,0x14,hi);
    o->write(ctx,0x10,lo);
    r->restored=o->read(ctx,0x10)==lo &&
                (!r->is64 || o->read(ctx,0x14)==hi);
    return r->restored ? rc : -3;
}
#endif
