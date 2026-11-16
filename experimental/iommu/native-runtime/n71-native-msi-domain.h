/* SPDX-License-Identifier: GPL-2.0-only */
/* Scoped adaptation of Linux pcie-apple.c MSI hierarchy: WLAN vectors8..15
 * only, corresponding to AIC264..271. Parent remains the live Apple AIC. */
#include <linux/msi.h>
#include <linux/irqchip/irq-msi-lib.h>
#include <linux/bitmap.h>
static struct {
 struct irq_domain *domain;struct fwnode_handle *fwnode;
 struct device_node *aic;unsigned long bitmap;bool active;
} n71_msi_scope;
static void n71_msi_compose(struct irq_data *d,struct msi_msg *msg)
{msg->address_hi=0;msg->address_lo=0xbffff000;msg->data=8+d->hwirq;}
static struct irq_chip n71_msi_chip={.name="N71-WLAN-MSI",
 .irq_mask=irq_chip_mask_parent,.irq_unmask=irq_chip_unmask_parent,
 .irq_eoi=irq_chip_eoi_parent,.irq_set_affinity=irq_chip_set_affinity_parent,
 .irq_set_type=irq_chip_set_type_parent,.irq_compose_msi_msg=n71_msi_compose};
static int n71_msi_alloc(struct irq_domain *domain,unsigned int virq,unsigned int nr,void *args)
{
 struct irq_fwspec spec={};int bit,rc;unsigned int i;
 if(!n71_msi_scope.active||!nr||nr>8)return -EPERM;
 bit=bitmap_find_free_region(&n71_msi_scope.bitmap,8,order_base_2(nr));if(bit<0)return bit;
 spec.fwnode=of_fwnode_handle(n71_msi_scope.aic);spec.param_count=3;
 spec.param[0]=0;spec.param[1]=264+bit;spec.param[2]=IRQ_TYPE_LEVEL_HIGH;
 rc=irq_domain_alloc_irqs_parent(domain,virq,nr,&spec);
 if(rc){bitmap_release_region(&n71_msi_scope.bitmap,bit,order_base_2(nr));return rc;}
 for(i=0;i<nr;i++)irq_domain_set_hwirq_and_chip(domain,virq+i,bit+i,&n71_msi_chip,NULL);
 pr_info("n71-perst-held: NATIVE_MSI_ALLOC count=%u message_data=%d AIC_vector=%d\n",nr,8+bit,264+bit);
 return 0;
}
static void n71_msi_free(struct irq_domain *domain,unsigned int virq,unsigned int nr)
{
 struct irq_data *d=irq_domain_get_irq_data(domain,virq);
 bitmap_release_region(&n71_msi_scope.bitmap,d->hwirq,order_base_2(nr));
}
static const struct irq_domain_ops n71_msi_ops={.alloc=n71_msi_alloc,.free=n71_msi_free};
static const struct msi_parent_ops n71_msi_parent_ops={
 .supported_flags=MSI_GENERIC_FLAGS_MASK|MSI_FLAG_MULTI_PCI_MSI,
 .required_flags=MSI_FLAG_USE_DEF_DOM_OPS|MSI_FLAG_USE_DEF_CHIP_OPS|MSI_FLAG_PCI_MSI_MASK_PARENT,
 .chip_flags=MSI_CHIP_FLAG_SET_EOI,.bus_select_token=DOMAIN_BUS_PCI_MSI,
 .init_dev_msi_info=msi_lib_init_dev_msi_info};
static int n71_native_msi_domain_start(struct pci_dev *ep)
{
 struct irq_domain_info info={.ops=&n71_msi_ops,.size=8};unsigned int i;
 if(n71_msi_scope.active||ep->vendor!=0x14e4||ep->device!=0x43a3||ep->msi_enabled||dev_get_msi_domain(&ep->dev))return -EBUSY;
 n71_msi_scope.aic=of_find_node_by_path("/soc/interrupt-controller@20e100000");
 if(!n71_msi_scope.aic)return -ENODEV;
 info.parent=irq_find_host(n71_msi_scope.aic);
 if(!info.parent)goto fail;
 for(i=264;i<272;i++)if(irq_find_mapping(info.parent,(1U<<16)|i))goto fail;
 n71_msi_scope.fwnode=irq_domain_alloc_named_fwnode("n71-wlan-only-msi");
 if(!n71_msi_scope.fwnode)goto fail;
 info.fwnode=n71_msi_scope.fwnode;
 n71_msi_scope.domain=msi_create_parent_irq_domain(&info,&n71_msi_parent_ops);
 if(!n71_msi_scope.domain)goto fail;
 n71_msi_scope.bitmap=0;n71_msi_scope.active=true;
 dev_set_msi_domain(&ep->dev,n71_msi_scope.domain);
 pr_info("n71-perst-held: NATIVE_MSI_DOMAIN_READY vectors=8 AIC_first=264 message_first=8\n");
 return 0;
fail:
 if(n71_msi_scope.fwnode)irq_domain_free_fwnode(n71_msi_scope.fwnode);
 of_node_put(n71_msi_scope.aic);memset(&n71_msi_scope,0,sizeof(n71_msi_scope));return -EBUSY;
}
static int n71_native_msi_domain_cleanup(void)
{
 if(!n71_msi_scope.active)return 0;
 if(n71_msi_scope.bitmap)return -EHWPOISON;
 irq_domain_remove(n71_msi_scope.domain);irq_domain_free_fwnode(n71_msi_scope.fwnode);
 of_node_put(n71_msi_scope.aic);memset(&n71_msi_scope,0,sizeof(n71_msi_scope));
 pr_info("n71-perst-held: NATIVE_MSI_DOMAIN_REMOVED allocations_remaining=0\n");return 0;
}
static bool n71_native_msi_cfg_allowed(unsigned int target,unsigned int off,unsigned int size,u32 value)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 if(!n71_msi_scope.active||target!=1||!m||!n71_config_ready(m))return false;
 if(off==4&&size==2)return value==2||value==0x402;
 if(off==0x5a&&size==2)return !((value^readw((u8 __iomem *)m->endpoint+off))&~0x71)&&!(value&0x70);
 if(off==0x5c&&size==4)return value==0xbffff000;
 if(off==0x60&&size==4)return value==0;
 if(off==0x64&&size==2)return value>=8&&value<16;
 return false;
}
