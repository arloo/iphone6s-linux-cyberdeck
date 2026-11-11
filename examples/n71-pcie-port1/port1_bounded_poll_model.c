/* SPDX-License-Identifier: MIT */
/*
 * N71/S8000 PCIe port-1: OFFLINE BOUNDED STATUS-QUERY MODEL.
 *
 * Original AppleS800xPCIePort virtual slot 1816 contains a status-query
 * backedge at its controller vtable slot 2008 with no explicit caller-side
 * retry limit. This standalone C model adds a finite retry policy for
 * future review; it DOES NOT claim that the slot is PCIe LTSSM/link-ready
 * or that its nonzero result means WLAN connected.
 *
 * This source contains NO MMIO, PCI, reset, clock, GPIO or DMA operation.
 * Callback injection is only used in synthetic tests. Never register
 * this as a working A9 controller or bind to physical hardware.
 */
#include <stdint.h>
#include <errno.h>

#define N71_WLAN_PORT_INDEX 1U
#define N71_MAX_OFFLINE_POLL_ATTEMPTS 4096U

typedef int (*n71_port1_query_fn)(void *opaque, uint32_t port, uint32_t *status);

int n71_port1_bounded_status_query(
    n71_port1_query_fn query, void *opaque, uint32_t port,
    uint32_t max_attempts, uint32_t *attempts_used, uint32_t *last_status)
{
    uint32_t attempt;
    uint32_t status = 0U;

    if (!query || !attempts_used || !last_status ||
        port != N71_WLAN_PORT_INDEX || max_attempts == 0U ||
        max_attempts > N71_MAX_OFFLINE_POLL_ATTEMPTS)
        return -EINVAL;

    *attempts_used = 0U;
    *last_status = 0U;

    for (attempt = 0U; attempt < max_attempts; ++attempt) {
        status = 0U;
        if (query(opaque, port, &status) != 0) {
            *attempts_used = attempt + 1U;
            return -EIO;
        }
        *attempts_used = attempt + 1U;
        *last_status = status;

        /* "nonzero" only. Meaning of original vtable method unknown. */
        if (status != 0U)
            return 0;
    }

    return -ETIMEDOUT;
}
