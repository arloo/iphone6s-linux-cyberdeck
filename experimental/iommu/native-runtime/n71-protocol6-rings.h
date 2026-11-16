/* SPDX-License-Identifier: GPL-2.0-only */
/* Protocol6 control-plane qualification, following brcmfmac pcie.c/msgbuf.h.
 * Default: BME stays OFF. N71_PROTOCOL6_DMA_REQUEST enables one bounded
 * real GET_VERSION exchange, with private firmware and translated SID0 only.
 * CONTROL_SEQUENCE adds bounded read-only revision/band/capability queries;
 * MSI_DELIVERY additionally requires a genuine, one-shot WLAN IRQ. */
static bool n71_tcm_range(u32 p,u32 bytes)
{return p>=0x180000 && p<0x240000 && bytes<=0x240000-p && !(p&3);}
#ifdef N71_PROTOCOL6_DMA_REQUEST
#include <linux/unaligned.h>
#ifdef N71_PROTOCOL6_MSI_DELIVERY
#include "n71-protocol6-msi.h"
#endif
static int n71_protocol6_version_request(struct pci_dev *pdev,void __iomem *ram,u32 shared,u32 *ptr,void **ring)
{
#ifdef N71_PROTOCOL6_MSI_DELIVERY
 struct n71_control_msi msi={};bool msi_started=false;
#endif
 struct n71_dart_trial_mmio *m=n71_pci_dma_context;
 struct iommu_domain *domain=iommu_get_domain_for_dev(&pdev->dev);
 void *resp=NULL,*input=NULL;dma_addr_t rdma=0,idma=0;u32 window,cmd[2],fault;u16 oldw,oldr;int rc=-EIO,i,step;bool drained=true;
 u8 scratch_saved[24];bool scratch_published=false;void __iomem *scratch=(u8 __iomem *)ram+shared-0x180000+52;
 const u32 commands[]={1,98,140,262};
 const u16 lengths[]={4,68,12,512};
#ifdef N71_PROTOCOL6_CONTROL_SEQUENCE
 const int steps=4;
#else
 const int steps=1;
#endif
 u8 *post,*request;u16 done=0,status=0,length=0,reported=0;u32 version=0;
 if(!n71_dma_context_ok(&pdev->dev)||domain!=n71_platform_domain)return -EPERM;
 cmd[0]=readw((u8 __iomem *)m->cfg+4);cmd[1]=readw((u8 __iomem *)m->endpoint+4);
 if(cmd[0]!=2||cmd[1]!=2||readl((u8 __iomem *)m->dart+0xc)!=0x80)return -EPERM;
 if(readw((u8 __iomem *)ram+ptr[0]-0x180000)||readw((u8 __iomem *)ram+ptr[1]-0x180000)||readw((u8 __iomem *)ram+ptr[2]-0x180000)||readw((u8 __iomem *)ram+ptr[3]-0x180000))return -EBUSY;
 resp=dma_alloc_coherent(&pdev->dev,16384,&rdma,GFP_KERNEL);input=dma_alloc_coherent(&pdev->dev,1024,&idma,GFP_KERNEL);
 if(!resp||!input){rc=-ENOMEM;goto out;}
 if(rdma<0x80000000ULL||rdma+16384>0xbfffc000ULL||idma<0x80000000ULL||idma+1024>0xbfffc000ULL||!iommu_iova_to_phys(domain,rdma)||!iommu_iova_to_phys(domain,rdma+16383)||!iommu_iova_to_phys(domain,idma)){rc=-ERANGE;goto out;}
 memset(resp,0,16384);memset(input,0,1024);
 window=readl((u8 __iomem *)m->endpoint+0x80);oldw=readw((u8 __iomem *)ram+ptr[0]-0x180000);oldr=readw((u8 __iomem *)ram+ptr[3]-0x180000);
 writel(0x18003000,(u8 __iomem *)m->endpoint+0x80);
 if(readl((u8 __iomem *)m->endpoint+0x80)!=0x18003000){writel(window,(u8 __iomem *)m->endpoint+0x80);rc=-EIO;goto out;}
 /* Match brcmfmac shared +52..75: bounded scratch/ring-update host buffers.
  * Required before endpoint DMA; restored and read back before freeing. */
 memcpy_fromio(scratch_saved,scratch,24);scratch_published=true;
 writel(8,scratch);writel(lower_32_bits(rdma+8192),(u8 __iomem *)scratch+4);writel(upper_32_bits(rdma+8192),(u8 __iomem *)scratch+8);
 writel(1024,(u8 __iomem *)scratch+12);writel(lower_32_bits(rdma+8208),(u8 __iomem *)scratch+16);writel(upper_32_bits(rdma+8208),(u8 __iomem *)scratch+20);
#ifdef N71_PROTOCOL6_MSI_DELIVERY
 rc=n71_control_msi_start(pdev,&msi);
 if(rc)goto stop;
 msi_started=true;
#endif
 dma_wmb();writew(6,(u8 __iomem *)m->cfg+4);writew(6,(u8 __iomem *)m->endpoint+4);
 if(readw((u8 __iomem *)m->cfg+4)!=6||readw((u8 __iomem *)m->endpoint+4)!=6)goto stop;
 for(step=0;step<steps;step++){
 post=(u8 *)ring[0]+80*step;request=post+40;
 memset(resp,0,8192);memset(input,0,1024);
 if(commands[step]==262)memcpy(input,"cap",4);
 post[0]=0xb;put_unaligned_le32(step+1,post+4);put_unaligned_le16(8192,post+8);put_unaligned_le32(lower_32_bits(rdma),post+16);put_unaligned_le32(upper_32_bits(rdma),post+20);
 request[0]=9;put_unaligned_le32(0xfffe,request+4);put_unaligned_le32(commands[step],request+8);put_unaligned_le16(step+1,request+12);put_unaligned_le16(lengths[step],request+14);put_unaligned_le16(lengths[step],request+16);put_unaligned_le32(lower_32_bits(idma),request+24);put_unaligned_le32(upper_32_bits(idma),request+28);
 dma_wmb();writew(2*(step+1),(u8 __iomem *)ram+ptr[0]-0x180000);writel(1,(u8 __iomem *)m->bar0+0x140);
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

   if(c[0]==0xc&&get_unaligned_le16(c+14)==step+1&&get_unaligned_le32(c+16)==commands[step]){
    status=get_unaligned_le16(c+8);length=get_unaligned_le16(c+12);if(commands[step]==1)version=get_unaligned_le32(resp);
    rc=(!status&&length>=4&&length<=8192&&get_unaligned_le32(c+4)==step+1)?0:-EPROTO;
    if(!rc&&commands[step]==1&&version!=2)rc=-EPROTO;
    pr_info("n71-perst-held: BRCM_DMA_QUERY step=%d command=%u rc=%d status=%u length=%u\n",step,commands[step],rc,status,length);
    if(!rc&&commands[step]==98){
     if(length<68)rc=-EPROTO;
     else pr_info("n71-perst-held: BRCM_DMA_REVINFO vendor=%04x device=%04x chip=%u chiprev=%u corerev=%u phytype=%u phyrev=%u\n",get_unaligned_le32(resp),get_unaligned_le32((u8 *)resp+4),get_unaligned_le32((u8 *)resp+44),get_unaligned_le32((u8 *)resp+12),get_unaligned_le32((u8 *)resp+16),get_unaligned_le32((u8 *)resp+48),get_unaligned_le32((u8 *)resp+52));
    }
    if(!rc&&commands[step]==140){
     u32 count=get_unaligned_le32(resp);
     if(count>2||length<4+4*count)rc=-EPROTO;
     else pr_info("n71-perst-held: BRCM_DMA_BANDLIST count=%u band0=%u band1=%u\n",count,count?get_unaligned_le32((u8 *)resp+4):0,count>1?get_unaligned_le32((u8 *)resp+8):0);
    }
    if(!rc&&commands[step]==262){
     ((u8 *)resp)[min_t(u16,length,511)]=0;
     pr_info("n71-perst-held: BRCM_DMA_CAPABILITIES returned=1 escan=%u p2p=%u mbss=%u\n",!!strstr(resp,"escan"),!!strstr(resp,"p2p"),!!strstr(resp,"mbss"));
    }
    goto query_done;
   }
  }}
  reported=done;
 }
