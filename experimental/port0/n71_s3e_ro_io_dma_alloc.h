/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_IO_DMA_ALLOC_H
#define N71_S3E_RO_IO_DMA_ALLOC_H
/*
 * Real Linux DMA API resource ownership for future N71/S8000 read-only
 * I/O SQ, CQ and one 4-KiB data sector, each in a 16-KiB Linux page.
 *
 * This module-local allocator is intentionally WITHOUT A CALL SITE.
 * It cannot establish NVMMU FlatDMA semantics, DART ownership, I/O queue
 * protocol acceptance, DMA drain, or authorization to read the NAND.
 *
 * The existing DMA epoch latch is monotonic: after the first possible
 * bus-master enable, NO unmap/free operation can be authorized here.
 * Partially acquired pages are released only while the epoch has never
 * started. Any ambiguous post-epoch path retains pages and pins the
 * original storage owner. All addresses stay out of kernel logs.
 */
#define N71_RO_IO_DMA_PAGES 3U
#define N71_RO_IO_FOREIGN_MAX 48U

static struct {
    void *page[N71_RO_IO_DMA_PAGES];
    dma_addr_t dma[N71_RO_IO_DMA_PAGES];
    bool mapped[N71_RO_IO_DMA_PAGES];
    bool ready, quarantined;
} n71_ro_io_dma_memory;

static int __maybe_unused n71_ro_io_dma_release_pre_epoch(void)
{
    unsigned int i;
    if (READ_ONCE(n71_admin_dma_epoch_latched)) {
        n71_ro_io_dma_memory.quarantined = true;
        n71_unreleased = true;
        return -EPERM;
    }
    if (n71_ro_io_dma_memory.quarantined)
        return -EPERM;
    for (i = 0; i < N71_RO_IO_DMA_PAGES; i++) {
        if (n71_ro_io_dma_memory.mapped[i]) {
            dma_unmap_single(n71_nvmmu_memory.dev,
                             n71_ro_io_dma_memory.dma[i],
                             PAGE_SIZE, DMA_BIDIRECTIONAL);
            n71_ro_io_dma_memory.mapped[i] = false;
        }
        if (n71_ro_io_dma_memory.page[i]) {
            free_page((unsigned long)n71_ro_io_dma_memory.page[i]);
            n71_ro_io_dma_memory.page[i] = NULL;
        }
        n71_ro_io_dma_memory.dma[i] = 0;
    }
    n71_ro_io_dma_memory.ready = false;
    return 0;
}

/* Caller must retain all 3 arrays/owned DART0 stream roots after BME.
 * A mismatch, even a non-overlapping but unknown inherited-owner range,
 * aborts BEFORE touching a new CPU page. */
static int n71_ro_io_dma_foreign_ranges(void *ctx,
        struct n71_s3e_ro_foreign_range *out,
        unsigned int *count)
{
    struct n71_storage_dart_context *m = ctx;
    unsigned int n = 0, i;
#define N71_RO_ADD_RANGE(address, length) do {                     \
    u64 _pa = (u64)(address), _len = (u64)(length);                 \
    if (_pa) {                                                     \
        if (n >= N71_RO_IO_FOREIGN_MAX) return -E2BIG;             \
        if (!_len || _pa >= N71_RO_DMA_ADDRESS_LIMIT ||           \
            _len > N71_RO_DMA_ADDRESS_LIMIT - _pa) return -EPERM; \
        out[n].pa = _pa; out[n].bytes = _len; n++;                  \
    }                                                             \
} while (0)
    if (!m || !out || !count) return -EINVAL;
    for (i = 0; i < 2; i++)
        N71_RO_ADD_RANGE(m->inherited_nvmmu_pa[i], i ? SZ_4K : SZ_16K);
    for (i = 0; i < 16; i++)
        N71_RO_ADD_RANGE(m->inherited_dart_pa[i], SZ_4K);
    if (n71_hmb_memory.inherited_pa)
        N71_RO_ADD_RANGE(n71_hmb_memory.inherited_pa,
                         n71_hmb_memory.inherited_size);
    if (n71_hmb_memory.mapped)
        N71_RO_ADD_RANGE(n71_hmb_memory.dma, SZ_8M);
    for (i = 0; i < 2; i++) {
        if (n71_nvmmu_memory.page[i] && !n71_nvmmu_memory.mapped[i])
            return -EPERM;
        if (n71_nvmmu_memory.mapped[i])
            N71_RO_ADD_RANGE(n71_nvmmu_memory.dma[i], PAGE_SIZE);
    }
    for (i = 0; i < 16; i++) {
        if (n71_tables.page[i] && !n71_tables.mapped[i])
            return -EPERM;
        if (n71_tables.mapped[i])
            N71_RO_ADD_RANGE(n71_tables.dma[i], PAGE_SIZE);
    }
    for (i = 0; i < 8; i++) {
        if (!n71_admin_memory.page[i] || !n71_admin_memory.mapped[i])
            return -EPERM;
        /* Admin SQ/CQ are the required first two OWNED frames in the
         * final five-frame plan, not foreign exclusion ranges. Their
         * collision with a prospective new page is checked separately
         * before zeroing, while admin data/SGL/4 L2 pages are foreign. */
        if (i >= 2)
            N71_RO_ADD_RANGE(n71_admin_memory.dma[i], PAGE_SIZE);
    }
