/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PCI_CORE_ENUMERATE_H
#define N71_PCI_CORE_ENUMERATE_H
#include <drivers/pci/pci.h>
#include "n71-pci-config-policy.h"
#ifdef N71_NATIVE_IOMMU_RUNTIME
static struct device *n71_native_pci_parent;
static int n71_native_pci_bind(struct pci_dev *);
#endif
#ifdef N71_NATIVE_MSI_DOMAIN
static bool n71_native_msi_cfg_allowed(unsigned int,unsigned int,unsigned int,u32);
static int n71_native_msi_domain_cleanup(void);
#endif
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
static bool n71_native_brcmf_cfg_allowed(unsigned int,unsigned int,unsigned int,u32);
#endif
static unsigned int n71_pci_reads,n71_pci_writes,n71_pci_denied;
static int n71_pci_config_read(struct pci_bus *bus,unsigned int devfn,int where,int size,u32 *value)
{
 struct n71_dart_trial_mmio *m=bus->sysdata;
 int target=n71_cfg_target(bus->number,devfn,where,size);
 void __iomem *p;
 *value=~0U;
 if(target<0||!n71_config_ready(m))return PCIBIOS_DEVICE_NOT_FOUND;
 p=(u8 __iomem *)(target?m->endpoint:m->cfg)+where;
 *value=size==1?readb(p):size==2?readw(p):readl(p);n71_pci_reads++;
 return PCIBIOS_SUCCESSFUL;
}
static int n71_pci_config_write(struct pci_bus *bus,unsigned int devfn,int where,int size,u32 value)
{
 struct n71_dart_trial_mmio *m=bus->sysdata;
 int target=n71_cfg_target(bus->number,devfn,where,size);
 void __iomem *base;
 if(target<0||!n71_config_ready(m))return PCIBIOS_DEVICE_NOT_FOUND;
 base=target?m->endpoint:m->cfg;
 if(!n71_cfg_write_allowed(target,where,size,value,readw((u8 __iomem *)base+4))
#ifdef N71_NATIVE_MSI_DOMAIN
 && !n71_native_msi_cfg_allowed(target,where,size,value)
#endif
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
 && !n71_native_brcmf_cfg_allowed(target,where,size,value)
#endif
 ) {
  n71_pci_denied++;pr_info("n71-perst-held: PCI_CORE_WRITE_DENIED target=%d off=%x size=%d value=%08x\n",target,where,size,value);
  return PCIBIOS_SET_FAILED;
 }
 if(size==2)writew(value,(u8 __iomem *)base+where);else writel(value,(u8 __iomem *)base+where);
 n71_pci_writes++;return PCIBIOS_SUCCESSFUL;
}
static struct pci_ops n71_pci_core_ops={.read=n71_pci_config_read,.write=n71_pci_config_write};
/* No pci_bus_add_devices: matching remains disabled throughout this lease.
 * Kernel PCI bus/device objects are removed BEFORE MMIO/DART/reset teardown.
 */
static int n71_pci_core_enumerate(void *ctx)
{
 LIST_HEAD(resources);
 struct resource mem={.name="n71-wlan-only",.start=0x7c0000000ULL,.end=0x7c07fffffULL,.flags=IORESOURCE_MEM};
 struct resource buses={.name="n71-wlan-buses",.start=0,.end=1,.flags=IORESOURCE_BUS};
 struct pci_bus *root=NULL,*child;
 struct pci_dev *rp,*ep;
 int rc=-ENODEV;
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
 bool aperture_claimed=false;struct resource *aperture=NULL;
#endif
 n71_pci_reads=n71_pci_writes=n71_pci_denied=0;
 if(!n71_config_ready(ctx))return -EIO;
 pci_lock_rescan_remove();
 if(pci_find_bus(0,0)){rc=-EBUSY;goto out;}
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
 aperture=kmemdup(&mem,sizeof(mem),GFP_KERNEL);if(!aperture){rc=-ENOMEM;goto out;}
 if(request_resource(&iomem_resource,aperture)){rc=-EBUSY;goto out;}
 aperture_claimed=true;
 pci_add_resource_offset(&resources,aperture,0x700000000ULL);
#else
 pci_add_resource_offset(&resources,&mem,0x700000000ULL);
#endif
 pci_add_resource(&resources,&buses);
#ifdef N71_NATIVE_IOMMU_RUNTIME
 root=pci_create_root_bus(stage==29?n71_native_pci_parent:NULL,0,
#else
 root=pci_create_root_bus(NULL,0,
#endif
&n71_pci_core_ops,ctx,&resources);
 if(!root)goto out;
 rp=pci_scan_single_device(root,PCI_DEVFN(1,0));
 if(!rp||rp->vendor!=0x106b||rp->device!=0x1004||rp->driver||!pci_dev_binding_disallowed(rp))goto remove;
 child=pci_add_new_bus(root,rp,1);if(!child)goto remove;
 ep=pci_scan_single_device(child,PCI_DEVFN(0,0));
 if(!ep||ep->vendor!=0x14e4||ep->device!=0x43a3||ep->driver||!pci_dev_binding_disallowed(ep))goto remove;
 if(pci_resource_start(ep,0)!=0x7c0000000ULL||pci_resource_len(ep,0)!=0x8000||
    pci_resource_start(ep,2)!=0x7c0400000ULL||pci_resource_len(ep,2)!=0x400000)goto remove;
 if((n71_config_read(ctx,4)&4)||(n71_endpoint_read(ctx,4)&4))goto remove;
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
 /* Fixed root bridge aperture is already programmed by the port1 lease. */
 child->resource[1]=aperture; /* Fixed MEM window of this private child bus. */
 rc=pci_claim_resource(ep,0);if(rc)goto remove;
 rc=pci_claim_resource(ep,2);if(rc)goto remove;
 pr_info("n71-perst-held: NATIVE_PCI_BAR_CLAIM_PASS BAR0_parent=1 BAR2_parent=1 fixed_WLAN_aperture_only=1\n");
#endif
 rc=0;
 pr_info("n71-perst-held: PCI_CORE_ENDPOINT_FOUND vendor=%04x device=%04x class=%06x revision=%02x BAR0_BYTES=%llx BAR2_BYTES=%llx binding_disallowed=1 driver_bound=0 BUS_MASTER_OFF\n",
 ep->vendor,ep->device,ep->class,ep->revision,(unsigned long long)pci_resource_len(ep,0),(unsigned long long)pci_resource_len(ep,2));
#ifdef N71_NATIVE_IOMMU_RUNTIME
 if(stage==29)rc=n71_native_pci_bind(ep);
#endif
remove:
 pci_stop_root_bus(root);pci_remove_root_bus(root);
#ifdef N71_NATIVE_MSI_DOMAIN
 if(n71_native_msi_domain_cleanup())rc=-EHWPOISON;
#endif
 pr_info("n71-perst-held: PCI_CORE_REMOVED rc=%d reads=%u writes=%u denied=%u before_reset_and_DART_teardown=1\n",rc,n71_pci_reads,n71_pci_writes,n71_pci_denied);
out:
 pci_free_resource_list(&resources);
#ifdef N71_NATIVE_BRCMFMAC_TRIAL
 if(aperture_claimed&&aperture->child){
  __module_get(THIS_MODULE);rc=-EHWPOISON;
  pr_err("n71-perst-held: PCI_APERTURE_RETAINED children_still_present module_pinned\n");
 }else{if(aperture_claimed)release_resource(aperture);kfree(aperture);}
#endif
 pci_unlock_rescan_remove();return rc;
}
#endif
