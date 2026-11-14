/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_ENDPOINT_MMIO_TRIAL_H
#define N71_ENDPOINT_MMIO_TRIAL_H
struct n71_mmio_ops {
 int (*ready)(void *);unsigned int (*root_read)(void *,unsigned int);unsigned int (*endpoint_read)(void *,unsigned int);
 void (*root_write)(void *,unsigned int,unsigned int);void (*endpoint_write)(void *,unsigned int,unsigned int);
 void (*root_command)(void *,unsigned int);void (*endpoint_command)(void *,unsigned int);
 unsigned int (*chip_read)(void *);
 int (*observe)(void *);
};
struct n71_mmio_result {unsigned int chip,restored,reads;};
/* Original N71 nonprefetchable range: bus c0000000 -> CPU7c0000000.
 * BAR0=32KiB at c0000000, BAR2=4MiB at c0400000. Memory decode only,
 * bus mastering never enabled. Command uses16-bit operations to avoid W1C status.
 */
static int n71_endpoint_mmio_trial(const struct n71_mmio_ops *o,void *ctx,struct n71_mmio_result *r)
{
 unsigned int rootwin,window,b[4],i;
 int rc=-1;
 r->chip=r->reads=0;r->restored=1;
 if(!o->ready(ctx)||(o->root_read(ctx,4)&0xffff)||(o->endpoint_read(ctx,4)&0xffff))return -1;
 for(i=0;i<4;i++)b[i]=o->endpoint_read(ctx,0x10+4*i);
 if(b[0]!=4||b[1]||b[2]!=4||b[3])return -2;
 rootwin=o->root_read(ctx,0x20);window=o->endpoint_read(ctx,0x80);
 if(!o->ready(ctx))return -1;
 o->endpoint_write(ctx,0x14,0);o->endpoint_write(ctx,0x10,0xc0000004U);
 o->endpoint_write(ctx,0x1c,0);o->endpoint_write(ctx,0x18,0xc0400004U);
 o->root_write(ctx,0x20,0xc070c000U);
 o->endpoint_write(ctx,0x80,0x18000000U);
 if(!o->ready(ctx)||o->endpoint_read(ctx,0x10)!=0xc0000004U||o->endpoint_read(ctx,0x14)||
    o->endpoint_read(ctx,0x18)!=0xc0400004U||o->endpoint_read(ctx,0x1c)||
    o->endpoint_read(ctx,0x80)!=0x18000000U||o->root_read(ctx,0x20)!=0xc070c000U)goto restore;
 o->root_command(ctx,2);o->endpoint_command(ctx,2);
 if(!o->ready(ctx)||(o->root_read(ctx,4)&0xffff)!=2||(o->endpoint_read(ctx,4)&0xffff)!=2)goto restore;
 r->chip=o->chip_read(ctx);r->reads=1;
 rc=(r->chip&0xffff)==0x4350?0:-2;
 if(!o->ready(ctx))rc=-1;
 if(!rc && o->observe)rc=o->observe(ctx);
restore:
 o->endpoint_command(ctx,0);o->root_command(ctx,0);
 /* Do not rewrite live BARs if decode/master did not clear. */
 if((o->endpoint_read(ctx,4)&0xffff)||(o->root_read(ctx,4)&0xffff)){r->restored=0;return -3;}
 o->endpoint_write(ctx,0x80,window);
 for(i=4;i>0;i--)o->endpoint_write(ctx,0x10+4*(i-1),b[i-1]);
 o->root_write(ctx,0x20,rootwin);
 if(o->endpoint_read(ctx,0x80)!=window||o->root_read(ctx,0x20)!=rootwin)r->restored=0;
 for(i=0;i<4;i++)if(o->endpoint_read(ctx,0x10+4*i)!=b[i])r->restored=0;
 return r->restored?rc:-3;
}
#endif
