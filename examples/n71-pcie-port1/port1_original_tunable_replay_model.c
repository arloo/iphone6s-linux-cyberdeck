/* SPDX-License-Identifier: MIT */
/*
 * N71/S8000 Apple original PCIe tunable REPLAY MODEL - NO HARDWARE.
 *
 * This is a userspace/offline pure function (also cross-compiled as an
 * unlinked ARM64 object). It consumes value records from private authorized
 * Apple iOS sources, and simulates Apple's verified 32-bit RMW formula:
 *
 *       simulated_after = (synthetic_before & ~mask) | (value & mask)
 *
 * Synthetic values come only from a deterministic local pseudo-state
 * generated from offset + caller seed. There is no MMIO pointer, callback,
 * syscall, PCIe config, Linux platform driver, ioremap, DART or radio path.
 *
 * Explicitly not safe to link as an active PCIe driver or use as a
 * hardware initialization script. It cannot validate live electrical
 * register semantics, port1 state, clock/PHY/RESET/MSI or DMA isolation.
 */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#define N71_SYNTHETIC_MAX_RECORDS 83U
#define N71_SHARED_STATUS_OFFSET  0x2cU

enum n71_bank {
    N71_BANK_ROOT_COMMON = 0,
    N71_BANK_ROOT_PHY = 1,
    N71_BANK_PORT1_CONFIG = 2,
    N71_BANK_PORT1_RC = 3
};

struct n71_original_tunable {
    uint32_t offset;
    uint32_t width;
    uint64_t mask;
    uint64_t value;
};

struct n71_replay_result {
    uint32_t examined;
    uint32_t synthetic_changes;
    uint32_t synthetic_unchanged;
    uint32_t protected_status_offset_reached;
    uint32_t physical_hardware_authorized;
};

/* Not an address or live device value. All pseudo-register state is
 * generated from caller-supplied synthetic seed, offset and bank.
 */
static uint32_t n71_fake_register(uint32_t bank, uint32_t offset,
                                 uint32_t seed)
{
    uint32_t x = seed ^ offset ^ (bank * UINT32_C(0x9e3779b9));
    x ^= x >> 16;
    x *= UINT32_C(0x7feb352d);
    x ^= x >> 15;
    x *= UINT32_C(0x846ca68b);
    x ^= x >> 16;
    return x;
}

static int n71_bank_info(unsigned int bank, size_t *expected,
                         uint32_t *span)
{
    if (!expected || !span)
        return -EINVAL;
    switch (bank) {
    case N71_BANK_ROOT_COMMON:
        *expected = 34;
        *span = 0x8000;
        return 0;
    case N71_BANK_ROOT_PHY:
        *expected = 41;
        *span = 0x4000;
        return 0;
    case N71_BANK_PORT1_CONFIG:
        *expected = 6;
        *span = 0x4000;
        return 0;
    case N71_BANK_PORT1_RC:
        *expected = 2;
        *span = 0x4000;
        return 0;
    default:
        return -EINVAL;
    }
}

/* Transactional output: an INVALID record never yields partial success.
 * The supplied records are const data. This function can modify ONLY the
 * in-memory result struct; it has no reference to any memory region.
 */
int n71_s8000_replay_original_tunables(
    unsigned int bank,
    const struct n71_original_tunable *records,
    size_t count,
    uint32_t synthetic_seed,
    struct n71_replay_result *result)
{
    size_t expected;
    uint32_t span;
    uint32_t changed = 0, unchanged = 0;
    size_t i, j;
    int rc;

    if (!result)
        return -EINVAL;

    result->examined = 0;
    result->synthetic_changes = 0;
    result->synthetic_unchanged = 0;
    result->protected_status_offset_reached = 0;
    result->physical_hardware_authorized = 0;

    rc = n71_bank_info(bank, &expected, &span);
    if (rc)
        return rc;
    if (!records || count != expected ||
        count == 0 || count > N71_SYNTHETIC_MAX_RECORDS)
        return -EINVAL;

    /* Entire-array verification BEFORE simulation. Every bank is
     * logically isolated; a real controller's shared resource effects
     * are intentionally NOT represented or implicitly authorized.
     */
    for (i = 0; i < count; i++) {
        const struct n71_original_tunable *r = &records[i];

        if (r->width != 4 || (r->offset & 3) != 0 ||
            r->offset > span - 4 ||
            r->mask > UINT32_MAX || r->value > UINT32_MAX ||
            (r->value & ~r->mask) != 0)
            return -ERANGE;

        if (bank == N71_BANK_ROOT_COMMON &&
            r->offset == N71_SHARED_STATUS_OFFSET)
            return -EPERM;

        for (j = 0; j < i; ++j)
            if (records[j].offset == r->offset)
                return -EEXIST; /* Proven real groups contain no duplicates. */
    }

    for (i = 0; i < count; i++) {
        const struct n71_original_tunable *r = &records[i];
        const uint32_t before =
            n71_fake_register(bank, r->offset, synthetic_seed);
        const uint32_t mask = (uint32_t)r->mask;
        const uint32_t value = (uint32_t)r->value;
        const uint32_t after = (before & ~mask) | (value & mask);

        /* This is a software formula invariant, NOT physical proof. */
        if ((before & ~mask) != (after & ~mask) ||
            (after & mask) != (value & mask))
            return -EIO;

        if (after == before)
            ++unchanged;
        else
            ++changed;
    }

    result->examined = (uint32_t)count;
    result->synthetic_changes = changed;
    result->synthetic_unchanged = unchanged;
    return 0;
}

/* Explicitly always deny real physical access, regardless of replay. */
int n71_s8000_replay_authorizes_pcie_mmio_or_dma(void)
{
    return 0;
}
