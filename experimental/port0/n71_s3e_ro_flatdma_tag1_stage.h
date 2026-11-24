/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_FLATDMA_TAG1_STAGE_H
#define N71_S3E_RO_FLATDMA_TAG1_STAGE_H
/*
 * Inert host-memory staging of a SECOND TCB + isolated SGL for N71/S8000.
 *
 * The original AppleS800xPCIe implementation creates 128-byte TCB slots
 * and returns (tag_index << 23) | NVMMU_virtual_base. The 16-KiB TCB
 * table holds 128 slots. Slot0 is occupied by our successful Identify.
 * Slot1 (offset128, IOVA0x40800000) is the next distinct candidate.
 *
 * The candidate transfer direction and TCB fields are patterned on the
 * successful one-page, device-to-host Identify. Their use for NVM READ
 * remains UNQUALIFIED against original IONVMeFamily I/O semantics.
 * This pure helper modifies only CPU-owned shadow views. The explicit
 * LBA0 trial separately validates/publishes them before BME, matching
 * the successful Identify descriptor as an experimental Read hypothesis.
 * This helper performs no cache sync, no register write or submission.
 * It performs no MMIO. Never run it
 * against a live/device-owned or inherited TCB table.
 */
#include "n71_s3e_ro_io_dart_map.h"

#define N71_RO_TCB_BYTES 128U
#define N71_RO_TCB_COUNT 128U
#define N71_RO_TCB_TAG1_OFFSET (N71_RO_TCB_BYTES * N71_RO_READ_FLATDMA_TAG_INDEX)
#define N71_RO_SGL_FIRST_ENTRY_BYTES 4U
#define N71_RO_ONE_PAGE_FROM_DEVICE_CANDIDATE 0x200U

static inline unsigned int n71_ro_get_le32(const unsigned char *p)
{
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8) |
           ((unsigned int)p[2] << 16) | ((unsigned int)p[3] << 24);
}

static inline int n71_s3e_ro_stage_flatdma_tag1(
    unsigned char *tcb_table_16k, unsigned char *sgl_page_16k,
    const struct n71_s3e_ro_owned_frames *frames,
    const struct n71_s3e_ro_io_layout *layout)
{
    unsigned char *slot;
    unsigned int i;
    unsigned long long a, b;
    if (!tcb_table_16k || !sgl_page_16k ||
        n71_s3e_ro_verify_queue_iova(layout) ||
        n71_s3e_ro_verify_ownership(frames, (void *)0, 0) ||
        N71_RO_TCB_COUNT != N71_RO_FLATDMA_TAG_COUNT ||
        N71_RO_TCB_COUNT * N71_RO_TCB_BYTES != N71_RO_HOST_FRAME_BYTES ||
        N71_RO_TCB_TAG1_OFFSET != 128U ||
        !n71_ro_valid_host_frame(frames->read_data_pa) ||
        !n71_ro_valid_host_frame(frames->read_sgl_pa))
        return -1;
    a = (unsigned long long)(unsigned long)tcb_table_16k;
    b = (unsigned long long)(unsigned long)sgl_page_16k;
    if ((a <= b && b - a < N71_RO_HOST_FRAME_BYTES) ||
        (b < a && a - b < N71_RO_HOST_FRAME_BYTES))
        return -1;

    /* Confirm the existing known-good admin transfer still owns tag0. */
    if (n71_ro_get_le32(tcb_table_16k) !=
            N71_RO_ONE_PAGE_FROM_DEVICE_CANDIDATE ||
        n71_ro_get_le32(tcb_table_16k + 4U) != 1U ||
        !n71_ro_get_le32(tcb_table_16k + 8U) ||
        !n71_ro_get_le64(tcb_table_16k + 16U))
        return -1;

    slot = tcb_table_16k + N71_RO_TCB_TAG1_OFFSET;
    for (i = 0; i < N71_RO_TCB_BYTES; i++)
        if (slot[i]) return -1; /* inherited or already active tag */
    for (i = 0; i < N71_RO_HOST_FRAME_BYTES; i++)
        if (sgl_page_16k[i]) return -1; /* never reuse a dirty SGL */

    /* This CPU-only candidate uses the previous successful Identify
     * descriptor fields; it is NOT validated for actual I/O READ. */
    n71_ro_le32(sgl_page_16k, (unsigned int)(frames->read_data_pa >> 12));
    n71_ro_le32(slot, N71_RO_ONE_PAGE_FROM_DEVICE_CANDIDATE);
    n71_ro_le32(slot + 8U, (unsigned int)(frames->read_data_pa >> 12));
    n71_ro_le64(slot + 16U, frames->read_sgl_pa);
    n71_ro_le32(slot + 4U, 1U); /* page-count last in CPU staging only */
    return 0;
}
#endif
