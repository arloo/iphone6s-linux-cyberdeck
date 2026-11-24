/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_READ_ONLY_IO_PLAN_H
#define N71_S3E_READ_ONLY_IO_PLAN_H
/*
 * N71/S8000 one-sector, read-only NVMe wire command candidates.
 *
 * This is a pure 64-byte command encoder, not a DMA/IO queue driver.
 * It MUST NOT be invoked by a live controller without separately verified
 * I/O SQ/CQ DART mappings, NVMMU payload mapping, vendor-specific flags,
 * authenticated controller state, and DMA lifetime ownership.
 *
 * The NVM READ opcode 0x02 belongs on I/O QID 1; CREATE CQ 0x05 and
 * CREATE SQ 0x01 belong on the ADMIN queue only. Never conflate the
 * latter admin opcode 0x01 with the destructive NVM WRITE opcode 0x01.
 *
 * All encoders leave the caller's output bytes untouched on failure.
 * Intentional use of portable byte stores avoids assumptions about host
 * endianness. No pointers, MMIO, data, addresses or secrets are logged.
 */
#define N71_RO_CMD_BYTES 64U
#define N71_RO_NSID 1U
#define N71_RO_QID 1U
#define N71_RO_Q_ENTRIES 16U
#define N71_RO_BLOCK_BYTES 4096U
#define N71_RO_PHYSICAL_NSZE 15625000ULL
#define N71_RO_DMA_ADDRESS_LIMIT (1ULL << 36)
#define N71_RO_NVM_READ 0x02U
#define N71_RO_ADMIN_CREATE_CQ 0x05U
#define N71_RO_ADMIN_CREATE_SQ 0x01U
#define N71_RO_IO_FLAG_UNQUALIFIED 0U
/* Authenticated against the owner's original S8000 NVMMU code:
 * read tag index << 23, then bitwise-OR with the ADT virtual-base.
 * Thus 0x40001000 is still inside tag 0 (Identify), NOT a new tag.
 * Tag 1 starts at 0x40800000. This selects a distinct TCB index;
 * command flags and physical READ semantics remain unqualified. */
#define N71_RO_FLATDMA_VBASE 0x40000000ULL
#define N71_RO_FLATDMA_TAG_SHIFT 23U
#define N71_RO_FLATDMA_TAG_BYTES (1ULL << N71_RO_FLATDMA_TAG_SHIFT)
#define N71_RO_FLATDMA_TAG_COUNT 128U
#define N71_RO_READ_FLATDMA_TAG_INDEX 1U
#define N71_RO_READ_FLATDMA_TAG_CANDIDATE \
    (N71_RO_FLATDMA_VBASE | (N71_RO_READ_FLATDMA_TAG_INDEX << N71_RO_FLATDMA_TAG_SHIFT))

struct n71_s3e_ro_io_layout {
    unsigned long long admin_sq_iova;
    unsigned long long admin_cq_iova;
    unsigned long long io_sq_iova;
    unsigned long long io_cq_iova;
    unsigned long long data_iova;
};

static inline void n71_ro_le16(unsigned char *p, unsigned int n)
{
    p[0] = (unsigned char)n;
    p[1] = (unsigned char)(n >> 8);
}

static inline void n71_ro_le32(unsigned char *p, unsigned int n)
{
    p[0] = (unsigned char)n;
    p[1] = (unsigned char)(n >> 8);
    p[2] = (unsigned char)(n >> 16);
    p[3] = (unsigned char)(n >> 24);
}

static inline void n71_ro_le64(unsigned char *p, unsigned long long n)
{
    n71_ro_le32(p, (unsigned int)n);
    n71_ro_le32(p + 4, (unsigned int)(n >> 32));
}

/* Require an exact tag base, not any arbitrary offset inside tag 0.
 * Only tag 1 is reserved by this single-read staging prototype. */
static inline int n71_s3e_ro_valid_read_flatdma_tag(unsigned long long iova)
{
    unsigned long long index;
    if (iova < N71_RO_FLATDMA_VBASE ||
        iova >= N71_RO_FLATDMA_VBASE +
                N71_RO_FLATDMA_TAG_COUNT * N71_RO_FLATDMA_TAG_BYTES ||
        (iova - N71_RO_FLATDMA_VBASE) % N71_RO_FLATDMA_TAG_BYTES)
        return 0;
    index = (iova - N71_RO_FLATDMA_VBASE) >> N71_RO_FLATDMA_TAG_SHIFT;
    return index == N71_RO_READ_FLATDMA_TAG_INDEX;
}

static inline int n71_ro_valid_page(unsigned long long iova)
{
    return iova && !(iova & (N71_RO_BLOCK_BYTES - 1ULL)) &&
           iova <= N71_RO_DMA_ADDRESS_LIMIT - N71_RO_BLOCK_BYTES;
}

