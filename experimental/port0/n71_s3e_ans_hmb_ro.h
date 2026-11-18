/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ANS_HMB_RO_H
#define N71_S3E_ANS_HMB_RO_H
/* Apple IONVMeFamily reads 0x1808 and programs 0x1810/0x1818.
 * This descriptor observer has no write operation and does not start ANS.
 * An absent (zero) HMB request is a valid diagnostic, not usable memory.
 */
struct n71_ans_hmb_ops {
    int (*ready)(void *);
    unsigned int (*read)(void *,unsigned int);
};
struct n71_ans_hmb_result {
    unsigned int request,base_lo,base_hi,size,request_again,reads;
    unsigned int stable,nonzero,aligned;
};
static int n71_ans_hmb_ro(const struct n71_ans_hmb_ops *o,void *ctx,
                         struct n71_ans_hmb_result *r)
{
    unsigned int i;
    unsigned int offsets[5]={0x1808,0x1810,0x1814,0x1818,0x1808};
    unsigned int values[5]={0,0,0,0,0};
    r->request=r->base_lo=r->base_hi=r->size=r->request_again=r->reads=0;
    r->stable=r->nonzero=r->aligned=0;
    for (i=0;i<5;i++) {
        if (!o->ready(ctx)) return -1;
        values[i]=o->read(ctx,offsets[i]);
        r->reads++;
    }
    r->request=values[0];r->base_lo=values[1];r->base_hi=values[2];
    r->size=values[3];r->request_again=values[4];
    r->stable=values[0]==values[4];
    r->nonzero=values[0]!=0;
    r->aligned=(values[0]&4095U)==0;
    if (!o->ready(ctx)) return -1;
    if (!r->stable || values[0]==~0U || values[1]==~0U ||
        values[2]==~0U || values[3]==~0U) return -2;
    return 0;
}
#endif