#undef N71_RO_ADD_RANGE
    *count = n;
    return 0;
}

static int n71_ro_io_dma_claim_valid(unsigned long long pa,
        const struct n71_s3e_ro_foreign_range *foreign,
        unsigned int foreign_count, unsigned int new_count)
{
    unsigned int i;
    if (!n71_ro_valid_host_frame(pa)) return -EPERM;
    for (i = 0; i < 2; i++) {
        u64 admin_pa = (u64)n71_admin_memory.dma[i];
        if (!n71_admin_memory.mapped[i] ||
            (pa < admin_pa + PAGE_SIZE && admin_pa < pa + PAGE_SIZE))
            return -EBUSY;
    }
    for (i = 0; i < foreign_count; i++)
        if (pa < foreign[i].pa + foreign[i].bytes &&
            foreign[i].pa < pa + PAGE_SIZE)
            return -EBUSY;
    for (i = 0; i < new_count; i++) {
        u64 other = (u64)n71_ro_io_dma_memory.dma[i];
        if (!n71_ro_io_dma_memory.mapped[i]) return -EPERM;
        if (pa < other + PAGE_SIZE && other < pa + PAGE_SIZE)
            return -EBUSY;
    }
    return 0;
}

/* Deliberately not invoked from n71_admin_prepare or module init.
 * Precondition: the already-working eight admin pages are owned,
 * controller disabled, PCIe master off, and no historical DMA epoch.
 */
static int __maybe_unused n71_ro_io_dma_alloc_pre_epoch(void *ctx)
{
    struct n71_s3e_ro_foreign_range foreign[N71_RO_IO_FOREIGN_MAX];
    struct n71_s3e_ro_owned_frames frames;
    struct n71_s3e_ro_io_layout layout = {
        .admin_sq_iova = N71_ADMIN_SQ_IOVA,
        .admin_cq_iova = N71_ADMIN_CQ_IOVA,
        .io_sq_iova = 0x80012000ULL,
        .io_cq_iova = 0x80013000ULL,
        .data_iova = N71_RO_READ_FLATDMA_TAG_CANDIDATE,
    };
    unsigned int foreign_count, i;
    struct device *dev = n71_nvmmu_memory.dev;
    int rc;

    if (!ctx || !dev || PAGE_SIZE != SZ_16K ||
        READ_ONCE(n71_admin_dma_epoch_latched) ||
        n71_ro_io_dma_memory.ready ||
        n71_ro_io_dma_memory.quarantined ||
        n71_unreleased || dev_is_dma_coherent(dev))
        return -EPERM;
    for (i = 0; i < N71_RO_IO_DMA_PAGES; i++)
        if (n71_ro_io_dma_memory.page[i] ||
            n71_ro_io_dma_memory.mapped[i]) return -EPERM;
    if ((n71_storage_root_read(ctx, 4) & 0xffffU) != 2 ||
        (n71_storage_endpoint_read(ctx, 4) & 0xffffU) != 2 ||
        n71_admin_reg(0x14) || n71_admin_reg(0x1c) ||
        !n71_storage_hmb_owned_ready(ctx))
        return -EPERM;
    rc = n71_ro_io_dma_foreign_ranges(ctx, foreign, &foreign_count);
    if (rc) return rc;
    for (i = 0; i < N71_RO_IO_DMA_PAGES; i++) {
        u64 pa;
        n71_ro_io_dma_memory.page[i] =
            (void *)__get_free_page(GFP_KERNEL);
        if (!n71_ro_io_dma_memory.page[i]) {
            rc = -ENOMEM;
            goto fail;
        }
        pa = virt_to_phys(n71_ro_io_dma_memory.page[i]);
        rc = n71_ro_io_dma_claim_valid(pa, foreign, foreign_count, i);
        if (rc) goto fail; /* do not zero a foreign/aliased page */
        memset(n71_ro_io_dma_memory.page[i], 0, PAGE_SIZE);
        n71_ro_io_dma_memory.dma[i] = dma_map_single(dev,
            n71_ro_io_dma_memory.page[i], PAGE_SIZE, DMA_BIDIRECTIONAL);
        if (dma_mapping_error(dev, n71_ro_io_dma_memory.dma[i])) {
            rc = -EIO;
            goto fail;
        }
        n71_ro_io_dma_memory.mapped[i] = true;
        if ((u64)n71_ro_io_dma_memory.dma[i] != pa) {
            rc = -EPERM; /* reject non-identity mappings on N71 */
            goto fail;
        }
    }
    frames.admin_sq_pa = n71_admin_memory.dma[0];
    frames.admin_cq_pa = n71_admin_memory.dma[1];
    frames.io_sq_pa = n71_ro_io_dma_memory.dma[0];
    frames.io_cq_pa = n71_ro_io_dma_memory.dma[1];
    frames.read_data_pa = n71_ro_io_dma_memory.dma[2];
    if (n71_s3e_ro_verify_queue_iova(&layout) ||
        n71_s3e_ro_verify_ownership(&frames, foreign, foreign_count)) {
        rc = -EPERM;
        goto fail;
    }
    /* This prepares only DMA-mapped host frames, NOT an active DART L2,
     * NVMMU FlatDMA TCB, read command or IO SQ/CQ. */
    n71_ro_io_dma_memory.ready = true;
    return 0;
fail:
    if (n71_ro_io_dma_release_pre_epoch()) return -3;
    return rc;
}
#endif
