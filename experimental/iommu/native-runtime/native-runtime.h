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
static int n71_pci_dma_probe(struct pci_dev *pdev,const struct pci_device_id *id){int rc=n71_dma_test_device(&pdev->dev);return rc?rc:n71_pci_irq_allocation_test(pdev);}
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
 pr_info("n71-perst-held: NATIVE_IOMMU_TRIAL rc=%d restored=%u stream0_only=1 PERST_LOW no_endpoint_DMA\n",rc,restored);
done:
 n71_native_active=false;return rc;
}
