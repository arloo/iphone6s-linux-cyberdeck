/* SPDX-License-Identifier: GPL-2.0-only */
/* Protocol6 control-plane qualification, following brcmfmac pcie.c/msgbuf.h.
 * Default: BME stays OFF. N71_PROTOCOL6_DMA_REQUEST enables one bounded
 * real GET_VERSION exchange, with private firmware and translated SID0 only. */
static bool n71_tcm_range(u32 p,u32 bytes)
{return p>=0x180000 && p<0x240000 && bytes<=0x240000-p && !(p&3);}
#ifdef N71_PROTOCOL6_DMA_REQUEST
#include <linux/unaligned.h>
static int n71_protocol6_version_request(struct pci_dev *pdev,void __iomem *ram,u32 shared,u32 *ptr,void **ring)
{
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 struct iommu_domain *domain=iommu_get_domain_for_dev(&pdev->dev);
 void *resp=NULL,*input=NULL;dma_addr_t rdma=0,idma=0;u32 window,cmd[2],fault;u16 oldw;int rc=-EIO,i;bool drained=true;
 u8 scratch_saved[24];bool scratch_published=false;void __iomem *scratch=(u8 __iomem *)ram+shared-0x180000+52;
 u8 *post=ring[0],*request=post+40;u16 done=0,status=0,length=0,reported=0;u32 version=0;
 if(!n71_dma_context_ok(&pdev->dev)||domain!=n71_platform_domain)return -EPERM;
 cmd[0]=readw((u8 __iomem *)m->cfg+4);cmd[1]=readw((u8 __iomem *)m->endpoint+4);
 if(cmd[0]!=2||cmd[1]!=2||readl((u8 __iomem *)m->dart+0xc)!=0x80)return -EPERM;
 if(readw((u8 __iomem *)ram+ptr[0]-0x180000)||readw((u8 __iomem *)ram+ptr[1]-0x180000)||readw((u8 __iomem *)ram+ptr[2]-0x180000)||readw((u8 __iomem *)ram+ptr[3]-0x180000))return -EBUSY;
 resp=dma_alloc_coherent(&pdev->dev,16384,&rdma,GFP_KERNEL);input=dma_alloc_coherent(&pdev->dev,16,&idma,GFP_KERNEL);
 if(!resp||!input){rc=-ENOMEM;goto out;}
 if(rdma<0x80000000ULL||rdma+16384>0xbfffc000ULL||idma<0x80000000ULL||idma+16>0xbfffc000ULL||!iommu_iova_to_phys(domain,rdma)||!iommu_iova_to_phys(domain,rdma+16383)||!iommu_iova_to_phys(domain,idma)){rc=-ERANGE;goto out;}
 memset(resp,0,16384);memset(input,0,16);
 post[0]=0xb;put_unaligned_le32(1,post+4);put_unaligned_le16(8192,post+8);put_unaligned_le32(lower_32_bits(rdma),post+16);put_unaligned_le32(upper_32_bits(rdma),post+20);
 request[0]=9;put_unaligned_le32(0xfffe,request+4);put_unaligned_le32(1,request+8);put_unaligned_le16(1,request+12);put_unaligned_le16(4,request+14);put_unaligned_le16(4,request+16);put_unaligned_le32(lower_32_bits(idma),request+24);put_unaligned_le32(upper_32_bits(idma),request+28);
 window=readl((u8 __iomem *)m->endpoint+0x80);oldw=readw((u8 __iomem *)ram+ptr[0]-0x180000);
 writel(0x18003000,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18003000){writel(window,(u8 __iomem *)m->endpoint+0x80);rc=-EIO;goto out;}
 /* Match brcmfmac shared +52..75: bounded scratch/ring-update host buffers.
  * Required before endpoint DMA; restored and read back before freeing. */
 memcpy_fromio(scratch_saved,scratch,24);scratch_published=true;
 writel(8,scratch);writel(lower_32_bits(rdma+8192),(u8 __iomem *)scratch+4);writel(upper_32_bits(rdma+8192),(u8 __iomem *)scratch+8);
 writel(1024,(u8 __iomem *)scratch+12);writel(lower_32_bits(rdma+8208),(u8 __iomem *)scratch+16);writel(upper_32_bits(rdma+8208),(u8 __iomem *)scratch+20);
 dma_wmb();writew(6,(u8 __iomem *)m->cfg+4);writew(6,(u8 __iomem *)m->endpoint+4);
 if(readw((u8 __iomem *)m->cfg+4)!=6||readw((u8 __iomem *)m->endpoint+4)!=6)goto stop;
 writew(2,(u8 __iomem *)ram+ptr[0]-0x180000);writel(1,(u8 __iomem *)m->bar0+0x140);
 rc=-ETIMEDOUT;
 for(i=0;i<50;i++){
  msleep(10);fault=readl((u8 __iomem *)m->dart+0x10);
  if(fault&BIT(31)){rc=-EFAULT;break;}
  done=readw((u8 __iomem *)ram+ptr[2]-0x180000);
  if(done>63){rc=-EPROTO;break;}
  dma_rmb();
  {unsigned int j;for(j=0;j<done;j++){
   u8 *c=(u8 *)ring[2]+24*j;
   if(j>=reported)pr_info("n71-perst-held: BRCM_DMA_CONTROL_MESSAGE index=%u type=%u request_id=%u status=%u length=%u trans_id=%u command=%u\n",j,c[0],get_unaligned_le32(c+4),get_unaligned_le16(c+8),get_unaligned_le16(c+12),get_unaligned_le16(c+14),get_unaligned_le32(c+16));

   if(c[0]==0xc&&get_unaligned_le16(c+14)==1&&get_unaligned_le32(c+16)==1){
    status=get_unaligned_le16(c+8);length=get_unaligned_le16(c+12);version=get_unaligned_le32(resp);
    rc=(!status&&length>=4&&get_unaligned_le32(c+4)==1&&version==2)?0:-EPROTO;goto stop;
   }
  }}
  reported=done;
 }
stop:
 writew(cmd[1],(u8 __iomem *)m->endpoint+4);writew(cmd[0],(u8 __iomem *)m->cfg+4);
 drained=readw((u8 __iomem *)m->endpoint+4)==cmd[1]&&readw((u8 __iomem *)m->cfg+4)==cmd[0]&&pci_wait_for_pending_transaction(pdev);
 if(!drained){pr_err("n71-perst-held: BRCM_DMA_PENDING retain_buffers_until_PERST\n");return -EHWPOISON;}
 pr_info("n71-perst-held: BRCM_DMA_INDICES h2d_read=%u h2d_write=%u d2h_write=%u d2h_read=%u\n",readw((u8 __iomem *)ram+ptr[1]-0x180000),readw((u8 __iomem *)ram+ptr[0]-0x180000),readw((u8 __iomem *)ram+ptr[2]-0x180000),readw((u8 __iomem *)ram+ptr[3]-0x180000));
 pr_info("n71-perst-held: BRCM_DMA_BUFFER_CHECK post_type=%u request_type=%u input=%08x response=%08x\n",post[0],request[0],get_unaligned_le32(input),get_unaligned_le32(resp));
 writew(oldw,(u8 __iomem *)ram+ptr[0]-0x180000);writel(window,(u8 __iomem *)m->endpoint+0x80);
 fault=readl((u8 __iomem *)m->dart+0x10);
 pr_info("n71-perst-held: BRCM_REAL_DMA_VERSION_REQUEST rc=%d completions=%u status=%u length=%u version=%u fault=%08x BME_RESTORED pending_transactions_drained=1\n",rc,done,status,length,version,fault);
 if(scratch_published){u8 check[24];memcpy_toio(scratch,scratch_saved,24);memcpy_fromio(check,scratch,24);if(memcmp(check,scratch_saved,24))return -EHWPOISON;}
 if(fault&BIT(31))return -EHWPOISON; /* retain all mappings until reset */
out:
 if(input)dma_free_coherent(&pdev->dev,16,input,idma);
 if(resp)dma_free_coherent(&pdev->dev,16384,resp,rdma);
 return rc;
}
#endif
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
 pr_info("n71-perst-held: BRCM_PROTOCOL6_RX_DATAOFFSET value=%u\n",readl((u8 __iomem *)ram+shared-0x180000+36));
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
#ifdef N71_PROTOCOL6_DMA_REQUEST
 rc=n71_protocol6_version_request(pdev,ram,shared,pointers,buf);
 if(rc==-EHWPOISON)return rc;
#endif
cleanup:
 /* Restore descriptors BEFORE releasing any DMA buffer; BME remains blocked. */
 if(published){
  u8 check[80];memcpy_toio(table,saved,sizeof(saved));memcpy_fromio(check,table,sizeof(check));
  if(memcmp(check,saved,sizeof(saved)))rc=-EIO;
 }
 if(!n71_dma_context_ok(&pdev->dev))return -EHWPOISON; /* retain buffers */
 for(i=0;i<5;i++)if(buf[i])dma_free_coherent(&pdev->dev,size[i],buf[i],dma[i]);
 pr_info("n71-perst-held: BRCM_PROTOCOL6_RING_TRIAL rc=%d rings=5 descriptors_restored=1 buffers_freed=1 BUS_MASTER_OFF DMA_trial_scope=protocol6\n",rc);
 return rc;
}
