/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PCI_CORE_ENUMERATE_H
#define N71_PCI_CORE_ENUMERATE_H
#include <drivers/pci/pci.h>
#include "n71-pci-config-policy.h"
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
 if(!n71_cfg_write_allowed(target,where,size,value,readw((u8 __iomem *)base+4))) {
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
 n71_pci_reads=n71_pci_writes=n71_pci_denied=0;
 if(!n71_config_ready(ctx))return -EIO;
 pci_lock_rescan_remove();
 if(pci_find_bus(0,0)){rc=-EBUSY;goto out;}
 pci_add_resource_offset(&resources,&mem,0x700000000ULL);
 pci_add_resource(&resources,&buses);
 root=pci_create_root_bus(NULL,0,&n71_pci_core_ops,ctx,&resources);
 if(!root)goto out;
 rp=pci_scan_single_device(root,PCI_DEVFN(1,0));
 if(!rp||rp->vendor!=0x106b||rp->device!=0x1004||rp->driver||!pci_dev_binding_disallowed(rp))goto remove;
 child=pci_add_new_bus(root,rp,1);if(!child)goto remove;
 ep=pci_scan_single_device(child,PCI_DEVFN(0,0));
 if(!ep||ep->vendor!=0x14e4||ep->device!=0x43a3||ep->driver||!pci_dev_binding_disallowed(ep))goto remove;
 if(pci_resource_start(ep,0)!=0x7c0000000ULL||pci_resource_len(ep,0)!=0x8000||
    pci_resource_start(ep,2)!=0x7c0400000ULL||pci_resource_len(ep,2)!=0x400000)goto remove;
 if((n71_config_read(ctx,4)&4)||(n71_endpoint_read(ctx,4)&4))goto remove;
 rc=0;
 pr_info("n71-perst-held: PCI_CORE_ENDPOINT_FOUND vendor=%04x device=%04x class=%06x revision=%02x BAR0_BYTES=%llx BAR2_BYTES=%llx binding_disallowed=1 driver_bound=0 BUS_MASTER_OFF\n",
 ep->vendor,ep->device,ep->class,ep->revision,(unsigned long long)pci_resource_len(ep,0),(unsigned long long)pci_resource_len(ep,2));
remove:
 pci_stop_root_bus(root);pci_remove_root_bus(root);
 pr_info("n71-perst-held: PCI_CORE_REMOVED rc=%d reads=%u writes=%u denied=%u before_reset_and_DART_teardown=1\n",rc,n71_pci_reads,n71_pci_writes,n71_pci_denied);
out:
 pci_free_resource_list(&resources);pci_unlock_rescan_remove();return rc;
}
#endif
