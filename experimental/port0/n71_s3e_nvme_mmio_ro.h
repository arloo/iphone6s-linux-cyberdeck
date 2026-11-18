/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_NVME_MMIO_RO_H
#define N71_S3E_NVME_MMIO_RO_H
struct n71_s3e_mmio_ops {
    int (*ready)(void *);
    unsigned int (*root_read)(void *,unsigned int);
    unsigned int (*endpoint_read)(void *,unsigned int);
    void (*root_window)(void *,unsigned int);
    void (*endpoint_bar)(void *,unsigned int,unsigned int);
    void (*root_command)(void *,unsigned int);
    void (*endpoint_command)(void *,unsigned int);
    unsigned int (*nvme_read)(void *,unsigned int);
    int (*active_readonly)(void *); /* optional, while BAR decode is active */
};
struct n71_s3e_mmio_result {
    unsigned int cap_lo,cap_hi,vs,cc,csts,reads,restored;
    unsigned int stage,root_window,pref_window,pref_hi_base,pref_hi_limit;
};
/* Physical BAR0 geometry must have passed immediately before entry.
 * Supervisor exclusively reserves CPU7c1000000..7c1003fff, corresponding
 * to bus c1000000 in the original N71 apcie non-prefetchable range.
 * Only BAR0, bridge memory window and 16-bit MSE command change.
 * Bus mastering never enabled. Five NVMe DWORD reads plus an optional read-only observer, no NVMe writes.
 * Return -3 retains DART roots and the CPU resource reservation.
 */
static int n71_s3e_nvme_mmio_ro_trial(const struct n71_s3e_mmio_ops *o,
                               void *ctx,struct n71_s3e_mmio_result *r)
{
    unsigned int lo,hi,window,pf,type;
    unsigned long long pf_base,pf_limit;
    int rc=-1;
    r->cap_lo=r->cap_hi=r->vs=r->cc=r->csts=r->reads=0;
    r->restored=1;
    r->stage=r->root_window=r->pref_window=r->pref_hi_base=r->pref_hi_limit=0;
    if (!o->ready(ctx) || (o->root_read(ctx,4)&0xffffU) ||
        (o->endpoint_read(ctx,4)&0xffffU)) return -1;
    r->stage=1;
    lo=o->endpoint_read(ctx,0x10);hi=o->endpoint_read(ctx,0x14);
    if (lo!=4 || hi) return -2;
    r->stage=2;
    window=o->root_read(ctx,0x20);r->root_window=window;
    /* Existing prefetch routes must overlap neither WLAN nor S3E. A reset
     * window covering unrelated bus addresses need not be rewritten. */
    pf=o->root_read(ctx,0x24);r->pref_window=pf;type=pf&15;
    if (type>1 || ((pf>>16)&15)!=type) return -2;
    pf_base=(unsigned long long)(pf&0xfff0U)<<16;
    pf_limit=(pf&0xfff00000U)|0x000fffffU;
    if (type==1) {
        r->pref_hi_base=o->root_read(ctx,0x28);
        r->pref_hi_limit=o->root_read(ctx,0x2c);
        pf_base|=(unsigned long long)r->pref_hi_base<<32;
        pf_limit|=(unsigned long long)r->pref_hi_limit<<32;
    }
    if (pf_base<=pf_limit &&
        ((pf_base<=0xc07fffffULL && pf_limit>=0xc0000000ULL) ||
         (pf_base<=0xc10fffffULL && pf_limit>=0xc1000000ULL))) return -2;
    if (!o->ready(ctx)) return -1;
    r->stage=3;
    o->endpoint_bar(ctx,0x14,0);
    o->endpoint_bar(ctx,0x10,0xc1000004U);
    o->root_window(ctx,0xc100c100U);
    if (!o->ready(ctx) || o->endpoint_read(ctx,0x10)!=0xc1000004U ||
        o->endpoint_read(ctx,0x14) || o->root_read(ctx,0x20)!=0xc100c100U)
        goto restore;
    r->stage=4;
    o->root_command(ctx,2);o->endpoint_command(ctx,2);
    if (!o->ready(ctx) || (o->root_read(ctx,4)&0xffffU)!=2 ||
        (o->endpoint_read(ctx,4)&0xffffU)!=2) goto restore;
    r->stage=5;
    /* Offsets match the running kernel's include/linux/nvme.h. */
    r->cap_lo=o->nvme_read(ctx,0);r->reads++;
    r->cap_hi=o->nvme_read(ctx,4);r->reads++;
    r->vs=o->nvme_read(ctx,8);r->reads++;
    r->cc=o->nvme_read(ctx,0x14);r->reads++;
    r->csts=o->nvme_read(ctx,0x1c);r->reads++;
    rc=0;
    if ((!r->cap_lo && !r->cap_hi) ||
        (r->cap_lo==~0U && r->cap_hi==~0U) ||
        (r->vs>>16)<1 || (r->vs>>16)>2 || r->cc==~0U || r->csts==~0U)
        rc=-2;
    if (!o->ready(ctx)) rc=-1;
    if (!rc && o->active_readonly) {
        rc=o->active_readonly(ctx);
        if (rc==-3) {r->restored=0;return -3;}
        if (!o->ready(ctx)) rc=-1;
    }
restore:
    o->endpoint_command(ctx,0);o->root_command(ctx,0);
    if ((o->endpoint_read(ctx,4)&0xffffU) ||
        (o->root_read(ctx,4)&0xffffU)) {r->restored=0;return -3;}
    o->endpoint_bar(ctx,0x14,hi);o->endpoint_bar(ctx,0x10,lo);
    o->root_window(ctx,window);
    r->restored=o->endpoint_read(ctx,0x10)==lo &&
        o->endpoint_read(ctx,0x14)==hi && o->root_read(ctx,0x20)==window;
    return r->restored ? rc : -3;
}
#endif
