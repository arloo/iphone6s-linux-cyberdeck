/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_ENDPOINT_BAR_SIZE_TRIAL_H
#define N71_ENDPOINT_BAR_SIZE_TRIAL_H
struct n71_bar_ops {int (*ready)(void *);unsigned int (*read)(void *,unsigned int);void (*write)(void *,unsigned int,unsigned int);};
struct n71_bar_result {unsigned int size[2],mask_lo[2],mask_hi[2],restored;};
/* Only the two known 64-bit memory BARs at offsets10/18; no command write.
 * Decode/master must already be OFF. Always restore high then low on failure.
 */
static int n71_endpoint_bar_size_trial(const struct n71_bar_ops *o,void *ctx,struct n71_bar_result *r)
{
    unsigned int i,off,lo,hi,ml,mh;
    unsigned long long mask,size;
    int rc;
    r->restored=1;
    for(i=0;i<2;i++)r->size[i]=r->mask_lo[i]=r->mask_hi[i]=0;
    for(i=0;i<2;i++) {
        off=0x10+8*i;rc=-1;
        if(!o->ready(ctx)||(o->read(ctx,4)&0xffff))return -1;
        lo=o->read(ctx,off);hi=o->read(ctx,off+4);
        if(lo!=4||hi)return -2;
        if(!o->ready(ctx))return -1;
        o->write(ctx,off,~0U);
        if(!o->ready(ctx))goto restore;
        o->write(ctx,off+4,~0U);
        if(!o->ready(ctx))goto restore;
        ml=o->read(ctx,off);
        if(!o->ready(ctx))goto restore;
        mh=o->read(ctx,off+4);
        r->mask_lo[i]=ml;r->mask_hi[i]=mh;
        mask=((unsigned long long)mh<<32)|(ml&~15U);size=~mask+1;
        if((ml&15)!=4||size<0x1000||size>0x10000000ULL||(size&(size-1))) {rc=-2;goto restore;}
        r->size[i]=(unsigned int)size;
        rc=o->ready(ctx)&&!(o->read(ctx,4)&0xffff)?0:-1;
restore:
        o->write(ctx,off+4,hi);o->write(ctx,off,lo);
        if(o->read(ctx,off)!=lo||o->read(ctx,off+4)!=hi){r->restored=0;return -3;}
        if(rc)return rc;
    }
    return o->ready(ctx)?0:-1;
}
#endif
