// SPDX-License-Identifier: GPL-2.0-only
#include <linux/iommu.h>
#include "native-blob.h"
extern int n71_native_driver_register(void);
extern void n71_native_driver_unregister(void);
static struct n71_dart_trial_mmio n71_owner_copy;
static bool n71_native_active;
int n71_runtime_owner_ok(void);
int n71_runtime_owner_ok(void)
{
 return n71_native_active && of_machine_is_compatible("apple,n71") &&
  of_machine_is_compatible("apple,s8000") && n71_port_perst_level(&n71_owner_copy)==0 &&
  readl((u8 __iomem *)n71_owner_copy.root+0x1ac)==1 &&
  (readl((u8 __iomem *)n71_owner_copy.root+0x2c)&0x11)==0x11;
}
static int n71_native_pci_action(struct device *,struct gpio_desc *,void __iomem *,void __iomem *,void __iomem *);
static struct n71_dart_trial_mmio *n71_pci_dma_context;
static struct iommu_domain *n71_platform_domain;
static bool n71_allow_pci_dma_api;
static int n71_dma_result;
static unsigned long n71_dma_retained_buffer;
static bool n71_dma_context_ok(struct device *dev)
{
 if(!dev_is_pci(dev))return n71_runtime_owner_ok();
 return n71_allow_pci_dma_api && n71_pci_dma_context &&
  to_pci_dev(dev)->vendor==0x14e4 && to_pci_dev(dev)->device==0x43a3 &&
  n71_config_ready(n71_pci_dma_context) &&
  !(n71_config_read(n71_pci_dma_context,4)&4) && !(n71_endpoint_read(n71_pci_dma_context,4)&4);
}
static int n71_dma_test_device(struct device *dev)
{struct iommu_domain *domain;unsigned long buffer=0;
 dma_addr_t dma=DMA_MAPPING_ERROR;phys_addr_t phys;int rc=-ENODEV;
 domain=iommu_get_domain_for_dev(dev);
 if(!domain||domain->type!=IOMMU_DOMAIN_DMA)goto done;
 if(!n71_dma_context_ok(dev)||dma_set_mask_and_coherent(dev,DMA_BIT_MASK(32)))goto done;
 buffer=__get_free_pages(GFP_KERNEL|__GFP_ZERO,0);if(!buffer){rc=-ENOMEM;goto done;}
 phys=virt_to_phys((void*)buffer);
 dma=dma_map_single(dev,(void*)buffer,PAGE_SIZE,DMA_BIDIRECTIONAL);
 if(dma_mapping_error(dev,dma)){dma=DMA_MAPPING_ERROR;rc=-EIO;goto done;}
 if(dma<0x80000000ULL||dma+PAGE_SIZE>0xbfffc000ULL||
   !n71_dma_context_ok(dev)||iommu_iova_to_phys(domain,dma)!=phys||
   iommu_iova_to_phys(domain,dma+PAGE_SIZE-1)!=phys+PAGE_SIZE-1){rc=-EFAULT;goto done;}
 dma_unmap_single(dev,dma,PAGE_SIZE,DMA_BIDIRECTIONAL);
 if(iommu_iova_to_phys(domain,dma)){n71_dma_retained_buffer=buffer;buffer=0;dma=DMA_MAPPING_ERROR;rc=-EIO;goto done;}
 dma=DMA_MAPPING_ERROR;rc=0;
 pr_info("n71-perst-held: NATIVE_IOMMU_DMA_API_MAP_UNMAP_PASS bytes=%lu identity_domain=0 physical_lookup_matched=1 perst_level=%d no_endpoint_DMA\n",PAGE_SIZE,n71_port_perst_level(&n71_owner_copy));
done:
 if(dma!=DMA_MAPPING_ERROR){
  dma_unmap_single(dev,dma,PAGE_SIZE,DMA_BIDIRECTIONAL);
  if(iommu_iova_to_phys(domain,dma)){n71_dma_retained_buffer=buffer;buffer=0;rc=-EIO;}
 }
 if(buffer)free_pages(buffer,0);
 if(!rc&&!dev_is_pci(dev))n71_platform_domain=domain;
 if(!rc&&dev_is_pci(dev)&&domain!=n71_platform_domain)rc=-EXDEV;
 if(!rc&&dev_is_pci(dev))pr_info("n71-perst-held: REAL_PCI_DMA_API_PASS vendor=14e4 device=43a3 translated_domain_shared=1 BUS_MASTER_OFF no_endpoint_DMA\n");
 n71_dma_result=rc;return rc;
}
static int n71_dma_probe(struct platform_device *pdev){return n71_dma_test_device(&pdev->dev);}
/* Original N71 ADT: MSI offset256 + WLAN vector base8. This only
 * qualifies Linux IRQ allocation; it neither programs nor tests MSI delivery. */
