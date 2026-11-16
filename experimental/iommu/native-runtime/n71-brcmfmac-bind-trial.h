/* SPDX-License-Identifier: GPL-2.0-only */
/* Real built-in brcmfmac binding. Original firmware stays owner-only.
 * Do not tear down PCI/IOMMU while asynchronous firmware setup is pending. */
#include <linux/netdevice.h>
#include <linux/rtnetlink.h>
#ifndef N71_BRCMFMAC_LIVE_SECONDS
#define N71_BRCMFMAC_LIVE_SECONDS 0
#endif
#if N71_BRCMFMAC_LIVE_SECONDS < 0 || N71_BRCMFMAC_LIVE_SECONDS > 120
#error "Live WLAN trial must remain within0..120seconds"
#endif
static bool n71_brcmf_trial_active;
static u32 n71_brcmf_saved_cfg[1024];
static bool n71_native_brcmf_cfg_allowed(unsigned int target,unsigned int off,unsigned int size,u32 value)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 if(target>1||!n71_brcmf_trial_active||!m||!n71_config_ready(m))return false;
 if(off==4&&size==2)return value==2||value==6||value==0x402||value==0x406;
 if(target!=1)return false;
 if(off==0x80&&size==4)return !value||(!(value&0xfff)&&value>=0x18000000&&value<=0x181ff000);
 if(off==0x4c&&size==2)return (value&3)==0&&(value&~3)==(n71_brcmf_saved_cfg[off/4]&0xffff&~3);
 if(off==0xbc&&size==2)return value==(n71_brcmf_saved_cfg[off/4]&0xffff&~3);
 if(size!=4)return false;
 switch(off){
 case 0x4c:case 0x58:case 0x5c:case 0x60:case 0x64:
 case 0xdc:case 0x228:case 0x248:case 0x4e0:case 0x4f4:
  return value==n71_brcmf_saved_cfg[off/4];
 default:return false;
 }
}
static int n71_native_brcmf_bind_trial(struct pci_dev *ep)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 struct net_device *nd;unsigned int i,found=0;int rc;
 u32 portcfg,portbase,rootcmd;struct iommu_domain *domain;
#ifdef N71_NATIVE_WLAN_RUNTIME
 bool runtime_ref=false;
