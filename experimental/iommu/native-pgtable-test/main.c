// SPDX-License-Identifier: GPL-2.0-only
/* CPU-only Linux native DART table allocation/map/unmap test. No MMIO or DMA. */
#include <linux/module.h>
#include <linux/io-pgtable.h>
#include <linux/mm.h>
#include <linux/sizes.h>
#include <linux/io.h>
#include <linux/iommu.h>
static bool armed;
module_param(armed,bool,0400);
extern struct io_pgtable_init_fns n71_pgtable_init_fns;
static int run(bool corrected,unsigned long buffer)
{
 struct io_pgtable_cfg cfg={.pgsize_bitmap=SZ_4K,.ias=32,.oas=36,.coherent_walk=true};
 struct io_pgtable_ops *ops=NULL;struct io_pgtable *iop=NULL;
 const unsigned long iovas[]={0x1000,0x40001000,0x80001000,0xc0001000};
 const u64 pa_mask=GENMASK_ULL(35,12);
 unsigned int i,maps=0;size_t mapped;int rc=-EINVAL;
 if(corrected){cfg.quirks=IO_PGTABLE_QUIRK_APPLE_DART_S5L8960X;iop=n71_pgtable_init_fns.alloc(&cfg,NULL);if(!iop)return -ENOMEM;iop->fmt=APPLE_DART;iop->cfg=cfg;iop->cookie=NULL;ops=&iop->ops;}
 else ops=alloc_io_pgtable_ops(APPLE_DART,&cfg,NULL);
 if(!ops)return -ENOMEM;
 if(cfg.apple_dart_cfg.n_ttbrs!=4||cfg.apple_dart_cfg.n_levels!=3)goto out;
 for(i=0;i<ARRAY_SIZE(iovas);i++) {
  u64 *root,*leaf,table,pte;
  mapped=0;rc=ops->map_pages(ops,iovas[i],virt_to_phys((void*)buffer),SZ_4K,1,IOMMU_READ|IOMMU_WRITE,GFP_KERNEL,&mapped);
  if(rc||mapped!=SZ_4K){rc=-EIO;goto out;}maps++;
  root=phys_to_virt(cfg.apple_dart_cfg.ttbr[i]);table=root[(iovas[i]>>21)&511];
  leaf=phys_to_virt(table&pa_mask);pte=leaf[(iovas[i]>>12)&511];
  if((table&3)!=(corrected?3:1)||(pte&3)!=3||(pte&pa_mask)!=virt_to_phys((void*)buffer)||
     ((pte>>40)!=0)==corrected||ops->iova_to_phys(ops,iovas[i]+123)!=virt_to_phys((void*)buffer)+123){rc=-EILSEQ;goto out;}
 }
 rc=0;
out:
 for(i=0;i<maps;i++) {
  if(ops->unmap_pages(ops,iovas[i],SZ_4K,1,NULL)!=SZ_4K||ops->iova_to_phys(ops,iovas[i]))rc=-EIO;
 }
 if(corrected)n71_pgtable_init_fns.free(iop);else free_io_pgtable_ops(ops);
 pr_info("n71-pgtable: CPU_ONLY corrected=%u rc=%d mapped_roots=%u unmap_checked=1 tables_freed=1 NO_MMIO_NO_DMA\n",corrected,rc,maps);
 return rc;
}
static int __init test_init(void)
{
 unsigned long buffer;int rc;
 if(!armed){pr_info("n71-pgtable: UNARMED no allocations or hardware actions\n");return 0;}
 buffer=__get_free_pages(GFP_KERNEL|__GFP_ZERO,0);if(!buffer)return -ENOMEM;
 rc=run(false,buffer);if(!rc)rc=run(true,buffer);free_pages(buffer,0);
 if(!rc)pr_info("n71-pgtable: BASELINE_AND_S5L8960X_TABLE_FORMAT_CPU_TEST_PASS no_DART_programmed\n");
 return rc;
}
static void __exit test_exit(void){}
module_init(test_init);module_exit(test_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 CPU-only native DART table format comparison, no MMIO/DMA");
