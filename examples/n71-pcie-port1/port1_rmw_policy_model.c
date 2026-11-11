/* SPDX-License-Identifier: MIT */
/*
 * Offline-only A9/S8000 PCIe port-1 register RMW POLICY MODEL.
 * Standalone portable C, compiled and executed only with synthetic data.
 *
 * Four bit transitions match original N71 S800x ROOT method patterns
 * statically verified in a separate private-kernelcache audit.
 * The source contains NO hardware MMIO mapping, PCIe probe, clock,
 * reset, GPIO, interrupt, DART or DMA operations.
 *
 * Values/offsets refer to the root controller's virtual mapping for
 * provider resource index 9; original runtime physical provider resource
 * ordering is NOT established. This is NOT a device driver.
 */
#include <stdint.h>
#include <errno.h>

#define N71_PORT1_INDEX 1U
#define N71_PORT1_ID2_OFFSET 0x180U
#define N71_PORT1_ID3_OFFSET 0x194U
#define N71_PORT1_ID4_OFFSET 0x1A4U
#define N71_SHARED_ID1_OFFSET 0x02CU

#define N71_OP_CONTROL_ID4 1968U
#define N71_OP_CONTROL_ID3 1984U
#define N71_OP_CONTROL_ID2_BIT8 1992U
#define N71_OP_CONTROL_ID2_BIT20 2000U

struct n71_synthetic_write {
    uint32_t register_relative_offset;
    uint32_t permitted_bit_mask;
    uint32_t new_value;
};

int n71_port1_calculate_synthetic_rmw(
    uint32_t port, uint32_t original_virtual_slot,
    uint32_t boolean_value, uint32_t previous_value,
    struct n71_synthetic_write *out)
{
    uint32_t mask = 0U;
    uint32_t offset = 0U;
    uint32_t wanted = 0U;

    if (!out || port != N71_PORT1_INDEX ||
        boolean_value > 1U)
        return -EINVAL;

    out->register_relative_offset = 0U;
    out->permitted_bit_mask = 0U;
    out->new_value = 0U;

    switch (original_virtual_slot) {
    case N71_OP_CONTROL_ID4:
        offset = N71_PORT1_ID4_OFFSET;
        mask = 1U;
        /* Original slot1968 inverts the boolean when storing bit0. */
        wanted = boolean_value ^ 1U;
        break;
    case N71_OP_CONTROL_ID3:
        offset = N71_PORT1_ID3_OFFSET;
        mask = 1U;
        wanted = boolean_value;
        break;
    case N71_OP_CONTROL_ID2_BIT8:
        offset = N71_PORT1_ID2_OFFSET;
        mask = (1U << 8);
        wanted = boolean_value << 8;
        break;
    case N71_OP_CONTROL_ID2_BIT20:
        offset = N71_PORT1_ID2_OFFSET;
        mask = (1U << 20);
        wanted = boolean_value << 20;
        break;
    default:
        return -EOPNOTSUPP;
    }

    out->register_relative_offset = offset;
    out->permitted_bit_mask = mask;
    out->new_value = (previous_value & ~mask) | wanted;
    return 0;
}

/* The shared ID1 bit4 status is READ-ONLY in this policy model. */
int n71_port1_is_allowed_synthetic_register_write(uint32_t port,
                                                    uint32_t offset,
                                                    uint32_t mask)
{
    if (port != N71_PORT1_INDEX)
        return 0;

    if (offset == N71_PORT1_ID2_OFFSET)
        return mask == (1U << 8) || mask == (1U << 20);

    if (offset == N71_PORT1_ID3_OFFSET ||
        offset == N71_PORT1_ID4_OFFSET)
        return mask == 1U;

    /* Explicitly includes denial of shared ID1 offset 0x2C. */
    return 0;
}
