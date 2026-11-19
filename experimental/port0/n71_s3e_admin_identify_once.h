/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ADMIN_IDENTIFY_ONCE_H
#define N71_S3E_ADMIN_IDENTIFY_ONCE_H
#include <linux/nvme.h>
#include <linux/dma-map-ops.h>
#include "n71_s3e_admin_once_core.h"
#include "n71_s3e_queue_retire_gate.h"
/* Included after the storage/HMB guard definitions in the owning pilot. */
#define N71_ADMIN_SQ_IOVA 0x80010000U
#define N71_ADMIN_CQ_IOVA 0x80011000U
#define N71_ADMIN_DATA_MARK 0x716964656e746966ULL
static struct {
    void *page[8]; /* SQ, CQ, data, SGL, then one L2 per DART stream */
    dma_addr_t dma[8];
    bool mapped[8],dart_mapped,prepared,regs_saved;
    bool submitted,completed,data_arrived,intms_saved;
    unsigned int old_intms,stage;
    unsigned int cq_polls,data_polls;
} n71_admin_memory;
static void n71_storage_admin_free(void)
{
    unsigned int i;
    for (i=0;i<8;i++) {
        if (n71_admin_memory.mapped[i])
            dma_unmap_single(n71_nvmmu_memory.dev,n71_admin_memory.dma[i],
                             PAGE_SIZE,DMA_BIDIRECTIONAL);
        if (n71_admin_memory.page[i])
            free_page((unsigned long)n71_admin_memory.page[i]);
    }
    memset(&n71_admin_memory,0,sizeof(n71_admin_memory));
}
static int n71_admin_alloc(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int i,j;
    if (PAGE_SIZE!=SZ_16K || n71_admin_memory.page[0] ||
        dev_is_dma_coherent(n71_nvmmu_memory.dev)) return -EPERM;
    pr_info("n71-s3e-p0: ADMIN_DMA_COHERENCY noncoherent_device=1 streaming_cache_sync_required=YES\n");
    for (i=0;i<8;i++) {
        u64 pa;
        n71_admin_memory.page[i]=(void *)__get_free_page(GFP_KERNEL);
        if (!n71_admin_memory.page[i]) return -ENOMEM;
        pa=virt_to_phys(n71_admin_memory.page[i]);
        if ((pa&4095) || pa>((1ULL<<36)-PAGE_SIZE)) return -EPERM;
        /* No automatic zeroing before inherited-owner exclusions. */
        for (j=0;j<2;j++) {
            u64 old=m->inherited_nvmmu_pa[j],size=j ? SZ_4K : SZ_16K;
            if (old && pa<old+size && old<pa+PAGE_SIZE) return -EPERM;
        }
        for (j=0;j<16;j++) {
            u64 old=m->inherited_dart_pa[j];
            if (old && pa<old+SZ_4K && old<pa+PAGE_SIZE) return -EPERM;
        }
        if (n71_hmb_memory.inherited_size &&
            pa<n71_hmb_memory.inherited_pa+n71_hmb_memory.inherited_size &&
            n71_hmb_memory.inherited_pa<pa+PAGE_SIZE) return -EPERM;
        memset(n71_admin_memory.page[i],0,PAGE_SIZE);
        n71_admin_memory.dma[i]=dma_map_single(n71_nvmmu_memory.dev,
            n71_admin_memory.page[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        if (dma_mapping_error(n71_nvmmu_memory.dev,n71_admin_memory.dma[i]))
            return -EIO;
        n71_admin_memory.mapped[i]=true;
        if (n71_admin_memory.dma[i]!=pa) return -EPERM;
    }
    pr_info("n71-s3e-p0: ADMIN_OWNED_MEMORY buffers=8 backing_bytes=%lu direct_dma=1 pa36=1 inherited_overlap_checked_before_zero=YES addresses_redacted=YES\n",8UL*PAGE_SIZE);
    return 0;
}
static int n71_admin_flush(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int i;
    writel(0xf02U,m->dart);
    for (i=0;i<1000;i++) {
        if (!(readl(m->dart)&BIT(3))) return 0;
        udelay(1);
    }
    return -3;
}
static int n71_admin_dart_map(void *ctx,int install)
{
    unsigned int sid,t;
    struct device *d=n71_nvmmu_memory.dev;
    if (!n71_storage_hmb_owned_ready(ctx)) return -EPERM;
    n71_admin_memory.dart_mapped=true; /* retain on a partial failure */
    for (sid=0;sid<4;sid++) {
        __le64 *l2=n71_admin_memory.page[4+sid];
        dma_sync_single_for_cpu(d,n71_admin_memory.dma[4+sid],PAGE_SIZE,DMA_BIDIRECTIONAL);
        memset(l2,0,PAGE_SIZE);
        if (install) {
            l2[16]=cpu_to_le64(n71_admin_memory.dma[0]|3ULL);
            l2[17]=cpu_to_le64(n71_admin_memory.dma[1]|3ULL);
        }
        dma_sync_single_for_device(d,n71_admin_memory.dma[4+sid],PAGE_SIZE,DMA_BIDIRECTIONAL);
        for (t=0;t<4;t+=2) {
            unsigned int index=4*sid+t;
            __le64 *l1=n71_tables.page[index];
            dma_sync_single_for_cpu(d,n71_tables.dma[index],PAGE_SIZE,DMA_TO_DEVICE);
            /* Original S5L8960x non-leaf builder: PA[35:12] | 3.
             * The PA|1 pilot faulted at the SQ address; PA|3 follows Apple. */
            l1[0]=install ? cpu_to_le64(n71_admin_memory.dma[4+sid]|3ULL) : 0;
            dma_sync_single_for_device(d,n71_tables.dma[index],PAGE_SIZE,DMA_TO_DEVICE);
        }
    }
    dma_wmb();
    if (n71_admin_flush(ctx)) return -3;
    n71_admin_memory.dart_mapped=!!install;
    pr_info("n71-s3e-p0: ADMIN_DART_QUEUE_MAP installed=%d streams=4 mapped_pages_per_stream=2 absolute_and_relative_windows=YES flush_pass=1 addresses_redacted=YES\n",install);
    return 0;
}
static unsigned int n71_admin_reg(unsigned int off)
{
    return readl((u8 __iomem *)n71_nvme_mmio+off);
}
static void n71_admin_write(unsigned int off,unsigned int value)
{
    writel(value,(u8 __iomem *)n71_nvme_mmio+off);
    readl((u8 __iomem *)n71_nvme_mmio+off);
}
static int n71_admin_qualified(void *ctx)
{
    return n71_admin_memory.prepared && n71_admin_memory.dart_mapped &&
        n71_storage_hmb_owned_ready(ctx) &&
        n71_storage_ans_hmb_read(ctx,0x1810)==0xbc000000U &&
        !n71_storage_ans_hmb_read(ctx,0x1814) &&
        n71_storage_ans_hmb_read(ctx,0x1818)==SZ_8M;
}
static int n71_admin_master(void *ctx,int enable)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int value=enable ? 6 : 2;
    if (enable && (!ans_identify_once || !n71_admin_qualified(ctx))) return -EPERM;
    /* These are 16-bit command writes. Never touch W1C PCI status. */
    writew(value,(u8 __iomem *)m->cfg+4);
    writew(value,(u8 __iomem *)m->endpoint+4);
    if ((n71_storage_root_read(ctx,4)&0xffffU)!=value ||
        (n71_storage_endpoint_read(ctx,4)&0xffffU)!=value) return -EIO;
    pr_info("n71-s3e-p0: ADMIN_BME_STATE enabled=%d both_command_words=%u\n",enable,value);
    return 0;
}
static void n71_admin_cc(void *ctx,unsigned int value)
{
    const char *phase;
    if (WARN_ON_ONCE(value!=0 && value!=0x460001U && value!=0x464001U)) return;
    phase=value==0x460001U ? "enable" :
          value==0x464001U ? "shutdown" : "disable";
    /* Optional READS only: CC transition INTMS and PERST snapshots.
     * The existing CC write below is unchanged. Never zero a queue,
     * unmap DART/NVMMU/HMB or infer that DMA has retired. */
    if (ans_phase_trace_ro)
        pr_info("n71-s3e-p0: ADMIN_CC_INTMS_RO phase=%s edge=before intms_bit0=%u perst_high=%u no_dma_release=YES\n",
            phase,!!(n71_admin_reg(0x0c)&1),n71_storage_reset_level(ctx)==1);
    n71_admin_write(0x14,value);
    if (ans_phase_trace_ro)
        pr_info("n71-s3e-p0: ADMIN_CC_INTMS_RO phase=%s edge=after intms_bit0=%u perst_high=%u no_dma_release=YES\n",
            phase,!!(n71_admin_reg(0x0c)&1),n71_storage_reset_level(ctx)==1);
}
static unsigned int n71_admin_csts(void *ctx) {return n71_admin_reg(0x1c);}
static void n71_admin_delay(void *ctx,unsigned int ms) {usleep_range(ms*1000UL,ms*1000UL+100);}
static int n71_admin_identify_ns1(void *ctx)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct nvme_completion cqe;
    struct nvme_id_ns *ns=n71_admin_memory.page[2];
    unsigned int i,status=0,format,lbads;
    u64 nsze,ncap,nuse,*tail=(u64 *)((u8 *)ns+SZ_4K-16);
    bool complete=false,arrived=false;
    if (!n71_storage_endpoint_ready(ctx) ||
        (n71_storage_root_read(ctx,4)&0xffffU)!=6 ||
        (n71_storage_endpoint_read(ctx,4)&0xffffU)!=6 ||
        n71_admin_reg(0x14)!=0x460001U || n71_admin_reg(0x1c)!=1 ||
        !(n71_admin_reg(0x0c)&1))
        return -EPERM;
    /* The one and only submitted opcode is Identify, namespace 1, CNS 0. */
    dma_wmb();
    n71_admin_write(0x1000,1);
    n71_admin_memory.submitted=true;
    for (i=0;i<5000;i++) {
        struct nvme_completion *cq=n71_admin_memory.page[1];
        dma_sync_single_for_cpu(d,n71_admin_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        status=le16_to_cpu(READ_ONCE(cq->status));
        if (status&1) {
            dma_rmb();
            memcpy(&cqe,cq,sizeof(cqe));
            complete=true;
        }
        dma_sync_single_for_device(d,n71_admin_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_admin_memory.cq_polls++;
        if (complete) break;
        if (n71_admin_reg(0x1c)&2) break;
        usleep_range(1000,1100);
    }
    pr_info("n71-s3e-p0: IDENTIFY_NS1_COMPLETION present=%u status=%04x polls=%u csts=%08x\n",
        complete,status,n71_admin_memory.cq_polls,n71_admin_reg(0x1c));
    if (!complete) return -ETIMEDOUT;
    n71_admin_memory.completed=true;
    n71_admin_write(0x1004,1);
    if ((status>>1) || le16_to_cpu(cqe.command_id)!=1 ||
        le16_to_cpu(cqe.sq_id)!=0 || le16_to_cpu(cqe.sq_head)!=1)
        return -EIO;
    /* CQ and data use different DMA paths. Do not accept CQ as data proof. */
    for (i=0;i<1000;i++) {
        dma_sync_single_for_cpu(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_rmb();
        arrived=READ_ONCE(tail[0])!=N71_ADMIN_DATA_MARK &&
                READ_ONCE(tail[1])!=~N71_ADMIN_DATA_MARK;
        if (arrived) break;
        dma_sync_single_for_device(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_admin_memory.data_polls++;
        udelay(100);
    }
    n71_admin_memory.data_arrived=arrived;
    if (!arrived) return -ENODATA;
    nsze=le64_to_cpu(ns->nsze);ncap=le64_to_cpu(ns->ncap);nuse=le64_to_cpu(ns->nuse);
    format=ns->flbas&15;lbads=ns->lbaf[format].ds;
    if (!nsze || ncap>nsze || nuse>nsze || format>ns->nlbaf ||
        lbads<9 || lbads>16 || nsze>(U64_MAX>>lbads)) return -EPROTO;
    pr_info("n71-s3e-p0: IDENTIFY_NAMESPACE_REAL nsid=1 nsze=%llu ncap=%llu nuse=%llu lba_bytes=%u capacity_bytes=%llu data_tail_arrived=1 data_wait_polls=%u personal_identifiers_redacted=YES no_block_IO=YES\n",
        nsze,ncap,nuse,1U<<lbads,nsze<<lbads,n71_admin_memory.data_polls);
    return 0;
}
static int n71_admin_prepare(void *ctx)
{
    struct device *d=n71_nvmmu_memory.dev;
    struct nvme_command command={};
    __le32 *tcb=n71_nvmmu_memory.page[0],*sgl;
    u64 *tail;
    int rc;
    unsigned int i;
    BUILD_BUG_ON(sizeof(command)!=64);
    BUILD_BUG_ON(sizeof(struct nvme_completion)!=16);
    n71_admin_memory.stage=1;
    rc=n71_admin_alloc(ctx);
    if (rc) return rc;
    n71_admin_memory.stage=2;
    dma_sync_single_for_cpu(d,n71_admin_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    command.identify.opcode=nvme_admin_identify;
    command.identify.flags=BIT(5);
    command.identify.command_id=cpu_to_le16(1);
    command.identify.nsid=cpu_to_le32(1);
    command.identify.cns=0;
    command.identify.dptr.prp1=cpu_to_le64(0x40000000ULL);
    memcpy(n71_admin_memory.page[0],&command,sizeof(command));
    dma_sync_single_for_device(d,n71_admin_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_sync_single_for_cpu(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
    memset(n71_admin_memory.page[2],0xa5,SZ_4K);
    tail=(u64 *)((u8 *)n71_admin_memory.page[2]+SZ_4K-16);
    tail[0]=N71_ADMIN_DATA_MARK;tail[1]=~N71_ADMIN_DATA_MARK;
    dma_sync_single_for_device(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_sync_single_for_cpu(d,n71_admin_memory.dma[3],PAGE_SIZE,DMA_BIDIRECTIONAL);
    sgl=n71_admin_memory.page[3];sgl[0]=cpu_to_le32(n71_admin_memory.dma[2]>>12);
    dma_sync_single_for_device(d,n71_admin_memory.dma[3],PAGE_SIZE,DMA_BIDIRECTIONAL);
    dma_sync_single_for_cpu(d,n71_nvmmu_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    tcb[0]=cpu_to_le32(0x200);tcb[2]=cpu_to_le32(n71_admin_memory.dma[2]>>12);
    tcb[4]=cpu_to_le32(lower_32_bits(n71_admin_memory.dma[3]));
    tcb[5]=cpu_to_le32(upper_32_bits(n71_admin_memory.dma[3]));
    dma_wmb();tcb[1]=cpu_to_le32(1); /* publish page count last */
    dma_sync_single_for_device(d,n71_nvmmu_memory.dma[0],PAGE_SIZE,DMA_BIDIRECTIONAL);
    n71_admin_memory.stage=3;
    rc=n71_admin_dart_map(ctx,1);
    if (rc) return rc;
    n71_admin_memory.stage=4;
    pr_info("n71-s3e-p0: ADMIN_QUEUE_BASELINE aqa=%08x ASQ_present=%u ACQ_present=%u addresses_redacted=YES\n",
        n71_admin_reg(0x24),!!(n71_admin_reg(0x28)|n71_admin_reg(0x2c)),
        !!(n71_admin_reg(0x30)|n71_admin_reg(0x34)));
    for (i=0x24;i<=0x34;i+=4)
        if (n71_admin_reg(i)) return -EPROTO;
    n71_admin_memory.regs_saved=true; /* all original queue fields are zero */
    n71_admin_memory.old_intms=n71_admin_reg(0x0c);
    n71_admin_memory.intms_saved=true;
    n71_admin_write(0x0c,~0U);
    if (!(n71_admin_reg(0x0c)&1)) return -EIO;
    pr_info("n71-s3e-p0: ADMIN_INTERRUPTS_MASKED admin_vector0_masked=1\n");
    n71_admin_write(0x24,0x000f000fU);
    n71_admin_write(0x28,N71_ADMIN_SQ_IOVA);n71_admin_write(0x2c,0);
    n71_admin_write(0x30,N71_ADMIN_CQ_IOVA);n71_admin_write(0x34,0);
    if (n71_admin_reg(0x24)!=0x000f000fU || n71_admin_reg(0x28)!=N71_ADMIN_SQ_IOVA ||
        n71_admin_reg(0x2c) || n71_admin_reg(0x30)!=N71_ADMIN_CQ_IOVA ||
        n71_admin_reg(0x34)) return -EIO;
    n71_admin_memory.prepared=true;n71_admin_memory.stage=5;
    pr_info("n71-s3e-p0: ADMIN_PREPARED queue_depth=16 controller_page_bytes=4096 host_page_bytes=%lu opcode=6 nsid=1 cns=0 FlatDMA_tag=0 only_owned_memory=YES\n",PAGE_SIZE);
    return 0;
}
static int n71_admin_unprepare(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i;
    if (!n71_storage_hmb_owned_ready(ctx)) return -3;
    if (n71_admin_memory.regs_saved) {
        for (i=0x24;i<=0x34;i+=4) n71_admin_write(i,0);
        for (i=0x24;i<=0x34;i+=4) if (n71_admin_reg(i)) return -3;
    }
    if (n71_admin_memory.intms_saved) {
        n71_admin_write(0x10,~n71_admin_memory.old_intms);
        n71_admin_write(0x0c,n71_admin_memory.old_intms);
        if (n71_admin_reg(0x0c)!=n71_admin_memory.old_intms) return -3;
    }
    if (n71_admin_memory.dart_mapped && n71_admin_dart_map(ctx,0)) return -3;
    /* CC=0, RDY/CFS=0 and both BME bits off before retiring FlatDMA. */
    for (i=0;i<2;i++) {
        dma_sync_single_for_cpu(d,n71_nvmmu_memory.dma[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        memset(n71_nvmmu_memory.page[i],0,PAGE_SIZE);
        dma_sync_single_for_device(d,n71_nvmmu_memory.dma[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
    }
    dma_wmb();
    writel(0x10000U,(u8 __iomem *)m->nvmmu+4);
    for (i=0;i<1000;i++) {
        if (!(readl((u8 __iomem *)m->nvmmu+4)&BIT(16))) break;
        udelay(1);
    }
    if (i==1000 || !(readl((u8 __iomem *)m->local+0x22c)&1) ||
        !n71_storage_hmb_owned_ready(ctx)) return -3;
    n71_admin_memory.prepared=false;
    pr_info("n71-s3e-p0: ADMIN_UNPREPARED queue_regs_restored=1 DART_leaves_removed=1 TCB_aux_zero=1 NVMMU_flush_pass=1 BME_OFF=1 buffers_retained_until_PERST_LOW=YES\n");
    return 0;
}
/* Optional, explicitly armed first-stage queue register retirement trial.
 * NOT equivalent to DMA retirement: always leave HMB, DART, NVMMU and
 * all backing pages pinned afterward, even if every queue register clears.
 * No additional NVMe command, no DART/NVMMU writes and no NAND block I/O.
 */
static void n71_admin_queue_register_retire_probe(void *ctx,
        const struct n71_admin_once_result *r)
{
    struct n71_queue_retire_observation v={};
    unsigned int i;
    bool cleared=true;
    bool phase_ok, hmb_owned=false;
    if (!ans_queue_retire_probe) return;
    /* Keep the original short-circuit contract: never inspect HMB
     * ownership on a failed shutdown, disabled controller or command.
     * Report each boolean even when the 13 register predicates cannot
     * safely be read. This branch never touches NVMe queue registers. */
    phase_ok=ans_identify_once && r->shutdown_attempted &&
        !r->shutdown_rc && !r->disable_rc && !r->inner_rc &&
        r->master_off;
    if (phase_ok)
        hmb_owned=n71_storage_hmb_owned_ready(ctx);
    if (!phase_ok || !hmb_owned) {
        pr_err("n71-s3e-p0: ADMIN_QUEUE_RETIRE_PHASE_GATES identify_armed=%u shutdown_attempted=%u shutdown_ok=%u disable_ok=%u inner_ok=%u master_off=%u hmb_checked=%u hmb_owned=%u action=REFUSE_KEEP_QUARANTINE\n",
            !!ans_identify_once, !!r->shutdown_attempted,
            !r->shutdown_rc, !r->disable_rc, !r->inner_rc,
            !!r->master_off, phase_ok, hmb_owned);
        pr_err("n71-s3e-p0: ADMIN_QUEUE_RETIRE_PROBE refused=1 phase_gate=0 DMA_QUARANTINE=YES\n");
        return;
    }
    v.shutdown_attempted=r->shutdown_attempted;
    v.shutdown_rc=r->shutdown_rc;
    v.shutdown_csts=r->shutdown_csts;
    v.disable_rc=r->disable_rc;
    v.disable_csts=r->disable_csts;
    v.master_off=r->master_off;
    v.cc=n71_admin_reg(0x14);
    v.csts=n71_admin_reg(0x1c);
    v.root_command=n71_storage_root_read(ctx,4)&0xffffU;
    v.endpoint_command=n71_storage_endpoint_read(ctx,4)&0xffffU;
    v.reset_low=n71_storage_reset_level(ctx)==0;
    v.prepared=n71_admin_memory.prepared;
    v.regs_saved=n71_admin_memory.regs_saved;
    v.dart_mapped=n71_admin_memory.dart_mapped;
    v.hmb_owned=n71_storage_hmb_owned_ready(ctx);
    v.hmb_lo=n71_storage_ans_hmb_read(ctx,0x1810);
    v.hmb_hi=n71_storage_ans_hmb_read(ctx,0x1814);
    v.hmb_size=n71_storage_ans_hmb_read(ctx,0x1818);
    v.intms=n71_admin_reg(0x0c);
    v.aqa=n71_admin_reg(0x24);
    v.asq_lo=n71_admin_reg(0x28);
    v.asq_hi=n71_admin_reg(0x2c);
    v.acq_lo=n71_admin_reg(0x30);
    v.acq_hi=n71_admin_reg(0x34);
    if (!n71_queue_retire_gate(&v)) {
        /* Distinguish the precise failed prerequisite without printing
         * register IOVAs, DMA/physical backing addresses or IDs.
         * Every item is a read-only boolean; refusal stays fail closed. */
        pr_err("n71-s3e-p0: ADMIN_QUEUE_RETIRE_GATES shn=%u disable=%u master_off=%u controller_zero=%u command_words_2=%u reset_low=%u prepared=%u regs_saved=%u dart_mapped=%u hmb_owned=%u hmb_zero=%u intms_bit0=%u queue_owned=%u action=REFUSE_KEEP_QUARANTINE\n",
            v.shutdown_attempted==1 && !v.shutdown_rc && v.shutdown_csts==9,
            !v.disable_rc && !v.disable_csts,
            v.master_off==1,
            !v.cc && !v.csts,
            v.root_command==2 && v.endpoint_command==2,
            v.reset_low==1,
            v.prepared==1,
            v.regs_saved==1,
            v.dart_mapped==1,
            v.hmb_owned==1,
            !v.hmb_lo && !v.hmb_hi && !v.hmb_size,
            !!(v.intms & 1),
            v.aqa==0x000f000fU &&
                v.asq_lo==N71_ADMIN_SQ_IOVA && !v.asq_hi &&
                v.acq_lo==N71_ADMIN_CQ_IOVA && !v.acq_hi);
        pr_err("n71-s3e-p0: ADMIN_QUEUE_RETIRE_PROBE refused=1 exact_gate=0 DMA_QUARANTINE=YES\n");
        return;
    }
    /* CC=0, CSTS=0, both PCI commands=2, SHST=2, HMB descriptor=0,
     * NAND reset asserted and all queue registers match owned values.
     * No DMA buffers or page tables are released here. */
    for (i=0x24;i<=0x34;i+=4) n71_admin_write(i,0);
    for (i=0x24;i<=0x34;i+=4)
        if (n71_admin_reg(i)) cleared=false;
    pr_info("n71-s3e-p0: ADMIN_QUEUE_RETIRE_PROBE armed=1 queue_regs_zero=%u controller_disabled=YES BME_OFF=YES HMB_DESCRIPTOR_ZERO=YES DART_STILL_MAPPED=YES NVMMU_UNTOUCHED=YES DMA_QUARANTINE=YES\n",
            cleared);
}
static int n71_storage_admin_identify_once(void *ctx)
{
    const struct n71_admin_once_ops o={
        .qualified=n71_admin_qualified,.master=n71_admin_master,.cc=n71_admin_cc,
        .csts=n71_admin_csts,.delay_ms=n71_admin_delay,.identify=n71_admin_identify_ns1,
    };
    struct n71_admin_once_result r={};
    int rc;
    if (!ans_identify_once || !n71_storage_hmb_owned_ready(ctx)) return -EPERM;
    rc=n71_admin_prepare(ctx);
    if (!rc) {
        rc=n71_admin_once_core(&o,ctx,&r);
        pr_info("n71-s3e-p0: ADMIN_IDENTIFY_ONCE rc=%d master_seen=%u controller_started=%u ready=%u submitted=%u completed=%u data_arrived=%u stopped=%u master_off=%u enable_polls=%u shutdown_polls=%u disable_polls=%u last_csts=%08x\n",
            rc,r.master_seen,r.started,r.ready,n71_admin_memory.submitted,
            n71_admin_memory.completed,n71_admin_memory.data_arrived,r.stopped,
            r.master_off,r.enable_polls,r.shutdown_polls,r.disable_polls,r.last_csts);
        pr_info("n71-s3e-p0: ADMIN_SHUTDOWN_TRACE attempted=%u rc=%d csts=%08x polls=%u disable_rc=%d disable_csts=%08x inner_rc=%d master_off=%u retained_on_uncertainty=YES\n",
            r.shutdown_attempted,r.shutdown_rc,r.shutdown_csts,r.shutdown_polls,
            r.disable_rc,r.disable_csts,r.inner_rc,r.master_off);
        /* Read-only predicate breakdown: never changes the original
         * quarantine outcome or programs the NVMe/HMB/SART/NVMMU registers.
         * No physical DMA addresses or identifiers are printed. */
        if (r.master_off && !r.disable_rc) {
            struct n71_storage_dart_context *m=ctx;
            unsigned int ready=n71_storage_ans_hmb_ready(ctx);
            unsigned int owned=n71_storage_hmb_owned_ready(ctx);
            /* These are *controller IOVA descriptor registers*, never a
             * physical HMB pointer. Read them once, only if the qualified
             * MMIO window is still accessible, with no hardware writes. */
            u32 hmb_lo=ready ? n71_storage_ans_hmb_read(ctx,0x1810) : ~0U;
            u32 hmb_hi=ready ? n71_storage_ans_hmb_read(ctx,0x1814) : ~0U;
            u32 hmb_size=ready ? n71_storage_ans_hmb_read(ctx,0x1818) : ~0U;
            unsigned int base_ok=ready && hmb_lo==0xbc000000U && !hmb_hi;
            unsigned int size_ok=ready && hmb_size==SZ_8M;
            pr_info("n71-s3e-p0: ADMIN_POST_DISABLE_PREDICATES qualified=%u prepared=%u dart_mapped=%u hmb_owned=%u ans_ready=%u ans_hmb_base_ok=%u ans_hmb_size_ok=%u endpoint_ready=%u root_cmd_2=%u endpoint_cmd_2=%u cc_zero=%u csts_zero=%u nvmmu_ctrl_1=%u nvmmu_inv_zero=%u retained_on_uncertainty=YES\n",
                r.post_disable_qualified,
                n71_admin_memory.prepared,n71_admin_memory.dart_mapped,
                owned,ready,base_ok,size_ok,
                n71_storage_endpoint_ready(ctx),
                (n71_storage_root_read(ctx,4)&0xffffU)==2,
                (n71_storage_endpoint_read(ctx,4)&0xffffU)==2,
                n71_admin_reg(0x14)==0,n71_admin_reg(0x1c)==0,
                readl(m->nvmmu)==1,
                readl((u8 __iomem *)m->nvmmu+4)==0);
            pr_info("n71-s3e-p0: ADMIN_POST_DISABLE_HMB_DESCRIPTOR accessible=%u iova_base_low=%08x iova_base_high=%08x size_bytes=%08x base_zero=%u size_zero=%u no_physical_addresses=YES quarantine_unchanged=YES\n",
                ready,hmb_lo,hmb_hi,hmb_size,
                ready && !hmb_lo && !hmb_hi,ready && !hmb_size);
            /* Post-stop queue/translation snapshot only. ASQ/ACQ are
             * controller IOVAs, not backing physical addresses, and
             * are intentionally compared rather than printed. A zeroed
             * HMB descriptor alone is insufficient to release DMA. */
            {
                u32 aqa=n71_admin_reg(0x24);
                u32 asq_lo=n71_admin_reg(0x28);
                u32 asq_hi=n71_admin_reg(0x2c);
                u32 acq_lo=n71_admin_reg(0x30);
                u32 acq_hi=n71_admin_reg(0x34);
                u32 dart_fault=readl((u8 __iomem *)m->dart+0x10);
                u32 nvmmu_fifo=readl((u8 __iomem *)m->local+0x22c);
                unsigned int queues_zero=!(aqa|asq_lo|asq_hi|acq_lo|acq_hi);
                unsigned int queues_owned=aqa==0x000f000fU &&
                    asq_lo==N71_ADMIN_SQ_IOVA && !asq_hi &&
                    acq_lo==N71_ADMIN_CQ_IOVA && !acq_hi;
                /* Post-core READ-ONLY evidence at the same lifetime point
                 * as the optional retired-queue gate. Not DMA authority.
                 * No new MMIO writes, reset changes or memory release. */
                if (ans_phase_trace_ro)
                    pr_info("n71-s3e-p0: ADMIN_POST_CORE_RO intms_bit0=%u reset_low=%u hmb_descriptor_zero=%u queues_owned=%u master_off=1 no_dma_release=YES\n",
                        !!(n71_admin_reg(0x0c)&1),
                        n71_storage_reset_level(ctx)==0,
                        ready && !hmb_lo && !hmb_hi && !hmb_size,
                        queues_owned);
                pr_info("n71-s3e-p0: ADMIN_POST_STOP_DMA_SNAPSHOT hmb_descriptor_zero=%u queues_zero=%u queues_owned_io_va=%u dart_queues_mapped=%u dart_fault=%08x nvmmu_fifo=%08x no_dma_release_attempted=YES quarantine_unchanged=YES\n",
                    ready && !hmb_lo && !hmb_hi && !hmb_size,
                    queues_zero,queues_owned,n71_admin_memory.dart_mapped,
                    dart_fault,nvmmu_fifo);
            }
        }
    }
    /* Even on successful queue register clear, this opt-in pilot NEVER
     * authorizes DART/HMB/NVMMU retirement, power-off or DMA free. */
    if (ans_queue_retire_probe) {
        n71_admin_queue_register_retire_probe(ctx,&r);
        rc=-3; /* pin every owned DMA resource until full phone restart */
    }
    pr_info("n71-s3e-p0: ADMIN_STAGE rc=%d prepare_stage=%u dart_fault=%08x nvmmu_fifo=%08x\n",
        rc,n71_admin_memory.stage,
        readl((u8 __iomem *)((struct n71_storage_dart_context *)ctx)->dart+0x10),
        readl((u8 __iomem *)((struct n71_storage_dart_context *)ctx)->local+0x22c));
    if (rc==-3) return -3;
    if (n71_admin_unprepare(ctx)) return -3;
    return rc;
}
#endif