/* This verifies only *layout arithmetic*. It does not claim that DART or
 * NVMMU has a translation, nor that any queue/device has been enabled. */
static inline int n71_s3e_ro_validate_layout(
    const struct n71_s3e_ro_io_layout *layout)
{
    unsigned long long pages[5];
    unsigned int i, j;
    if (!layout) return -1;
    pages[0] = layout->admin_sq_iova;
    pages[1] = layout->admin_cq_iova;
    pages[2] = layout->io_sq_iova;
    pages[3] = layout->io_cq_iova;
    pages[4] = layout->data_iova;
    for (i = 0; i < 5; i++) {
        if (!n71_ro_valid_page(pages[i])) return -1;
        for (j = 0; j < i; j++)
            if (pages[i] == pages[j]) return -1;
    }
    return 0;
}

/* Queue commands are purely speculative until the original S8000 vendor
 * flags, queue ownership and ABI are independently verified. They MUST
 * remain unsubmitted by the default Identify path. The separate explicit
 * queue-only trial may select a flags hypothesis for these ADMIN commands.
 * 16 entries, QID 1,
 * contiguous buffer, completion interrupts disabled (polling only). */
static inline int n71_s3e_ro_encode_create_cq(
    unsigned char *out, const struct n71_s3e_ro_io_layout *layout)
{
    unsigned char tmp[N71_RO_CMD_BYTES] = {0};
    unsigned int i;
    if (!out || n71_s3e_ro_validate_layout(layout)) return -1;
    tmp[0] = N71_RO_ADMIN_CREATE_CQ;
    n71_ro_le16(tmp + 2, 2U); /* admin CID 2, Identify used CID 1 */
    n71_ro_le64(tmp + 24, layout->io_cq_iova);
    n71_ro_le16(tmp + 40, N71_RO_QID);
    n71_ro_le16(tmp + 42, N71_RO_Q_ENTRIES - 1U);
    n71_ro_le16(tmp + 44, 1U); /* physically contiguous, no IRQ */
    for (i = 0; i < N71_RO_CMD_BYTES; i++) out[i] = tmp[i];
    return 0;
}

static inline int n71_s3e_ro_encode_create_sq(
    unsigned char *out, const struct n71_s3e_ro_io_layout *layout)
{
    unsigned char tmp[N71_RO_CMD_BYTES] = {0};
    unsigned int i;
    if (!out || n71_s3e_ro_validate_layout(layout)) return -1;
    tmp[0] = N71_RO_ADMIN_CREATE_SQ; /* NOT an NVM write */
    n71_ro_le16(tmp + 2, 3U); /* admin CID 3, CQ must precede SQ */
    n71_ro_le64(tmp + 24, layout->io_sq_iova);
    n71_ro_le16(tmp + 40, N71_RO_QID);
    n71_ro_le16(tmp + 42, N71_RO_Q_ENTRIES - 1U);
    n71_ro_le16(tmp + 44, 1U); /* physically contiguous */
    n71_ro_le16(tmp + 46, N71_RO_QID); /* completion queue */
    for (i = 0; i < N71_RO_CMD_BYTES; i++) out[i] = tmp[i];
    return 0;
}

/* One 4 KiB sector, no metadata, no FUA, no fused commands, no writes.
 * Caller must validate NS geometry from the *current* real Identify
 * completion and ownership; flags are deliberately 0 until S8000 IO
 * interpretation is source-/hardware-qualified. No SQ doorbell here. */
static inline int n71_s3e_ro_encode_one_sector(
    unsigned char *out, const struct n71_s3e_ro_io_layout *layout,
    unsigned long long current_nsze, unsigned int current_lba_bytes,
    unsigned long long slba)
{
    unsigned char tmp[N71_RO_CMD_BYTES] = {0};
    unsigned int i;
    if (!out || n71_s3e_ro_validate_layout(layout) ||
        current_nsze != N71_RO_PHYSICAL_NSZE ||
        current_lba_bytes != N71_RO_BLOCK_BYTES ||
        slba >= current_nsze ||
        !n71_s3e_ro_valid_read_flatdma_tag(layout->data_iova)) return -1;
    tmp[0] = N71_RO_NVM_READ; /* exclusively I/O QID 1 */
    tmp[1] = N71_RO_IO_FLAG_UNQUALIFIED;
    n71_ro_le16(tmp + 2, 1U); /* first I/O CID on QID 1 */
    n71_ro_le32(tmp + 4, N71_RO_NSID);
    n71_ro_le64(tmp + 24, layout->data_iova);
    n71_ro_le64(tmp + 40, slba);
    n71_ro_le16(tmp + 48, 0U); /* zero-based NLB => exactly one sector */
    for (i = 0; i < N71_RO_CMD_BYTES; i++) out[i] = tmp[i];
    return 0;
}
#endif
