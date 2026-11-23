/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_IO_DART_MAP_H
#define N71_S3E_RO_IO_DART_MAP_H
/*
 * Inert, transactional DART0 L2 queue-map staging for N71/S8000.
 *
 * The real admin owner maps IOVA 0x80010000/0x80011000 to L2[16]/[17]
 * for each of four DART0 streams. For a future isolated I/O QID 1,
 * stage queue translations at 0x80012000/0x80013000 -> L2[18]/[19].
 * The data page is NOT mapped through these queue entries; ANS FlatDMA
 * needs its own original-S8000 NVMMU/TCB/SGL qualification.
 *
 * Pure memory writer: NO DART root updates, TLB flush, dma_map_single,
 * cache sync, MMIO, endpoint enable, BME, SQ doorbells or DMA retirement.
 * All four tables are validated BEFORE any staged CPU-memory mutation.
 * Never call on an active/device-owned L2 or interpret staged bytes as
 * a live translation. All five physical pages are Linux-owned 16-KiB
 * backing pages with separate physical identities and 36-bit reachability.
 */
#include "n71_s3e_read_only_io_plan.h"

#define N71_RO_DART_STREAMS 4U
#define N71_RO_DART_TABLE_BYTES 4096U
#define N71_RO_HOST_FRAME_BYTES 16384U
#define N71_RO_DART_LEAF_FLAGS 3ULL
#define N71_RO_DART_ADMIN_SQ_INDEX 16U
#define N71_RO_DART_ADMIN_CQ_INDEX 17U
#define N71_RO_DART_IO_SQ_INDEX 18U
#define N71_RO_DART_IO_CQ_INDEX 19U

struct n71_s3e_ro_owned_frames {
    unsigned long long admin_sq_pa;
    unsigned long long admin_cq_pa;
    unsigned long long io_sq_pa;
    unsigned long long io_cq_pa;
    unsigned long long read_data_pa;
};

struct n71_s3e_ro_foreign_range {
    unsigned long long pa;
    unsigned long long bytes;
};

static inline unsigned long long n71_ro_get_le64(const unsigned char *p)
{
    unsigned long long n = 0;
    unsigned int i;
    for (i = 0; i < 8; i++)
        n |= (unsigned long long)p[i] << (i * 8);
    return n;
}

static inline int n71_ro_valid_host_frame(unsigned long long pa)
{
    return pa && !(pa & (N71_RO_HOST_FRAME_BYTES - 1ULL)) &&
           pa <= N71_RO_DMA_ADDRESS_LIMIT - N71_RO_HOST_FRAME_BYTES;
}

static inline int n71_s3e_ro_verify_ownership(
    const struct n71_s3e_ro_owned_frames *frames,
    const struct n71_s3e_ro_foreign_range *foreign,
    unsigned int foreign_count)
{
    unsigned long long pages[5], limit = N71_RO_DMA_ADDRESS_LIMIT;
    unsigned int i, j;
    if (!frames || (foreign_count && !foreign) || foreign_count > 128U)
        return -1;
    pages[0] = frames->admin_sq_pa;
    pages[1] = frames->admin_cq_pa;
    pages[2] = frames->io_sq_pa;
    pages[3] = frames->io_cq_pa;
    pages[4] = frames->read_data_pa;
    for (i = 0; i < 5; i++) {
        if (!n71_ro_valid_host_frame(pages[i])) return -1;
        for (j = 0; j < i; j++)
            if (pages[i] == pages[j]) return -1;
        for (j = 0; j < foreign_count; j++) {
            unsigned long long pa = foreign[j].pa;
            unsigned long long bytes = foreign[j].bytes;
            /* Unknown/overflowing ownership is NOT safe to overwrite. */
            if (!bytes || pa >= limit || bytes > limit - pa)
                return -1;
            if (pages[i] < pa + bytes &&
                pa < pages[i] + N71_RO_HOST_FRAME_BYTES)
                return -1;
        }
    }
    return 0;
}

static inline int n71_s3e_ro_verify_queue_iova(
    const struct n71_s3e_ro_io_layout *layout)
{
    if (n71_s3e_ro_validate_layout(layout)) return -1;
    return layout->admin_sq_iova == 0x80010000ULL &&
           layout->admin_cq_iova == 0x80011000ULL &&
           layout->io_sq_iova == 0x80012000ULL &&
           layout->io_cq_iova == 0x80013000ULL &&
           /* Never alias the live admin Identify FlatDMA data tag. */
           layout->data_iova != 0x40000000ULL ? 0 : -1;
}

/* The caller owns FOUR isolated CPU 4-KiB table views, each backed by
 * a separate unmapped 16-KiB Linux page; memory is NOT device-visible.
 * The existing admin queue leaves must match the proven original state,
 * while both I/O queue leaves must be zero on EVERY stream. Check all
 * views and foreign physical ranges before touching any L2 bytes.
 */
static inline int n71_s3e_ro_stage_io_queue_l2(
    unsigned char *const table[N71_RO_DART_STREAMS],
    const struct n71_s3e_ro_io_layout *layout,
    const struct n71_s3e_ro_owned_frames *frames,
    const struct n71_s3e_ro_foreign_range *foreign,
    unsigned int foreign_count)
{
    unsigned int sid, previous;
    if (!table || n71_s3e_ro_verify_queue_iova(layout) ||
        n71_s3e_ro_verify_ownership(frames, foreign, foreign_count))
        return -1;
    for (sid = 0; sid < N71_RO_DART_STREAMS; sid++) {
        unsigned char *l2 = table[sid];
        if (!l2) return -1;
        for (previous = 0; previous < sid; previous++) {
            unsigned long a = (unsigned long)l2;
            unsigned long b = (unsigned long)table[previous];
            if (a == b || (a > b && a - b < N71_RO_DART_TABLE_BYTES) ||
                (b > a && b - a < N71_RO_DART_TABLE_BYTES))
                return -1;
        }
        if (n71_ro_get_le64(l2 + 8U * N71_RO_DART_ADMIN_SQ_INDEX) !=
                (frames->admin_sq_pa | N71_RO_DART_LEAF_FLAGS) ||
            n71_ro_get_le64(l2 + 8U * N71_RO_DART_ADMIN_CQ_INDEX) !=
                (frames->admin_cq_pa | N71_RO_DART_LEAF_FLAGS) ||
            n71_ro_get_le64(l2 + 8U * N71_RO_DART_IO_SQ_INDEX) ||
            n71_ro_get_le64(l2 + 8U * N71_RO_DART_IO_CQ_INDEX))
            return -1;
    }
    /* No failure remains after validation; commit all four in RAM. */
    for (sid = 0; sid < N71_RO_DART_STREAMS; sid++) {
        n71_ro_le64(table[sid] + 8U * N71_RO_DART_IO_SQ_INDEX,
                    frames->io_sq_pa | N71_RO_DART_LEAF_FLAGS);
        n71_ro_le64(table[sid] + 8U * N71_RO_DART_IO_CQ_INDEX,
                    frames->io_cq_pa | N71_RO_DART_LEAF_FLAGS);
    }
    return 0;
}
#endif