#include <linux/interrupt.h>
#include <linux/irqdomain.h>
static irqreturn_t n71_disabled_irq_handler(int irq,void *data){return IRQ_NONE;}
/* AppleS800xPCIe original implementation: eight vectors ->0x31 at
 * port0x124, base OR(base<<16) at0x128. No endpoint MSI/BME writes. */
static int n71_wlan_msi_register_trial(struct pci_dev *pdev)
{
 void __iomem *port;u32 cfg,base;int rc=0;
 if(!n71_dma_context_ok(&pdev->dev)||!n71_pci_dma_context->port)return -EPERM;
 port=n71_pci_dma_context->port;
 cfg=readl((u8 __iomem *)port+0x124);base=readl((u8 __iomem *)port+0x128);
 /* Do not replace an inherited active MSI route. */
 if(cfg&1)return -EBUSY;
 writel(0x00080008,(u8 __iomem *)port+0x128);
 if(readl((u8 __iomem *)port+0x128)!=0x00080008){rc=-EIO;goto restore;}
 writel(0x31,(u8 __iomem *)port+0x124);
 if(readl((u8 __iomem *)port+0x124)!=0x31||!n71_dma_context_ok(&pdev->dev))rc=-EIO;
restore:
 writel(cfg,(u8 __iomem *)port+0x124);
 writel(base,(u8 __iomem *)port+0x128);
 if(readl((u8 __iomem *)port+0x124)!=cfg||readl((u8 __iomem *)port+0x128)!=base)return -EIO;
 pr_info("n71-perst-held: WLAN_MSI_PORT_REGISTER_TRIAL rc=%d restored=1 eight_vectors=1 BUS_MASTER_OFF no_MSI_delivery_test\n",rc);
 return rc;
}
static int n71_pci_irq_allocation_test(struct pci_dev *pdev)
{
 struct device_node *np;struct irq_domain *domain;struct irq_fwspec spec={};
 unsigned int irq;int rc;
 if(!n71_dma_context_ok(&pdev->dev))return -EPERM;
 np=of_find_node_by_path("/soc/interrupt-controller@20e100000");
 if(!np)return -ENODEV;
 domain=irq_find_host(np);
 if(!domain||irq_find_mapping(domain,(1U<<16)|264)){rc=-EBUSY;goto out;}
 spec.fwnode=of_fwnode_handle(np);spec.param_count=3;
 spec.param[0]=0;spec.param[1]=264;spec.param[2]=IRQ_TYPE_LEVEL_HIGH;
 irq=irq_create_fwspec_mapping(&spec);
 if(!irq){rc=-ENXIO;goto out;}
 rc=request_irq(irq,n71_disabled_irq_handler,IRQF_NO_AUTOEN,"n71-wlan-msi-allocation-only",pdev);
 if(!rc){
  pr_info("n71-perst-held: WLAN_MSI_AIC_ALLOCATION_PASS vector=264 IRQ_DISABLED no_MSI_delivery_test BUS_MASTER_OFF\n");
  rc=n71_wlan_msi_register_trial(pdev);
  free_irq(irq,pdev);
 }
 irq_dispose_mapping(irq);
 if(irq_find_mapping(domain,(1U<<16)|264))rc=-EIO;
 if(!rc)pr_info("n71-perst-held: WLAN_MSI_AIC_ALLOCATION_REMOVED mapping_absent=1\n");
out:
 of_node_put(np);return rc;
}
#ifdef N71_PRIVATE_FIRMWARE_TRIAL
#include <linux/vmalloc.h>
#include <linux/fs.h>
#include "n71-private-firmware.h"
#ifdef N71_PRIVATE_FIRMWARE_BOOT_TRIAL
#ifndef N71_FW_BOOT_POLLS
#define N71_FW_BOOT_POLLS 100
#endif
#ifndef N71_FW_BOOT_POLL_MS
#define N71_FW_BOOT_POLL_MS 50
#endif
#if N71_FW_BOOT_POLLS < 1 || N71_FW_BOOT_POLLS > 100 || N71_FW_BOOT_POLL_MS < 1 || N71_FW_BOOT_POLL_MS > 50
#error Invalid bounded firmware observation interval
#endif
#include "n71-protocol6-rings.h"
/* CR4-only bounded reset sequence from brcmfmac chip.c. BME remains OFF. */
static int n71_cr4_cycle(struct n71_dart_trial_mmio *m,bool halt)
{
 unsigned int i;void __iomem *w=m->bar0;
 writel(0x18102000,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18102000)return -EIO;
 writel(0x23,(u8 __iomem *)w+0x408);readl((u8 __iomem *)w+0x408);
 writel(1,(u8 __iomem *)w+0x800);udelay(20);
 if(readl((u8 __iomem *)w+0x800)!=1)return -EIO;
 writel((halt?0x20:0)|3,(u8 __iomem *)w+0x408);readl((u8 __iomem *)w+0x408);
 for(i=0;i<50;i++){
  writel(0,(u8 __iomem *)w+0x800);usleep_range(40,60);
  if(!(readl((u8 __iomem *)w+0x800)&1))break;
 }
 if(i==50)return -EIO;
 writel((halt?0x20:0)|1,(u8 __iomem *)w+0x408);
 return readl((u8 __iomem *)w+0x408)==((halt?0x20:0)|1)?0:-EIO;
}
static int n71_firmware_boot_trial(struct pci_dev *pdev,void __iomem *ram)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 void __iomem *vec;u32 old,token,shared=0,flags=0,d11io,d11reset;int rc,i,stop;
 vec=ioremap(0x7c0400000ULL,4);if(!vec)return -ENOMEM;
 old=readl(vec);token=readl((u8 __iomem *)ram+0xbfffc);
 /* Match brcmf_chip_cr4_set_passive: D11 PHY reset/clock flags, then
  * leave D11 in reset for firmware to enable. Exact EROM wrapper only. */
 writel(0x18101000,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18101000){iounmap(vec);return -EIO;}
 d11io=readl((u8 __iomem *)m->bar0+0x408);d11reset=readl((u8 __iomem *)m->bar0+0x800);
 if(d11io==0xffffffff||d11reset>1){iounmap(vec);return -EIO;}
 if(!d11reset){
  writel(0xf,(u8 __iomem *)m->bar0+0x408);readl((u8 __iomem *)m->bar0+0x408);
  writel(1,(u8 __iomem *)m->bar0+0x800);udelay(20);
 }
 writel(7,(u8 __iomem *)m->bar0+0x408);readl((u8 __iomem *)m->bar0+0x408);
 if(readl((u8 __iomem *)m->bar0+0x800)!=1){iounmap(vec);return -EHWPOISON;}
 pr_info("n71-perst-held: BRCM_D11_PASSIVE prepared=1 old_ioctl=%08x old_reset=%08x reset_held=1\n",d11io,d11reset);

 writel((u32)n71_fw[0]|((u32)n71_fw[1]<<8)|((u32)n71_fw[2]<<16)|((u32)n71_fw[3]<<24),vec);readl(vec);
 pr_info("n71-perst-held: BRCM_RESET_VECTOR verified=%u\n",readl(vec)==((u32)n71_fw[0]|((u32)n71_fw[1]<<8)|((u32)n71_fw[2]<<16)|((u32)n71_fw[3]<<24)));
 rc=n71_cr4_cycle(m,false);
 if(!rc){
  rc=-ETIMEDOUT;
  for(i=0;i<N71_FW_BOOT_POLLS;i++){
   msleep(N71_FW_BOOT_POLL_MS);shared=readl((u8 __iomem *)ram+0xbfffc);
   if(!n71_dma_context_ok(&pdev->dev)){rc=-EIO;break;}
   if(shared!=token&&shared>=0x180000&&shared<0x23fffc&&!(shared&3)){
    flags=readl((u8 __iomem *)ram+shared-0x180000);rc=0;break;
   }
  }
 }
 writel(0x18102000,(u8 __iomem *)m->endpoint+0x80);
 pr_info("n71-perst-held: BRCM_CR4_AFTER_EXEC ioctl=%08x reset=%08x\n",readl((u8 __iomem *)m->bar0+0x408),readl((u8 __iomem *)m->bar0+0x800));
 if(!rc)rc=n71_protocol6_ring_trial(pdev,ram,shared);
 stop=n71_cr4_cycle(m,true);
 if(!stop){writel(old,vec);readl(vec);}
 if(!stop){
  writel(0x18101000,(u8 __iomem *)m->endpoint+0x80);
  if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18101000)stop=-EIO;
  else{
   writel(d11reset,(u8 __iomem *)m->bar0+0x800);usleep_range(40,60);
   writel(d11io,(u8 __iomem *)m->bar0+0x408);
   if(readl((u8 __iomem *)m->bar0+0x800)!=d11reset||readl((u8 __iomem *)m->bar0+0x408)!=d11io)stop=-EIO;
  }
  writel(0x18002000,(u8 __iomem *)m->endpoint+0x80);
  pr_info("n71-perst-held: BRCM_D11_PASSIVE_RESTORE rc=%d\n",stop);
 }

 pr_info("n71-perst-held: BRCM_FIRMWARE_BOOT_TRIAL rc=%d shared=%08x flags=%08x cpu_rehalted=%u BUS_MASTER_OFF DMA_trial_scope=protocol6\n",rc,shared,flags,!stop);
 iounmap(vec);
 return stop?-EHWPOISON:rc;
}
#endif
static int n71_firmware_write_trial(struct pci_dev *pdev)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 void __iomem *ram;u8 *backup,*check;size_t size=0xc0000;int rc=-EIO;
 bool verified=false,restored=false;
 if(!n71_dma_context_ok(&pdev->dev)||readl((u8 __iomem *)m->endpoint+0x80)!=0x18002000)return -EPERM;
 if(sizeof(n71_fw)+sizeof(n71_nvram)>=size)return -EFBIG;
 backup=vmalloc(size);check=vmalloc(size);
 if(!backup||!check){vfree(backup);vfree(check);return -ENOMEM;}
 ram=ioremap(0x7c0580000ULL,size);
 if(!ram){vfree(backup);vfree(check);return -ENOMEM;}
 memcpy_fromio(backup,ram,size);
 memcpy_toio(ram,n71_fw,sizeof(n71_fw));
 memcpy_toio((u8 __iomem *)ram+size-sizeof(n71_nvram),n71_nvram,sizeof(n71_nvram));
 memcpy_fromio(check,ram,size);
 verified=!memcmp(check,n71_fw,sizeof(n71_fw))&&!memcmp(check+size-sizeof(n71_nvram),n71_nvram,sizeof(n71_nvram));
