// SPDX-License-Identifier: GPL-2.0-only
#include <linux/io-pgtable.h>
extern struct io_pgtable_init_fns n71_pgtable_init_fns;
struct io_pgtable_ops *n71_alloc_io_pgtable_ops(enum io_pgtable_fmt,struct io_pgtable_cfg *,void *);
void n71_free_io_pgtable_ops(struct io_pgtable_ops *);
struct io_pgtable_ops *n71_alloc_io_pgtable_ops(enum io_pgtable_fmt fmt,struct io_pgtable_cfg *cfg,void *cookie)
{
 struct io_pgtable *iop;
 if(fmt!=APPLE_DART||!(cfg->quirks&IO_PGTABLE_QUIRK_APPLE_DART_S5L8960X))return NULL;
 iop=n71_pgtable_init_fns.alloc(cfg,cookie);if(!iop)return NULL;
 iop->fmt=fmt;iop->cfg=*cfg;iop->cookie=cookie;return &iop->ops;
}
void n71_free_io_pgtable_ops(struct io_pgtable_ops *ops)
{
 struct io_pgtable *iop;
 if(!ops)return;
 iop=io_pgtable_ops_to_pgtable(ops);
 io_pgtable_tlb_flush_all(iop);n71_pgtable_init_fns.free(iop);
}
