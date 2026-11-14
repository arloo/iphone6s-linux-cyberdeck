/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_ENDPOINT_CONFIG_SNAPSHOT_H
#define N71_ENDPOINT_CONFIG_SNAPSHOT_H
struct n71_snapshot_ops { int (*ready)(void *); unsigned int (*read)(void *, unsigned int); };
struct n71_snapshot { unsigned int header, bars[6], caps, pcie, link, reads; };
static int n71_endpoint_snapshot(const struct n71_snapshot_ops *o, void *ctx, struct n71_snapshot *r)
{
    unsigned int i, ptr, h, seen[8] = {0};
    r->header = r->caps = r->pcie = r->link = r->reads = 0;
    for (i=0;i<6;i++) r->bars[i]=0;
    if (!o->ready(ctx)) return -1;
    r->header=o->read(ctx,0x0c);r->reads++;
    if ((r->header & 0x007f0000U) != 0) return -2;
    for(i=0;i<6;i++) {
        if (!o->ready(ctx)) return -1;
        r->bars[i]=o->read(ctx,0x10+4*i);r->reads++;
    }
    if (!o->ready(ctx)) return -1;
    ptr=o->read(ctx,0x34)&0xff;r->reads++;
    for(i=0;ptr && i<48;i++) {
        if (ptr<0x40 || ptr>0xfc || (ptr&3) || (seen[ptr/32] & (1U<<(ptr%32)))) return -2;
        seen[ptr/32] |= 1U<<(ptr%32);
        if(!o->ready(ctx)) return -1;
        h=o->read(ctx,ptr);r->reads++;r->caps++;
        if((h&0xff)==0x10) {
            if(r->pcie || ptr>0xec) return -2;
            r->pcie=ptr;
            if(!o->ready(ctx)) return -1;
            r->link=o->read(ctx,ptr+0x10);r->reads++;
        }
        ptr=(h>>8)&0xff;
    }
    if(ptr || !r->pcie) return -2;
    return o->ready(ctx)?0:-1;
}
#endif
