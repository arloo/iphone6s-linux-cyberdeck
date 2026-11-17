/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ENDPOINT_CFG_RO_H
#define N71_S3E_ENDPOINT_CFG_RO_H
struct n71_s3e_cfg_ops {
    int (*ready)(void *);
    unsigned int (*root_read)(void *,unsigned int);
    void (*root_bus_write)(void *,unsigned int);
    unsigned int (*endpoint_read)(void *,unsigned int);
    int (*observe)(void *);
};
struct n71_s3e_cfg_result {
    unsigned int id,command,class_rev,saved_bus,restored,reads;
};
/* The supervisor reserves bus2 before entry. Endpoint header reads only;
 * root routing is temporarily changed and restored. The optional observer
 * owns any separately guarded config/MMIO transaction; this helper itself
 * changes only the temporary bus route.
 * Return -3 means routing rollback failed: retain active empty DART roots.
 */
static int n71_s3e_endpoint_cfg_trial(const struct n71_s3e_cfg_ops *o,
                          void *ctx,struct n71_s3e_cfg_result *r)
{
    unsigned int saved,target,i,words[3]={0};
    int rc=-1;
    r->id=r->command=r->class_rev=r->saved_bus=r->restored=r->reads=0;
    if (!o->ready(ctx) || o->root_read(ctx,0)!=0x1003106bU ||
        (o->root_read(ctx,8)>>16)!=0x0604U ||
        (o->root_read(ctx,4)&0xffffU)!=0) return -1;
    saved=o->root_read(ctx,0x18);
    r->saved_bus=saved;
    if (saved & 0x00ffffffU) return -1;
    target=(saved & 0xff000000U)|0x00020200U;
    if (!o->ready(ctx)) return -1;
    o->root_bus_write(ctx,target);
    if (o->root_read(ctx,0x18)!=target) goto restore;
    for (i=0;i<3;i++) {
        if (!o->ready(ctx)) goto restore;
        words[i]=o->endpoint_read(ctx,4*i);
        r->reads++;
        if (!i && words[0]!=0x2002106bU) {rc=-2;goto restore;}
        if (i==1 && (words[1]&4)) {rc=-4;goto restore;}
    }
    rc=o->ready(ctx) && (words[2]>>8)==0x018002U ? 0 : -2;
    if (!rc && o->observe) rc=o->observe(ctx);
restore:
    r->id=words[0];r->command=words[1];r->class_rev=words[2];
    o->root_bus_write(ctx,saved);
    r->restored=o->root_read(ctx,0x18)==saved;
    return r->restored ? rc : -3;
}
#endif
