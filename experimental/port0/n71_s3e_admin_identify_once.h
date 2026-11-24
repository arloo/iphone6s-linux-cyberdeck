/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ADMIN_IDENTIFY_ONCE_H
#define N71_S3E_ADMIN_IDENTIFY_ONCE_H
#include <linux/nvme.h>
#include <linux/dma-map-ops.h>
#include "n71_s3e_admin_once_core.h"
#include "n71_s3e_queue_retire_gate.h"
#include "n71_s3e_post_reset_protocol.h"
/* Included after the storage/HMB guard definitions in the owning pilot. */
#include "n71_s3e_admin_protocol_accounting.h"
#include "n71_s3e_admin_cqe_validate.h"
#include "n71_s3e_late_dma_observer.h"
/* Pure queue/Read encoders; live paths require separate explicit opt-ins. */
#include "n71_s3e_read_only_io_plan.h"
/* Pure four-stream L2 staging, used by explicit owned queue preparation. */
#include "n71_s3e_ro_io_dart_map.h"
#define N71_ADMIN_SQ_IOVA 0x80010000U
#define N71_ADMIN_CQ_IOVA 0x80011000U
#define N71_ADMIN_DATA_MARK 0x716964656e746966ULL
static struct {
    void *page[8]; /* SQ, CQ, data, SGL, then one L2 per DART stream */
    dma_addr_t dma[8];
    bool mapped[8],dart_mapped,prepared,regs_saved;
    bool submitted,completed,completion_validated,cq_head_doorbell_written;
    bool data_arrived,namespace_validated,intms_saved;
    unsigned int old_intms,stage;
    unsigned int cq_polls,data_polls;
    u64 nsze;
    unsigned int lba_bytes;
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
/* Pre-epoch I/O backing: only the explicit queue trial calls the allocator. */
#include "n71_s3e_ro_io_dma_alloc.h"
/* Original S8000 8 MiB tag stride: isolated TCB1/SGL CPU staging only. */
#include "n71_s3e_ro_flatdma_tag1_stage.h"
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
    /* The epoch begins BEFORE any BME-capable PCI command write. */
    if (enable) WRITE_ONCE(n71_admin_dma_epoch_latched, true);
    /* These are 16-bit command writes. Never touch W1C PCI status. */
    /* Additional READS only under the already opt-in observer.
     * Samples bracket the EXISTING root and endpoint BME writes without
     * changing their order, values, timing requirements, or guards.
     * Do not interpret an INTMS change as proof of DMA retirement. */
    if (ans_phase_trace_ro && !enable)
        pr_info("n71-s3e-p0: ADMIN_BME_INTMS_RO edge=before_root intms_bit0=%u perst_high=%u no_dma_release=YES\n",
            !!(n71_admin_reg(0x0c)&1),n71_storage_reset_level(ctx)==1);
    writew(value,(u8 __iomem *)m->cfg+4);
    if (ans_phase_trace_ro && !enable)
        pr_info("n71-s3e-p0: ADMIN_BME_INTMS_RO edge=after_root intms_bit0=%u perst_high=%u no_dma_release=YES\n",
            !!(n71_admin_reg(0x0c)&1),n71_storage_reset_level(ctx)==1);
    writew(value,(u8 __iomem *)m->endpoint+4);
    if (ans_phase_trace_ro && !enable)
        pr_info("n71-s3e-p0: ADMIN_BME_INTMS_RO edge=after_endpoint intms_bit0=%u perst_high=%u no_dma_release=YES\n",
            !!(n71_admin_reg(0x0c)&1),n71_storage_reset_level(ctx)==1);
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
#include "n71_s3e_io_queue_runtime.h"
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
    /* Initial command is Identify NS1/CNS0. Only the explicit queue trial
     * may subsequently submit Create CQ/SQ; no NVM command is issued. */
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
    /* Reject a malformed or foreign CQE before advancing the CQ head.
     * The controller can still DMA: no completion validation authorizes
     * unmapping CQ, SQ, HMB, DART or NVMMU backing. */
    /* A phase probe and the later copied CQE must agree. A changing
     * completion slot cannot be acknowledged as our single command. */
    if (status!=le16_to_cpu(cqe.status) ||
        !n71_s3e_admin_identify_cqe_valid(
            &(const struct n71_s3e_admin_cqe_fields){
                .status=le16_to_cpu(cqe.status),
                .command_id=le16_to_cpu(cqe.command_id),
                .sq_id=le16_to_cpu(cqe.sq_id),
                .sq_head=le16_to_cpu(cqe.sq_head)})) {
        pr_err("n71-s3e-p0: IDENTIFY_CQE_REJECTED no_cq_head_doorbell=YES quarantine=YES\n");
        return -EIO;
    }
    n71_admin_memory.completion_validated=true;
    n71_admin_write(0x1004,1);
    /* Software issued a doorbell; this is not a device acknowledgement. */
    n71_admin_memory.cq_head_doorbell_written=true;
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
    n71_admin_memory.namespace_validated=true;
    n71_admin_memory.nsze=nsze;
    n71_admin_memory.lba_bytes=1U<<lbads;
    pr_info("n71-s3e-p0: IDENTIFY_NAMESPACE_REAL nsid=1 nsze=%llu ncap=%llu nuse=%llu lba_bytes=%u capacity_bytes=%llu data_tail_arrived=1 data_wait_polls=%u personal_identifiers_redacted=YES no_block_IO=YES\n",
        nsze,ncap,nuse,1U<<lbads,nsze<<lbads,n71_admin_memory.data_polls);
    if (ans_io_queue_once) return n71_io_queue_create_once(ctx);
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
    /* Compile-time ABI guards for the future read-only I/O path.
     * These guards perform no command submission or queue-map mutation. */
    BUILD_BUG_ON(offsetof(struct nvme_rw_command, dptr)!=24);
    BUILD_BUG_ON(offsetof(struct nvme_rw_command, slba)!=40);
    BUILD_BUG_ON(offsetof(struct nvme_rw_command, length)!=48);
    BUILD_BUG_ON(offsetof(struct nvme_create_cq, prp1)!=24);
    BUILD_BUG_ON(offsetof(struct nvme_create_cq, cqid)!=40);
    BUILD_BUG_ON(offsetof(struct nvme_create_sq, sqid)!=40);
    BUILD_BUG_ON(offsetof(struct nvme_delete_queue, qid)!=40);
    BUILD_BUG_ON(nvme_admin_delete_sq!=0x00 || nvme_admin_delete_cq!=0x04);
    BUILD_BUG_ON(nvme_cmd_read!=0x02);
    BUILD_BUG_ON(offsetof(struct nvme_create_sq, cqid)!=46);
    BUILD_BUG_ON(N71_RO_HOST_FRAME_BYTES!=SZ_16K);
    BUILD_BUG_ON(N71_RO_DART_STREAMS!=4);
    BUILD_BUG_ON(((N71_ADMIN_SQ_IOVA >> 12)&511U)!=N71_RO_DART_ADMIN_SQ_INDEX);
    BUILD_BUG_ON(((N71_ADMIN_CQ_IOVA >> 12)&511U)!=N71_RO_DART_ADMIN_CQ_INDEX);
    BUILD_BUG_ON(((0x80012000U >> 12)&511U)!=N71_RO_DART_IO_SQ_INDEX);
    BUILD_BUG_ON(((0x80013000U >> 12)&511U)!=N71_RO_DART_IO_CQ_INDEX);
    BUILD_BUG_ON(N71_RO_TCB_COUNT * N71_RO_TCB_BYTES != SZ_16K);
    BUILD_BUG_ON(N71_RO_TCB_TAG1_OFFSET != 128U);
    BUILD_BUG_ON(N71_RO_READ_FLATDMA_TAG_CANDIDATE != 0x40800000ULL);
    BUILD_BUG_ON(N71_RO_IO_DMA_PAGES != 4U);
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
    if (ans_io_queue_once) {
        rc=n71_io_queue_prepare(ctx);
        if (rc) return rc;
    }
    pr_info("n71-s3e-p0: ADMIN_PREPARED queue_depth=16 controller_page_bytes=4096 host_page_bytes=%lu opcode=6 nsid=1 cns=0 FlatDMA_tag=0 only_owned_memory=YES\n",PAGE_SIZE);
    return 0;
}
static int n71_admin_unprepare(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i;
    /* Shutdown and BME-off alone cannot retire DMA-owned memory. */
    if (!n71_dma_retire_authorized(&(struct n71_dma_retirement_boundary){
            .admin_epoch_started=ans_identify_once || READ_ONCE(n71_admin_dma_epoch_latched),
            .controller_shutdown_consistent=0,
            .independent_quiescence_proven=0})) {
        pr_err("n71-s3e-p0: DMA_RETIREMENT_BOUNDARY stage=UNPREPARE release=DENIED\n");
        return -3;
    }
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
    /* Protocol-consistent reset is NOT independent DMA quiescence.
     * The old queue register write pilot is held behind an explicit
     * retirement refusal after any admin/BME epoch, even if every prior
     * read-only queue predicate passed. */
    if (!n71_dma_retire_authorized(&(struct n71_dma_retirement_boundary){
            .admin_epoch_started=ans_identify_once || READ_ONCE(n71_admin_dma_epoch_latched),
            .controller_shutdown_consistent=1,
            .independent_quiescence_proven=0})) {
        pr_err("n71-s3e-p0: ADMIN_QUEUE_RETIRE_PROBE refused=1 dma_epoch_no_proof=YES queue_regs_untouched=YES\n");
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
/* Opt-in POST-STOP RAM observer. The owned DMA pages and DART roots
 * remain pinned; no new NVMe/PCIe/DART/NVMMU MMIO commands are issued.
 * A changed hash is a late-write *suspect*, not attribution to the device.
 * Stable hashes are NEVER a proof of DMA retirement or absence of TLPs.
 */
static void n71_admin_late_dma_probe_ro(const struct n71_admin_once_result *r)
{
    struct n71_s3e_late_dma_observer obs={};
    struct device *d=n71_nvmmu_memory.dev;
    unsigned int i;
    bool qualified;
    if (!ans_late_dma_probe_ro) return;
    qualified=r && d && ans_identify_once &&
        READ_ONCE(n71_admin_dma_epoch_latched) &&
        n71_admin_memory.prepared && n71_admin_memory.dart_mapped &&
        n71_admin_memory.submitted && n71_admin_memory.completed &&
        n71_admin_memory.completion_validated &&
        n71_admin_memory.data_arrived && n71_admin_memory.namespace_validated &&
        n71_admin_memory.mapped[1] && n71_admin_memory.mapped[2] &&
        n71_admin_memory.page[1] && n71_admin_memory.page[2] &&
        r->inner_rc==0 && r->shutdown_attempted &&
        r->shutdown_rc==0 && r->shutdown_csts==9 &&
        r->disable_rc==0 && r->disable_csts==0 && r->master_off;
    if (!qualified) {
        pr_err("n71-s3e-p0: ADMIN_LATE_DMA_PROBE_RO refused=1 incomplete_poststop_gate=YES quarantine_unchanged=YES\n");
        return;
    }
    for (i=0;i<12;i++) {
        unsigned long long cq_hash,data_hash;
        /* Matches the preexisting DMA_BIDIRECTIONAL cache ownership path.
         * The device may still have the ability to write either page. */
        dma_sync_single_for_cpu(d,n71_admin_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_sync_single_for_cpu(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
        /* A host page is 16 KiB while the controller queue is 4 KiB.
         * Include the full allocated backing page to detect suspicious
         * writes beyond the expected queue/payload window as well. */
        cq_hash=n71_s3e_late_dma_fingerprint(n71_admin_memory.page[1],PAGE_SIZE);
        data_hash=n71_s3e_late_dma_fingerprint(n71_admin_memory.page[2],PAGE_SIZE);
        dma_sync_single_for_device(d,n71_admin_memory.dma[1],PAGE_SIZE,DMA_BIDIRECTIONAL);
        dma_sync_single_for_device(d,n71_admin_memory.dma[2],PAGE_SIZE,DMA_BIDIRECTIONAL);
        n71_s3e_late_dma_observe(&obs,cq_hash,data_hash);
        if (i+1<12) msleep(50);
    }
    pr_info("n71-s3e-p0: ADMIN_LATE_DMA_PROBE_RO samples=%u interval_ms=50 observed_page_bytes=%lu cq_changes=%u data_changes=%u cq_transitions=%u data_transitions=%u first_cq_deviation_sample=%u first_data_deviation_sample=%u any_change=%u suspected_late_ram_change=%u stable_is_not_proof=YES release_allowed=NO quarantine_unchanged=YES\n",
        obs.samples,PAGE_SIZE,obs.cq_changed,obs.data_changed,
        obs.cq_transitions,obs.data_transitions,
        obs.first_cq_deviation_sample,obs.first_data_deviation_sample,
        obs.ever_changed,obs.ever_changed);
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
        if (n71_series_enabled()) n71_read_series_observe_retained_ro(ctx);
        n71_admin_late_dma_probe_ro(&r);
        /* Read existing software lifecycle fields; no extra MMIO reads. */
        {
            const struct n71_s3e_admin_protocol_snapshot snap={
                .submitted=n71_admin_memory.submitted,
                .completion_observed=n71_admin_memory.completed,
                .completion_validated=n71_admin_memory.completion_validated,
                .cq_head_doorbell_written=n71_admin_memory.cq_head_doorbell_written,
                .data_arrived=n71_admin_memory.data_arrived,
                .namespace_validated=n71_admin_memory.namespace_validated,
                .shutdown_attempted=r.shutdown_attempted,
                .shutdown_complete=!r.shutdown_rc && r.shutdown_csts==9,
                .controller_disabled=!r.disable_rc && !r.disable_csts,
                .master_off=r.master_off,
                .queues_retained=n71_admin_memory.prepared && n71_admin_memory.dart_mapped,
                .admin_epoch_latched=READ_ONCE(n71_admin_dma_epoch_latched)
            };
            const enum n71_s3e_admin_protocol_result state=
                n71_s3e_admin_protocol_classify(&snap);
            pr_info("n71-s3e-p0: ADMIN_PROTOCOL_ACCOUNTING_RO state=%u completed_valid=%u namespace_valid=%u queue_owned=%u dma_release_authorized=NO\n",
                state,snap.completion_validated,snap.namespace_validated,
                snap.queues_retained);
        }
        pr_info("n71-s3e-p0: ADMIN_IDENTIFY_ONCE rc=%d master_seen=%u controller_started=%u ready=%u submitted=%u completed=%u data_arrived=%u stopped=%u master_off=%u enable_polls=%u shutdown_polls=%u disable_polls=%u last_csts=%08x\n",
            rc,r.master_seen,r.started,r.ready,n71_admin_memory.submitted,
            n71_admin_memory.completed,n71_admin_memory.data_arrived,r.stopped,
            r.master_off,r.enable_polls,r.shutdown_polls,r.disable_polls,r.last_csts);
        pr_info("n71-s3e-p0: ADMIN_SHUTDOWN_TRACE attempted=%u rc=%d csts=%08x polls=%u disable_rc=%d disable_csts=%08x inner_rc=%d master_off=%u retained_on_uncertainty=YES\n",
            r.shutdown_attempted,r.shutdown_rc,r.shutdown_csts,r.shutdown_polls,
            r.disable_rc,r.disable_csts,r.inner_rc,r.master_off);
        /* Telemetry only: independently report observed controller stop
         * even when the pre-start HMB descriptor check must fail after
         * shutdown. Neither state proves DMA retirement. */
        pr_info("n71-s3e-p0: ADMIN_CONTROLLER_STOP_RO controller_stop_observed=%u post_disable_qualified=%u legacy_stopped=%u identify_inner_ok=%u dma_quiescence_proven=NO dma_release_authorized=NO\n",
            r.controller_stop_observed,r.post_disable_qualified,r.stopped,
            r.inner_rc==0 && n71_admin_memory.completed &&
            n71_admin_memory.completion_validated &&
            n71_admin_memory.namespace_validated);
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
                if (ans_phase_trace_ro) {
                    const struct n71_post_reset_protocol_observation p={
                        .shutdown_attempted=r.shutdown_attempted,
                        .shutdown_rc=r.shutdown_rc,
                        .shutdown_csts=r.shutdown_csts,
                        .disable_rc=r.disable_rc,
                        .disable_csts=r.disable_csts,
                        .master_off=r.master_off,
                        .cc=n71_admin_reg(0x14),
                        .csts=n71_admin_reg(0x1c),
                        .root_command=n71_storage_root_read(ctx,4)&0xffffU,
                        .endpoint_command=n71_storage_endpoint_read(ctx,4)&0xffffU,
                        .intms=n71_admin_reg(0x0c),
                        .perst_high=n71_storage_reset_level(ctx)==1,
                        .hmb_descriptor_zero=ready && !hmb_lo && !hmb_hi && !hmb_size,
                        .queues_owned=queues_owned,
                        .prepared=n71_admin_memory.prepared,
                        .dart_mapped=n71_admin_memory.dart_mapped,
                        .hmb_owned=owned,
                    };
                    /* Read-only protocol interpretation, NOT a DMA or
                     * queue-retirement decision. Keep existing -3 path. */
                    pr_info("n71-s3e-p0: ADMIN_POST_RESET_PROTOCOL_RO consistent=%u queue_write_authorized=NO DMA_QUARANTINE=YES\n",
                        n71_post_reset_protocol_consistent(&p));
                }
                pr_info("n71-s3e-p0: ADMIN_POST_STOP_DMA_SNAPSHOT hmb_descriptor_zero=%u queues_zero=%u queues_owned_io_va=%u dart_queues_mapped=%u dart_fault=%08x nvmmu_fifo=%08x no_dma_release_attempted=YES quarantine_unchanged=YES\n",
                    ready && !hmb_lo && !hmb_hi && !hmb_size,
                    queues_zero,queues_owned,n71_admin_memory.dart_mapped,
                    dart_fault,nvmmu_fifo);
                /* Original AppleS5L8960XDART N71 source confirms the
                 * status register at 0x10 and bit31 as the fault-context
                 * branch predicate. Do not read 0x14/0x18/0x1c just because
                 * other status bits are set (e.g. the observed 0x500).
                 * Require opt-in, completed controller shutdown, BME-off
                 * and owned DART mapping. Never log raw context, or treat
                 * any register state as independent DMA quiescence. */
                if (ans_phase_trace_ro && r.controller_stop_observed &&
                    n71_admin_memory.dart_mapped &&
                    (dart_fault & BIT(31))) {
                    u32 axi0=readl((u8 __iomem *)m->dart+0x14);
                    u32 axi1=readl((u8 __iomem *)m->dart+0x18);
                    u32 fault_address=readl((u8 __iomem *)m->dart+0x1c);
                    pr_info("n71-s3e-p0: ADMIN_DART0_FAULT_CONTEXT_RO status_bit31=1 status_bit8=%u status_bit10=%u axi0_nonzero=%u axi1_nonzero=%u addr_nonzero=%u original_s8000_offsets_verified=YES context_semantics_unverified=YES fault_not_dma_fence=YES raw_context_redacted=YES quarantine_unchanged=YES\n",
                        !!(dart_fault & BIT(8)),
                        !!(dart_fault & BIT(10)),!!axi0,!!axi1,
                        !!fault_address);
                }
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
    if (ans_io_queue_once && n71_ro_io_dma_memory.ready) {
        n71_ro_io_dma_memory.quarantined=true;
        n71_unreleased=true;
        pr_info("n71-s3e-p0: IO_QUEUE_BACKING_QUARANTINED io_pages=4 all_admin_hmb_dart_nvmmu_retained=YES release_authorized=NO\n");
        return -3;
    }
    if (rc==-3) return -3;
    if (n71_admin_unprepare(ctx)) return -3;
    return rc;
}
#endif
