/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_NVMMU_OWNED_TABLES_H
#define N71_S3E_NVMMU_OWNED_TABLES_H
struct n71_nvmmu_ops {
    unsigned int (*read)(void *,unsigned int);
    void (*write)(void *,unsigned int,unsigned int);
    int (*ready)(void *); /* full DART guard AND physically asserted PERST */
    void (*tick)(void *);
    int (*active_hold)(void *); /* must reassert PERST before return */
};
struct n71_nvmmu_result {
    unsigned int restored,owned_polls,restore_polls,last;
};
static int n71_nvmmu_flush(const struct n71_nvmmu_ops *o,void *ctx,
                          unsigned int *last,unsigned int *polls)
{
    unsigned int i;
    *polls=0;
    if (!o->ready(ctx) || o->read(ctx,4)!=0) return -3;
    o->write(ctx,4,0x10000U);
    for (i=0;i<1000;i++) {
        *last=o->read(ctx,4);*polls=i+1;
        if (!o->ready(ctx)) return -3;
        if (!(*last&0x10000U)) return *last ? -3 : 0;
        o->tick(ctx);
    }
    return -3;
}
/* Both buffers belong to the caller and are zeroed/DMA-synchronized.
 * Original source: aux4KiB at+10/+14, TCB16KiB at+08/+0c, then bounded
 * invalidate+04 bit16. No control/SART/FIFO/NVMe writes. No DMA proof.
 * Unsafe timeout, observer or restore retains every owner and buffer.
 */
static int n71_nvmmu_owned_tables_trial(const struct n71_nvmmu_ops *o,
                void *ctx,unsigned long long tcb,unsigned long long aux,
                struct n71_nvmmu_result *r)
{
    static const unsigned int offsets[4]={0x10,0x14,8,0x0c};
    unsigned int saved[4],next[4],i;
    int rc=-2;
    r->restored=1;r->owned_polls=r->restore_polls=r->last=0;
    if (!o->ready(ctx) || o->read(ctx,0)!=1 || o->read(ctx,4)!=0 ||
        !tcb || !aux || (tcb&127) || (aux&4095) ||
        tcb>((1ULL<<36)-16384) || aux>((1ULL<<36)-4096) ||
        (tcb<aux+4096 && aux<tcb+16384)) return -1;
    next[0]=(unsigned int)aux;next[1]=(unsigned int)(aux>>32);
    next[2]=(unsigned int)tcb;next[3]=(unsigned int)(tcb>>32);
    for (i=0;i<4;i++) saved[i]=o->read(ctx,offsets[i]);
    for (i=0;i<4;i++) {
        if (!o->ready(ctx)) {r->restored=0;return -3;}
        o->write(ctx,offsets[i],next[i]);
        if (o->read(ctx,offsets[i])!=next[i]) goto restore;
    }
    if (n71_nvmmu_flush(o,ctx,&r->last,&r->owned_polls)) {
        r->restored=0;return -3;
    }
    rc=o->active_hold ? o->active_hold(ctx) : 0;
    if (rc==-3 || !o->ready(ctx) || o->read(ctx,4)!=0) {
        r->restored=0;return -3;
    }
restore:
    if (!o->ready(ctx) || o->read(ctx,4)!=0) {r->restored=0;return -3;}
    for (i=0;i<4;i++) {
        o->write(ctx,offsets[i],saved[i]);
        if (o->read(ctx,offsets[i])!=saved[i]) {r->restored=0;return -3;}
    }
    if (n71_nvmmu_flush(o,ctx,&r->last,&r->restore_polls)) {
        r->restored=0;return -3;
    }
    for (i=0;i<4;i++) if (o->read(ctx,offsets[i])!=saved[i]) r->restored=0;
    if (o->read(ctx,0)!=1 || !o->ready(ctx)) r->restored=0;
    return r->restored ? rc : -3;
}
#endif