query_done:
 if(rc)break;
 reported=done;dma_wmb();writew(done,(u8 __iomem *)ram+ptr[3]-0x180000);
 }
stop:
 writew(cmd[1],(u8 __iomem *)m->endpoint+4);writew(cmd[0],(u8 __iomem *)m->cfg+4);
 drained=readw((u8 __iomem *)m->endpoint+4)==cmd[1]&&readw((u8 __iomem *)m->cfg+4)==cmd[0]&&pci_wait_for_pending_transaction(pdev);
#ifdef N71_PROTOCOL6_MSI_DELIVERY
 if(msi_started){int mrc=n71_control_msi_stop(&msi,!rc);if(mrc)rc=mrc;}
#endif
 if(!drained){pr_err("n71-perst-held: BRCM_DMA_PENDING retain_buffers_until_PERST\n");return -EHWPOISON;}
 pr_info("n71-perst-held: BRCM_DMA_INDICES h2d_read=%u h2d_write=%u d2h_write=%u d2h_read=%u\n",readw((u8 __iomem *)ram+ptr[1]-0x180000),readw((u8 __iomem *)ram+ptr[0]-0x180000),readw((u8 __iomem *)ram+ptr[2]-0x180000),readw((u8 __iomem *)ram+ptr[3]-0x180000));
 pr_info("n71-perst-held: BRCM_DMA_BUFFER_CHECK post_type=%u request_type=%u input=%08x response=%08x\n",((u8 *)ring[0])[0],((u8 *)ring[0])[40],get_unaligned_le32(input),get_unaligned_le32(resp));
 {int cap=pci_find_capability(pdev,PCI_CAP_ID_MSI);
  pr_info("n71-perst-held: BRCM_DMA_MSI_PREFLIGHT cap=%x control=%04x port_msiaddr=%08x mailbox_status=%08x mailbox_mask=%08x READ_ONLY\n",cap,cap>=0x40&&cap<=0xe8?readw((u8 __iomem *)m->endpoint+cap+2):0,readl((u8 __iomem *)m->port+0x168),readl((u8 __iomem *)m->bar0+0x48),readl((u8 __iomem *)m->bar0+0x4c));
 }
 writew(oldr,(u8 __iomem *)ram+ptr[3]-0x180000);
 writew(oldw,(u8 __iomem *)ram+ptr[0]-0x180000);writel(window,(u8 __iomem *)m->endpoint+0x80);
 fault=readl((u8 __iomem *)m->dart+0x10);
 pr_info("n71-perst-held: BRCM_REAL_DMA_CONTROL_REQUEST rc=%d completions=%u status=%u length=%u version=%u fault=%08x BME_RESTORED pending_transactions_drained=1\n",rc,done,status,length,version,fault);
 if(scratch_published){u8 check[24];memcpy_toio(scratch,scratch_saved,24);memcpy_fromio(check,scratch,24);if(memcmp(check,scratch_saved,24))return -EHWPOISON;}
 if((fault&BIT(31))||rc==-EHWPOISON)return -EHWPOISON; /* retain all mappings until reset */
out:
 if(input)dma_free_coherent(&pdev->dev,1024,input,idma);
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
