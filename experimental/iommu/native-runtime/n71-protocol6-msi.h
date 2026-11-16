/* SPDX-License-Identifier: GPL-2.0-only */
/* One-shot WLAN-only MSI: original vector264, upstream Apple port registers.
 * No other port/SID is enabled. Mailbox mask is disabled on the first IRQ.
 * The original global message data is8 (data0 yielded no interrupt).
 * S8000 port+0x168 reads zero: never write the newer-SoC MSI-address register. */
#include <linux/atomic.h>
struct n71_control_msi {
 struct n71_dart_trial_mmio *m;struct pci_dev *pdev;bool generic;
 unsigned int irq;int cap;
 u16 control,data;u32 lo,hi,cfg,base,address,mask;
 bool requested,enabled,changed;
 atomic_t count,status,bad;
};
static irqreturn_t n71_control_msi_irq(int irq,void *data)
{
 struct n71_control_msi *s=data;u32 status=readl((u8 __iomem *)s->m->bar0+0x48);
 writel(0,(u8 __iomem *)s->m->bar0+0x4c);
 if(status!=0xffffffff&&(status&0xff0000)){
  writel(status&0xff0000,(u8 __iomem *)s->m->bar0+0x48);
  atomic_or(status&0xff0000,&s->status);atomic_inc(&s->count);
 }else atomic_inc(&s->bad);
 return IRQ_HANDLED;
}
static int n71_control_msi_stop(struct n71_control_msi *s,bool require_irq)
{
 struct n71_dart_trial_mmio *m=s->m;int rc=0;
 if(s->changed){
  writel(0,(u8 __iomem *)m->bar0+0x4c);
  writew(s->control,(u8 __iomem *)m->endpoint+s->cap+2);
 }
 if(s->enabled){disable_irq(s->irq);s->enabled=false;}
 if(s->requested){free_irq(s->irq,s);s->requested=false;}
 if(s->generic){pci_disable_msi(s->pdev);s->generic=false;}
 else if(s->irq)irq_dispose_mapping(s->irq);
 s->irq=0;
 if(s->changed){
  writel(s->cfg,(u8 __iomem *)m->port+0x124);
  writel(s->base,(u8 __iomem *)m->port+0x128);
  writel(s->lo,(u8 __iomem *)m->endpoint+s->cap+4);
  writel(s->hi,(u8 __iomem *)m->endpoint+s->cap+8);
  writew(s->data,(u8 __iomem *)m->endpoint+s->cap+12);
  writel(s->mask,(u8 __iomem *)m->bar0+0x4c);
  if(readl((u8 __iomem *)m->port+0x124)!=s->cfg||readl((u8 __iomem *)m->port+0x128)!=s->base||readl((u8 __iomem *)m->port+0x168)!=s->address||readw((u8 __iomem *)m->endpoint+s->cap+2)!=s->control||readl((u8 __iomem *)m->endpoint+s->cap+4)!=s->lo||readl((u8 __iomem *)m->endpoint+s->cap+8)!=s->hi||readw((u8 __iomem *)m->endpoint+s->cap+12)!=s->data||readl((u8 __iomem *)m->bar0+0x4c)!=s->mask)rc=-EHWPOISON;
 }
 if(!rc&&require_irq&&(!atomic_read(&s->count)||atomic_read(&s->bad)))rc=-ETIMEDOUT;
 pr_info("n71-perst-held: BRCM_DMA_MSI_DELIVERY rc=%d required=%u vector=264 count=%d status=%08x unexpected=%d restored=%u IRQ_REMOVED\n",rc,require_irq,atomic_read(&s->count),atomic_read(&s->status),atomic_read(&s->bad),rc!=-EHWPOISON);
 return rc;
}
static int n71_control_msi_start(struct pci_dev *pdev,struct n71_control_msi *s)
{
 struct device_node *np=NULL;int rc=-EPERM;
#ifndef N71_NATIVE_MSI_DOMAIN
 struct irq_domain *domain;struct irq_fwspec spec={};
#endif
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 if(!n71_dma_context_ok(&pdev->dev)||!m->port)return -EPERM;
 s->m=m;atomic_set(&s->count,0);atomic_set(&s->status,0);atomic_set(&s->bad,0);
 s->cap=pci_find_capability(pdev,PCI_CAP_ID_MSI);
 if(s->cap<0x40||s->cap>0xe8)return -EOPNOTSUPP;
 s->control=readw((u8 __iomem *)m->endpoint+s->cap+2);
 if(!(s->control&PCI_MSI_FLAGS_64BIT)||(s->control&(PCI_MSI_FLAGS_ENABLE|PCI_MSI_FLAGS_MASKBIT)))return -EBUSY;
 s->cfg=readl((u8 __iomem *)m->port+0x124);s->base=readl((u8 __iomem *)m->port+0x128);s->address=readl((u8 __iomem *)m->port+0x168);
 s->mask=readl((u8 __iomem *)m->bar0+0x4c);
 if((s->cfg&1)||s->mask)return -EBUSY;
 s->lo=readl((u8 __iomem *)m->endpoint+s->cap+4);s->hi=readl((u8 __iomem *)m->endpoint+s->cap+8);s->data=readw((u8 __iomem *)m->endpoint+s->cap+12);
#ifdef N71_NATIVE_MSI_DOMAIN
 s->pdev=pdev;rc=pci_enable_msi(pdev);if(rc)return rc;
 s->generic=true;s->irq=pdev->irq;
#else
 np=of_find_node_by_path("/soc/interrupt-controller@20e100000");if(!np)return -ENODEV;
 domain=irq_find_host(np);
 if(!domain||irq_find_mapping(domain,(1U<<16)|264)){rc=-EBUSY;goto put;}
 spec.fwnode=of_fwnode_handle(np);spec.param_count=3;spec.param[0]=0;spec.param[1]=264;spec.param[2]=IRQ_TYPE_LEVEL_HIGH;
 s->irq=irq_create_fwspec_mapping(&spec);if(!s->irq){rc=-ENXIO;goto put;}
#endif
 rc=request_irq(s->irq,n71_control_msi_irq,IRQF_NO_AUTOEN,"n71-wlan-control-one-shot",s);
 if(rc)goto put;
 s->requested=true;s->changed=true;
 writel(0x00080008,(u8 __iomem *)m->port+0x128);writel(0x31,(u8 __iomem *)m->port+0x124);
 pr_info("n71-perst-held: BRCM_DMA_MSI_ROUTE cfg=%08x base=%08x fixed_address_register=%08x\n",readl((u8 __iomem *)m->port+0x124),readl((u8 __iomem *)m->port+0x128),readl((u8 __iomem *)m->port+0x168));
 if(readl((u8 __iomem *)m->port+0x128)!=0x00080008||readl((u8 __iomem *)m->port+0x124)!=0x31){rc=-EIO;goto put;}
#ifndef N71_NATIVE_MSI_DOMAIN
 writel(0xbffff000,(u8 __iomem *)m->endpoint+s->cap+4);writel(0,(u8 __iomem *)m->endpoint+s->cap+8);writew(8,(u8 __iomem *)m->endpoint+s->cap+12);
 writew((s->control&~0x71)|PCI_MSI_FLAGS_ENABLE,(u8 __iomem *)m->endpoint+s->cap+2);
#endif
 pr_info("n71-perst-held: BRCM_DMA_MSI_ENDPOINT cap=%x control=%04x addrlo=%08x addrhi=%08x data=%04x\n",s->cap,readw((u8 __iomem *)m->endpoint+s->cap+2),readl((u8 __iomem *)m->endpoint+s->cap+4),readl((u8 __iomem *)m->endpoint+s->cap+8),readw((u8 __iomem *)m->endpoint+s->cap+12));
 if(readl((u8 __iomem *)m->endpoint+s->cap+4)!=0xbffff000||readl((u8 __iomem *)m->endpoint+s->cap+8)||readw((u8 __iomem *)m->endpoint+s->cap+12)!=8||readw((u8 __iomem *)m->endpoint+s->cap+2)!=((s->control&~0x71)|1)){rc=-EIO;goto put;}
 writel(readl((u8 __iomem *)m->bar0+0x48)&0xff0000,(u8 __iomem *)m->bar0+0x48);
 enable_irq(s->irq);s->enabled=true;writel(0xff0000,(u8 __iomem *)m->bar0+0x4c);rc=0;
put:
 of_node_put(np);
 if(rc){int stopped=n71_control_msi_stop(s,false);if(stopped)rc=stopped;}
 return rc;
}