#ifdef N71_PRIVATE_FIRMWARE_BOOT_TRIAL
 if(verified){
  rc=n71_firmware_boot_trial(pdev,ram);
  if(rc==-EHWPOISON){iounmap(ram);vfree(backup);vfree(check);return rc;}
  {size_t j;unsigned int changes=0;u32 expected;
   for(j=0;j<size;j+=4){memcpy(&expected,check+j,4);if(readl((u8 __iomem *)ram+j)!=expected)changes++;}
   pr_info("n71-perst-held: BRCM_EXEC_RAM_CHANGED_WORDS count=%u total=%zu\n",changes,size/4);
   {struct file *dump;loff_t pos=0;ssize_t written;
    memcpy_fromio(check,ram,size);
    dump=filp_open("/tmp/n71-wlan-fw-ram-private.bin",O_WRONLY|O_CREAT|O_TRUNC,0600);
    if(!IS_ERR(dump)){
     written=kernel_write(dump,check,size,&pos);filp_close(dump,NULL);
     pr_info("n71-perst-held: BRCM_PRIVATE_RAM_CAPTURE bytes=%zd expected=%zu\n",written,size);
    }
   }

  }

 }else rc=-EIO;
#endif
 memcpy_toio(ram,backup,size);
 memcpy_fromio(check,ram,size);restored=!memcmp(check,backup,size);
