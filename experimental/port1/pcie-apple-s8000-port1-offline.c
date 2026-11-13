// SPDX-License-Identifier: GPL-2.0
/*
 * N71/S8000 PCIe port1 source-derived sequencing policy — OFFLINE / inert.
 *
 * Real original Apple N71 Mach-O + ADT and iOS IORegistry were independently
 * used to resolve root selector offsets and the port1 inherited call order.
 * This file is portable between a Linux Kbuild ARM64 object and an offline
 * native test harness. It performs NO MMIO and defines NO device driver.
 *
 * Do NOT use as a standalone PCIe host; global PCIe config index0, DART1
 * physical requester SID and root power/reset noninterference UNPROVEN.
 */
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/types.h>
#else
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#endif

enum n71_s8000_port1_step {
    N71_P1_ROOT_1968_ASSERT,
    N71_P1_ROOT_1984_START,
    N71_P1_ROOT_2008_STATUS, /* read only */
    N71_P1_ROOT_1992_CONTROL,
    N71_P1_ROOT_2000_OPTIONAL,
    N71_P1_ROOT_1968_RELEASE,
};

enum {
    N71_ROOT_PORT1_ID2 = 0x180, /* original root 2016: selector2+stride */
    N71_ROOT_PORT1_ID3 = 0x194, /* original root 2016: selector3+stride */
    N71_ROOT_PORT1_ID4 = 0x1a4, /* original root 2016: selector4+stride */
    N71_ROOT_PORT1_ID5 = 0x1ac, /* original root 2016: selector5+stride */
    N71_ROOT_GLOBAL_STATUS = 0x2c,
    N71_ROOT_POLL_INTERVAL_US = 10,
    N71_REFCLK_PERST_SOURCE_DELAY_US = 100,
    N71_P1_MAX_POLL_SAMPLES = 1000, /* 10 ms *POLICY*, not Apple proven */
};

struct n71_s8000_port1_rmw {
    unsigned int offset;
    unsigned int mask;
    unsigned int value;
    bool write;
};

/* Produce the precise root-relative source-derived masked RMW operation.
 * Returned value is DATA ONLY; never a request to perform physical MMIO.
 */
int n71_s8000_port1_plan_step(enum n71_s8000_port1_step step,
                              bool enable_optional,
                              struct n71_s8000_port1_rmw *out)
{
    struct n71_s8000_port1_rmw op = { 0 };

    if (!out)
        return -EINVAL;

    switch (step) {
    case N71_P1_ROOT_1968_ASSERT:
        op.offset = N71_ROOT_PORT1_ID4;
        op.mask = 1U;
        op.write = true;
        break;
    case N71_P1_ROOT_1984_START:
        op.offset = N71_ROOT_PORT1_ID3;
        op.mask = 1U;
        op.value = 1U;
        op.write = true;
        break;
    case N71_P1_ROOT_2008_STATUS:
        op.offset = N71_ROOT_PORT1_ID5;
        op.mask = 1U;
        op.write = false;
        break;
    case N71_P1_ROOT_1992_CONTROL:
        op.offset = N71_ROOT_PORT1_ID2;
        op.mask = 1U << 8;
        op.write = true;
        break;
    case N71_P1_ROOT_2000_OPTIONAL:
        if (!enable_optional)
            return -EOPNOTSUPP;
        op.offset = N71_ROOT_PORT1_ID2;
        op.mask = 1U << 20;
        op.value = 1U << 20;
        op.write = true;
        break;
    case N71_P1_ROOT_1968_RELEASE:
        op.offset = N71_ROOT_PORT1_ID4;
        op.mask = 1U;
        op.value = 1U;
        op.write = true;
        break;
    default:
        return -EINVAL;
    }
    *out = op;
    return 0;
}

/* Exact preserved-bit RMW for a SHADOW REGISTER VALUE, not hardware. */
int n71_s8000_port1_shadow_apply(unsigned int current,
                                 const struct n71_s8000_port1_rmw *step,
                                 unsigned int *next)
{
    if (!step || !next || !step->write ||
        (step->value & ~step->mask))
        return -EINVAL;
    /* Never accept an arbitrary mask even within the port1 offset bank.
     * Exact original-Apple root method slots prescribe every allowed bit.
     */
    switch (step->offset) {
    case N71_ROOT_PORT1_ID2:
        if (!((step->mask == (1U << 8) && step->value == 0) ||
              (step->mask == (1U << 20) && step->value == (1U << 20))))
            return -EOPNOTSUPP;
        break;
    case N71_ROOT_PORT1_ID3:
        if (step->mask != 1U || step->value != 1U)
            return -EOPNOTSUPP;
        break;
    case N71_ROOT_PORT1_ID4:
        if (step->mask != 1U || step->value > 1U)
            return -EOPNOTSUPP;
        break;
    default:
        return -EOPNOTSUPP;
    }
    *next = (current & ~step->mask) | step->value;
    return 0;
}

/* A finite decision over a synthetic captured status sequence. This does
 * NOT read any controller registers; a future owned MMIO driver must be
 * separately reviewed before supplying actual hardware observations.
 *
 * 1000 10-us intervals is a defensive NEW Linux budget, NOT an original
 * bounded timeout; the Apple original polling loop was unbounded.
 */
int n71_s8000_poll_observations(const unsigned int *samples,
                               unsigned int count, unsigned int expected_bit,
                               unsigned int *consumed)
{
    unsigned int i;

    if (!samples || !consumed || count == 0 ||
        count > N71_P1_MAX_POLL_SAMPLES ||
        (expected_bit != 4 && expected_bit != 0))
        return -EINVAL;

    for (i = 0; i < count; i++) {
        if (samples[i] & (1U << expected_bit)) {
            *consumed = i + 1;
            return 0;
        }
    }
    *consumed = count;
    return -ETIMEDOUT;
}

/* Even a correctly planned sequence is NOT authorized to activate. */
int n71_s8000_port1_host_enable(void)
{
    return -EOPNOTSUPP;
}
