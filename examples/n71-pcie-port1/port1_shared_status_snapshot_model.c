/* SPDX-License-Identifier: MIT */
/*
 * N71/S8000 port1 shared ID1 bit4 status: OFFLINE SNAPSHOT MODEL.
 *
 * Accepts only caller-supplied synthetic 32-bit values in memory.
 * Never maps, reads or writes an actual hardware register. The
 * reconstructed original Apple S800x ROOT slot1984 polls bit4 of ID1
 * at offset 0x2C, via common IODeviceMemory provider index 9.
 *
 * Independently observed original iOS 15.7.9 IORegistry establishes
 * provider index9 = 0x600000000 length0x8000 on this N71/S8000.
 * Neither bit4 nor the callback has independently established
 * electrical power-good, PCIe LTSSM link-up, or safe DMA semantics.
 *
 * This model's success code means BIT4 OBSERVED IN PROVIDED DATA,
 * never "PCIe ready" and NEVER permission to touch physical hardware.
 */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#define N71_PORT1_INDEX                  1U
#define N71_COMMON_RESOURCE_INDEX        9U
#define N71_SHARED_ID1_OFFSET            0x2cU
#define N71_SHARED_ID1_BIT               4U
#define N71_SHARED_BASE                  UINT64_C(0x600000000)
#define N71_SHARED_LENGTH                UINT64_C(0x8000)
#define N71_MAX_SYNTHETIC_SNAPSHOTS      4096U

struct n71_s8000_common_resource {
    uint32_t port;
    uint32_t provider_index;
    uint32_t offset;
    uint64_t base;
    uint64_t length;
};

struct n71_s8000_snapshot_result {
    uint32_t examined;
    uint32_t last_value;
    uint32_t bit4_observed;
};

/* Does not expose an MMIO or callback API: strictly immutable inputs. */
int n71_port1_check_shared_snapshots(
    const struct n71_s8000_common_resource *resource,
    const uint32_t *snapshots,
    size_t snapshot_count,
    struct n71_s8000_snapshot_result *result)
{
    size_t i;

    if (!result)
        return -EINVAL;
    result->examined = 0;
    result->last_value = 0;
    result->bit4_observed = 0;

    if (!resource || !snapshots ||
        resource->port != N71_PORT1_INDEX ||
        resource->provider_index != N71_COMMON_RESOURCE_INDEX ||
        resource->base != N71_SHARED_BASE ||
        resource->length != N71_SHARED_LENGTH ||
        resource->offset != N71_SHARED_ID1_OFFSET ||
        snapshot_count == 0 ||
        snapshot_count > N71_MAX_SYNTHETIC_SNAPSHOTS)
        return -EINVAL;

    for (i = 0; i < snapshot_count; ++i) {
        const uint32_t value = snapshots[i];

        result->examined = (uint32_t)(i + 1);
        result->last_value = value;

        /* Original method checks bit4 specifically, NOT nonzero. */
        if ((value & (UINT32_C(1) << N71_SHARED_ID1_BIT)) != 0U) {
            result->bit4_observed = 1U;
            return 0;
        }
    }
    return -ETIMEDOUT;
}

/* A status sample cannot establish an electrically verified PCIe link. */
int n71_port1_shared_snapshot_authorizes_hardware(void)
{
    return 0;
}