#ifndef N71_PRIVATE_FIRMWARE_BOOT_TRIAL
 if(verified&&restored&&n71_dma_context_ok(&pdev->dev))rc=0;
#else
 if(!restored||!n71_dma_context_ok(&pdev->dev))rc=-EIO;
#endif
 pr_info("n71-perst-held: BRCM_FIRMWARE_NVRAM_WRITE_VERIFY_RESTORE rc=%d firmware_bytes=%zu nvram_bytes=%zu verified=%u restored=%u CPU_HALTED BUS_MASTER_OFF trial_completed\n",rc,sizeof(n71_fw),sizeof(n71_nvram),verified,restored);
 iounmap(ram);vfree(backup);vfree(check);return rc;
}
#endif
/* Bounded read-only EROM discovery. Never accesses the quarantined OTP. */
static int n71_brcm_erom_inventory(struct pci_dev *pdev)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 u32 saved,a,b,id=0,base=0,wrap=0,wt=0;unsigned int i=0,cores=0;bool end=false,pcie=false,arm=false;int rc=-EIO;
 if(!n71_dma_context_ok(&pdev->dev))return -EPERM;
 saved=readl((u8 __iomem *)m->endpoint+0x80);
 writel(0x1810d000,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=0x1810d000)goto restore;
 while(i<1024){
  a=readl((u8 __iomem *)m->bar0+4*i++);
  if(a==0xffffffff)break;
  if(a==15){end=true;break;}
  if((a&15)==1){
   if(i>=1024||((a>>20)!=0x4bf&&(a>>20)!=0x43b))break;
   b=readl((u8 __iomem *)m->bar0+4*i++);
   if((b&15)!=1)break;
   id=(a>>8)&0xfff;base=wrap=0;wt=((b>>4)&31)?3:2;
   cores++;
   pr_info("n71-perst-held: BRCM_EROM_CORE id=%03x revision=%u master_wrappers=%u slave_wrappers=%u\n",id,b>>24,(b>>14)&31,(b>>19)&31);
  } else if((a&7)==5){
   u32 size=(a>>4)&3,type=(a>>6)&3;
   if(a&8){if(i>=1024)break;i++;}
   if(size==3){
    if(i>=1024)break;
    b=readl((u8 __iomem *)m->bar0+4*i++);
    if(b&8){if(i>=1024)break;i++;}
   }
   if(size>1)continue;
   if(!base&&type==0)base=a&0xfffff000;
   if(!wrap&&type==wt)wrap=a&0xfffff000;
   if(base&&wrap){
    pr_info("n71-perst-held: BRCM_EROM_CORE_MAP id=%03x base=%08x wrapper=%08x\n",id,base,wrap);
    if(id==0x83c)pcie=true;
    if(id==0x83e)arm=true;
   }
  }
 }
 if(end&&cores>0&&cores<64&&pcie&&arm&&n71_dma_context_ok(&pdev->dev))rc=0;
 if(!rc){
  u32 control,reset,cap;
  writel(0x18102000,(u8 __iomem *)m->endpoint+0x80);
  if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18102000){rc=-EIO;goto restore;}
  control=readl((u8 __iomem *)m->bar0+0x408);
  reset=readl((u8 __iomem *)m->bar0+0x800);
  pr_info("n71-perst-held: BRCM_CR4_STATE ioctl=%08x resetctrl=%08x cpu_halt=%u reset_asserted=%u\n",control,reset,!!(control&0x20),!!(reset&1));
  if(!(reset&1)&&control!=0xffffffff){
   writel(0x18002000,(u8 __iomem *)m->endpoint+0x80);
   if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18002000){rc=-EIO;goto restore;}
   cap=readl((u8 __iomem *)m->bar0+4);
   if(cap==0xffffffff){rc=-EIO;goto restore;}
   pr_info("n71-perst-held: BRCM_CR4_CAP cap=%08x tcm_a_banks=%u tcm_b_banks=%u READ_ONLY\n",cap,cap&15,(cap>>4)&15);
   if((control&0x20)&&((cap&15)+((cap>>4)&15))<=16){
    u32 idx,info,total=0,banks=(cap&15)+((cap>>4)&15);
    u32 saved_idx=readl((u8 __iomem *)m->bar0+0x40);
    for(idx=0;idx<banks;idx++){
     writel(idx,(u8 __iomem *)m->bar0+0x40);
     info=readl((u8 __iomem *)m->bar0+0x44);
     if(info==0xffffffff){rc=-EIO;break;}
     total+=((info&0x7f)+1)*((info&0x200)?1024:8192);
    }
    writel(saved_idx,(u8 __iomem *)m->bar0+0x40);
    if(readl((u8 __iomem *)m->bar0+0x40)!=saved_idx)rc=-EIO;
    if(!total||total>0x400000)rc=-EINVAL;
    pr_info("n71-perst-held: BRCM_CR4_RAM_SIZE rc=%d banks=%u bytes=%u index_restored=%u CPU_HALTED no_RAM_write\n",rc,banks,total,readl((u8 __iomem *)m->bar0+0x40)==saved_idx);
    if(!rc&&total==0xc0000&&n71_dma_context_ok(&pdev->dev)){
     void __iomem *tcm=ioremap(0x7c0400000ULL+0x180000+total-16,16);
     u32 old[4],j;bool verified=true,restored=true;
     if(!tcm){rc=-ENOMEM;goto restore;}
     for(j=0;j<4;j++)old[j]=readl((u8 __iomem *)tcm+4*j);
     for(j=0;j<4;j++)writel(0x4e373100U+j,(u8 __iomem *)tcm+4*j);
     for(j=0;j<4;j++)if(readl((u8 __iomem *)tcm+4*j)!=0x4e373100U+j)verified=false;
     for(j=0;j<4;j++)writel(old[j],(u8 __iomem *)tcm+4*j);
     for(j=0;j<4;j++)if(readl((u8 __iomem *)tcm+4*j)!=old[j])restored=false;
     iounmap(tcm);
#ifdef N71_PRIVATE_FIRMWARE_TRIAL
     if(verified&&restored)rc=n71_firmware_write_trial(pdev);
#endif

     if(!verified||!restored)rc=-EIO;
     pr_info("n71-perst-held: BRCM_TCM_WRITE_READ_RESTORE rc=%d bytes=16 verified=%u restored=%u CPU_HALTED BUS_MASTER_OFF trial_completed\n",rc,verified,restored);
    }

   }

  }
 }

