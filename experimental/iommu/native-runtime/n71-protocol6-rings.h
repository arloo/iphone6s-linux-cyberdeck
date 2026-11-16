/* SPDX-License-Identifier: GPL-2.0-only */
/* Protocol6 control-plane qualification, following brcmfmac pcie.c/msgbuf.h.
 * BME stays OFF. No producer indices, doorbells or endpoint DMA are issued. */
static bool n71_tcm_range(u32 p,u32 bytes)
{return p>=0x180000 && p<0x240000 && bytes<=0x240000-p && !(p&3);}
static int n71_protocol6_ring_trial(struct pci_dev *pdev,void __iomem *ram,u32 shared)
{
 const u16 depth[5]={64,1024,64,1024,1024},item[5]={40,32,24,16,32};
 void *buf[5]={};dma_addr_t dma[5]={};u32 size[5];
 struct iommu_domain *domain=iommu_get_domain_for_dev(&pdev->dev);
 u32 info,mem,flags,pointers[4],off;u16 flow,sub,comp;unsigned int i,j;
 u8 saved[80];bool published=false;int rc=-EINVAL;
 void __iomem *table;
 if(!n71_dma_context_ok(&pdev->dev)||domain!=n71_platform_domain||!n71_tcm_range(shared,80))return -EPERM;
 flags=readl((u8 __iomem *)ram+shared-0x180000);
 if((flags&255)!=6)return -EPROTONOSUPPORT;
 info=readl((u8 __iomem *)ram+shared-0x180000+48);
 if(!n71_tcm_range(info,60))return -ERANGE;
 off=info-0x180000;mem=readl((u8 __iomem *)ram+off);
 for(i=0;i<4;i++)pointers[i]=readl((u8 __iomem *)ram+off+4+4*i);
 flow=readw((u8 __iomem *)ram+off+52);sub=readw((u8 __iomem *)ram+off+54);comp=readw((u8 __iomem *)ram+off+56);
 if(flow>512||sub<2||sub>514||comp<3||comp>64||!n71_tcm_range(mem,80))return -ERANGE;
 for(i=0;i<4;i++)if(!n71_tcm_range(pointers[i],4*(i<2?sub:comp)))return -ERANGE;
 pr_info("n71-perst-held: BRCM_PROTOCOL6_RING_METADATA_PASS flow=%u submission=%u completion=%u dma_index_capable=%u TCM_pointers_valid=1\n",flow,sub,comp,!!(flags&0x10000));
 table=(u8 __iomem *)ram+mem-0x180000;
 memcpy_fromio(saved,table,sizeof(saved));
 for(i=0;i<5;i++){
  size[i]=(u32)depth[i]*item[i];
  buf[i]=dma_alloc_coherent(&pdev->dev,size[i],&dma[i],GFP_KERNEL);
  if(!buf[i]){rc=-ENOMEM;goto cleanup;}
  memset(buf[i],0,size[i]);
  if(dma[i]<0x80000000ULL||dma[i]+size[i]>0xbfffc000ULL){rc=-ERANGE;goto cleanup;}
  for(j=0;j<size[i];j+=4096)if(!iommu_iova_to_phys(domain,dma[i]+j)){rc=-EFAULT;goto cleanup;}
  if(!iommu_iova_to_phys(domain,dma[i]+size[i]-1)){rc=-EFAULT;goto cleanup;}
 }
 if(!n71_dma_context_ok(&pdev->dev)){rc=-EPERM;goto cleanup;}
 published=true;dma_wmb();
 for(i=0;i<5;i++){
  void __iomem *d=(u8 __iomem *)table+i*16;
  writew(depth[i],(u8 __iomem *)d+4);writew(item[i],(u8 __iomem *)d+6);
  writel(lower_32_bits(dma[i]),(u8 __iomem *)d+8);writel(upper_32_bits(dma[i]),(u8 __iomem *)d+12);
  if(readw((u8 __iomem *)d+4)!=depth[i]||readw((u8 __iomem *)d+6)!=item[i]||readl((u8 __iomem *)d+8)!=lower_32_bits(dma[i])||readl((u8 __iomem *)d+12)!=upper_32_bits(dma[i])){rc=-EIO;goto cleanup;}
 }
 rc=0;
cleanup:
 /* Restore descriptors BEFORE releasing any DMA buffer; BME remains blocked. */
 if(published){
  u8 check[80];memcpy_toio(table,saved,sizeof(saved));memcpy_fromio(check,table,sizeof(check));
  if(memcmp(check,saved,sizeof(saved)))rc=-EIO;
 }
 if(!n71_dma_context_ok(&pdev->dev))return -EHWPOISON; /* retain buffers */
 for(i=0;i<5;i++)if(buf[i])dma_free_coherent(&pdev->dev,size[i],buf[i],dma[i]);
 pr_info("n71-perst-held: BRCM_PROTOCOL6_RING_TRIAL rc=%d rings=5 descriptors_restored=1 buffers_freed=1 BUS_MASTER_OFF no_endpoint_DMA\n",rc);
 return rc;
}