#endif
 domain=iommu_get_domain_for_dev(&ep->dev);
 if(!n71_dma_context_ok(&ep->dev)||domain!=n71_platform_domain||ep->driver)return -EPERM;
 rootcmd=readw((u8 __iomem *)m->cfg+4);
 if(rootcmd!=2||readw((u8 __iomem *)m->endpoint+4)!=2)return -EBUSY;
 portcfg=readl((u8 __iomem *)m->port+0x124);portbase=readl((u8 __iomem *)m->port+0x128);
 if(portcfg&1)return -EBUSY;
 for(i=0;i<1024;i++)n71_brcmf_saved_cfg[i]=readl((u8 __iomem *)m->endpoint+4*i);
 rc=device_set_driver_override(&ep->dev,"brcmfmac");if(rc)return rc;
 writel(0x00080008,(u8 __iomem *)m->port+0x128);writel(0x31,(u8 __iomem *)m->port+0x124);
 if(readl((u8 __iomem *)m->port+0x128)!=0x00080008||readl((u8 __iomem *)m->port+0x124)!=0x31){rc=-EIO;goto restore;}
 n71_brcmf_trial_active=true;writew(6,(u8 __iomem *)m->cfg+4);
 rc=device_attach(&ep->dev);
 pr_info("n71-perst-held: BRCMFMAC_NATIVE_BIND attach_rc=%d driver_bound=%u translated_domain=1\n",rc,ep->driver&&!strcmp(ep->driver->name,"brcmfmac"));
 if(rc>0){
  /* Firmware is pre-staged in RAM. Allow asynchronous setup to settle. */
  for(i=0;;i++){
   if(i==600)pr_warn("n71-perst-held: BRCMFMAC_FW_SETUP_PENDING retaining hardware lease until driver settles\n");
   msleep(100);found=0;rtnl_lock();
   for_each_netdev(&init_net,nd)if(nd->dev.parent==&ep->dev&&nd->ieee80211_ptr)found++;
   rtnl_unlock();
   if(found){msleep(500);break;}
   if(!ep->driver&&!dev_get_drvdata(&ep->dev))break;
  }
  pr_info("n71-perst-held: BRCMFMAC_NATIVE_WLAN devices=%u elapsed_ms=%u driver_bound=%u fault=%08x\n",found,(i+1)*100,!!ep->driver,readl((u8 __iomem *)m->dart+0x10));
  rc=found?0:-ENODEV;
#ifdef N71_NATIVE_WLAN_RUNTIME
  if(found){
   /* The worker owns all live stack contexts until kthread_stop finishes. */
   pci_dev_get(ep);runtime_ref=true;WRITE_ONCE(n71_runtime_state,2);WRITE_ONCE(n71_runtime_result,0);
   pr_info("n71-perst-held: BRCMFMAC_MANAGED_RUNTIME_READY stop_via_module_remove=1\n");
   pci_unlock_rescan_remove();
   while(!kthread_should_stop()){
    msleep(250);
    if(!device_is_registered(&ep->dev)||!READ_ONCE(ep->driver)){rc=-ENODEV;break;}
    if(readl((u8 __iomem *)m->dart+0x10)&BIT(31)){writew(2,(u8 __iomem *)m->endpoint+4);rc=-EFAULT;break;}
   }
   pci_lock_rescan_remove();WRITE_ONCE(n71_runtime_state,3);
  }
#else
  if(found&&N71_BRCMFMAC_LIVE_SECONDS){
   pr_info("n71-perst-held: BRCMFMAC_LIVE_WLAN_READY seconds=%u\n",N71_BRCMFMAC_LIVE_SECONDS);
   for(i=0;i<N71_BRCMFMAC_LIVE_SECONDS;i++){
    msleep(1000);if(readl((u8 __iomem *)m->dart+0x10)&BIT(31)){writew(2,(u8 __iomem *)m->endpoint+4);rc=-EFAULT;break;}
   }
  }
#endif
  device_release_driver(&ep->dev);

 }else rc=rc?rc:-ENODEV;
 n71_brcmf_trial_active=false;
restore:
 writew(2,(u8 __iomem *)m->endpoint+4);writew(rootcmd,(u8 __iomem *)m->cfg+4);
 if(!pci_wait_for_pending_transaction(ep)){rc=-EHWPOISON;goto out_ref;}
 writel(portcfg,(u8 __iomem *)m->port+0x124);writel(portbase,(u8 __iomem *)m->port+0x128);
 writel(n71_brcmf_saved_cfg[0x80/4],(u8 __iomem *)m->endpoint+0x80);
 writel(n71_brcmf_saved_cfg[0x5c/4],(u8 __iomem *)m->endpoint+0x5c);
 writel(n71_brcmf_saved_cfg[0x60/4],(u8 __iomem *)m->endpoint+0x60);
 writew(n71_brcmf_saved_cfg[0x64/4],(u8 __iomem *)m->endpoint+0x64);
 writew(n71_brcmf_saved_cfg[0x58/4]>>16,(u8 __iomem *)m->endpoint+0x5a);
 if(readw((u8 __iomem *)m->endpoint+4)!=2||readw((u8 __iomem *)m->cfg+4)!=rootcmd||readl((u8 __iomem *)m->port+0x124)!=portcfg||readl((u8 __iomem *)m->port+0x128)!=portbase){rc=-EHWPOISON;goto out_ref;}
 pr_info("n71-perst-held: BRCMFMAC_NATIVE_TRIAL rc=%d BME_OFF driver_detached=1 pending_transactions_drained=1\n",rc);
out_ref:
#ifdef N71_NATIVE_WLAN_RUNTIME
 if(runtime_ref)pci_dev_put(ep);
#endif
 return rc;
}