restore:
 writel(saved,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=saved)return -EIO;
 pr_info("n71-perst-held: BRCM_EROM_INVENTORY rc=%d cores=%u eot=%u window_restored=1 BUS_MASTER_OFF no_OTP_no_core_reset\n",rc,cores,end);
 return rc;
}
static int n71_pci_dma_probe(struct pci_dev *pdev,const struct pci_device_id *id){int rc=n71_dma_test_device(&pdev->dev);if(!rc)rc=n71_pci_irq_allocation_test(pdev);return rc?rc:n71_brcm_erom_inventory(pdev);}
static const struct pci_device_id n71_pci_dma_ids[]={{PCI_DEVICE(0x14e4,0x43a3)},{}};
static struct pci_driver n71_pci_dma_driver={.name="n71-native-pci-dma-test",.id_table=n71_pci_dma_ids,.probe=n71_pci_dma_probe};
static int n71_native_pci_bind(struct pci_dev *ep)
{
 int rc;
 rc=device_set_driver_override(&ep->dev,"n71-native-pci-dma-test");if(rc)return rc;
 rc=pci_register_driver(&n71_pci_dma_driver);if(rc)return rc;
 n71_dma_result=-EINPROGRESS;n71_allow_pci_dma_api=true;
 pci_bus_add_device(ep);
 rc=n71_dma_result;
 if(!ep->driver||strcmp(ep->driver->name,"n71-native-pci-dma-test"))rc=-ENODEV;
 n71_allow_pci_dma_api=false;pci_unregister_driver(&n71_pci_dma_driver);
 return rc;
}
static struct platform_driver n71_dma_driver={.probe=n71_dma_probe,.driver={.name="n71-native-dma-probe"}};
static struct platform_device *n71_make_device(const char *name,struct device_node *np,struct device *parent,bool provider)
{
 struct platform_device *p;int rc;
 struct resource r={.start=0x602008000ULL,.end=0x60200bfffULL,.flags=IORESOURCE_MEM};
 p=platform_device_alloc(name,PLATFORM_DEVID_NONE);if(!p)return ERR_PTR(-ENOMEM);
 p->dev.parent=parent;device_set_node(&p->dev,of_fwnode_handle(of_node_get(np)));
 p->dev.coherent_dma_mask=DMA_BIT_MASK(32);p->dev.dma_mask=&p->dev.coherent_dma_mask;
 if(provider){rc=platform_device_add_resources(p,&r,1);if(rc)goto fail;}
 rc=platform_device_add(p);if(!rc)return p;
fail:
 platform_device_put(p);return ERR_PTR(rc);
}
static int n71_native_iommu_trial(struct device *parent,void __iomem *ap,void __iomem *root,void __iomem *dart,struct gpio_desc *perst)
{
 struct device_node *node=NULL,*dn=NULL,*cn=NULL;struct platform_device *provider=NULL,*consumer=NULL;
 unsigned int saved[16],i,fault,command;int id=0,rc=-EINVAL,err;
 bool provider_driver=false,consumer_driver=false,overlay=false,restored=true;
 if(n71_native_active)return -EBUSY;
 n71_owner_copy=(struct n71_dart_trial_mmio){.ap=ap,.root=root,.dart=dart};n71_native_active=true;
 if(!n71_runtime_owner_ok()||readl((u8 __iomem *)dart+0xc))goto done;
 node=of_find_node_by_path("/soc/n71-native-iommu-lease");if(node){of_node_put(node);goto done;}
 command=readl(dart);fault=readl((u8 __iomem *)dart+0x10);
 if((command&8)||(fault&BIT(31)))goto done;
 for(i=0;i<16;i++)saved[i]=readl((u8 __iomem *)dart+0x40+4*i);
 rc=of_overlay_fdt_apply(n71_native_dtbo,sizeof(n71_native_dtbo),&id,NULL);if(rc)goto done;
 overlay=true;
 dn=of_find_node_by_path("/soc/n71-native-iommu-lease/dart@602008000");
 cn=of_find_node_by_path("/soc/n71-native-iommu-lease/dma-probe");
 if(!dn||!cn){rc=-ENODEV;goto cleanup;}
 rc=n71_native_driver_register();if(rc)goto cleanup;provider_driver=true;
 provider=n71_make_device("n71-native-dart-provider",dn,parent,true);
 if(IS_ERR(provider)){rc=PTR_ERR(provider);provider=NULL;goto cleanup;}
 if(!provider->dev.driver||!platform_get_drvdata(provider)){rc=-ENODEV;goto cleanup;}
 n71_dma_result=-EINPROGRESS;
 rc=platform_driver_register(&n71_dma_driver);if(rc)goto cleanup;consumer_driver=true;
 consumer=n71_make_device("n71-native-dma-probe",cn,parent,false);
 if(IS_ERR(consumer)){rc=PTR_ERR(consumer);consumer=NULL;goto cleanup;}
 rc=n71_dma_result;
 if(!rc&&stage==29)rc=n71_native_pci_action(parent,perst,ap,root,dart);
cleanup:
 /* Disable only SID0 BEFORE device/domain teardown frees any table pages. */
 if(!n71_runtime_owner_ok()||(readl((u8 __iomem *)dart+0xc)&0xffffff00U))return -EHWPOISON;
 writel(0,(u8 __iomem *)dart+0xc);
 if(readl((u8 __iomem *)dart+0xc))return -EHWPOISON;
 if(consumer)platform_device_unregister(consumer);
 if(consumer_driver)platform_driver_unregister(&n71_dma_driver);
 if(provider)platform_device_unregister(provider);
 if(provider_driver)n71_native_driver_unregister();
 if(n71_dma_retained_buffer){free_pages(n71_dma_retained_buffer,0);n71_dma_retained_buffer=0;}
 if(readl((u8 __iomem *)dart+0xc))return -EHWPOISON;
 for(i=0;i<4;i++)writel(saved[i],(u8 __iomem *)dart+0x40+4*i);
 for(i=0;i<16;i++)if(readl((u8 __iomem *)dart+0x40+4*i)!=saved[i])restored=false;
 if(readl((u8 __iomem *)dart+0x10)!=fault||((readl(dart)^command)&~0xf00U))restored=false;
 if(!restored)rc=-EIO;
 of_node_put(cn);of_node_put(dn);
 if(overlay){err=of_overlay_remove(&id);if(err)rc=err;}
 pr_info("n71-perst-held: NATIVE_IOMMU_TRIAL rc=%d restored=%u stream0_only=1 PERST_LOW DMA_trial_scope=diagnostic\n",rc,restored);
done:
 n71_native_active=false;return rc;
}
