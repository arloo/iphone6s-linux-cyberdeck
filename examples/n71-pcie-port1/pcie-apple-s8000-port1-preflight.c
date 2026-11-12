// SPDX-License-Identifier: GPL-2.0
/*
 * Apple S8000/N71 PCIe WLAN PORT1-ONLY metadata preflight - HARDWARE BLOCKED.
 *
 * This is a development-only platform guard, NOT a functional PCIe host.
 * The owner-retained original Apple N71 ADT independently proves exactly
 * three disjoint per-WLAN/DART1 windows; all other PCIe port, shared-root,
 * NAND/storage and baseband windows remain forbidden.
 *
 * Probe reads ONLY OF properties and pre-resolved resource DESCRIPTORS.
 * It NEVER maps MMIO, accesses registers, powers a PHY, requests a clock,
 * drives reset/PERST#, creates MSI/IRQ, touches NAND or configures DMA.
 * Even after ALL requested preflight metadata is correct, probe returns
 * -EOPNOTSUPP. Neither a kernel build nor a passing preflight implies
 * real BCM4350 enumeration or Wi-Fi functionality.
 *
 * NEVER bind the upstream M1 "apple,pcie" compatible to A9/S8000.
 */
#include <linux/errno.h>
#include <linux/ioport.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

struct apple_s8000_guard_range {
    resource_size_t start;
    resource_size_t size;
};

/* SoC-invariant, authentic N71/S8000 Apple ADT resource metadata.
 * No board-private calibration or raw Apple original binary data.
 */
static const struct apple_s8000_guard_range wlan_candidate[] = {
    { 0x602000000ULL, 0x4000 }, /* port-1 register window A */
    { 0x602004000ULL, 0x4000 }, /* port-1 register window B */
    { 0x602008000ULL, 0x4000 }, /* port-1 dedicated DART window */
};

/* These windows are ALWAYS protected and never passed to a probe. */
static const struct apple_s8000_guard_range protected[] = {
    { 0x600000000ULL, 0x8000 }, /* shared root-complex A */
    { 0x600008000ULL, 0x4000 }, /* shared root-complex B */
    { 0x601000000ULL, 0xc000 }, /* port-0 storage and DART0 */
    { 0x603000000ULL, 0xc000 }, /* port-2 baseband and DART2 */
    { 0x604000000ULL, 0x8000 }, /* unknown port-3 */
    { 0x610000000ULL, 0x1000000 }, /* shared configuration aperture */
};

static const char * const wlan_candidate_names[] = {
    "port1-reg-a", "port1-reg-b", "dart1-reg",
};

static bool apple_s8000_regions_overlap(const struct apple_s8000_guard_range *a,
                                        const struct apple_s8000_guard_range *b)
{
    resource_size_t a_end, b_end;

    if (!a->size || !b->size ||
        a->start > (resource_size_t)-1 - a->size ||
        b->start > (resource_size_t)-1 - b->size)
        return true;

    a_end = a->start + a->size;
    b_end = b->start + b->size;
    return a->start < b_end && b->start < a_end;
}

static bool apple_s8000_port1_metadata_isolated(void)
{
    size_t i, j;

    for (i = 0; i < ARRAY_SIZE(wlan_candidate); i++) {
        for (j = i + 1; j < ARRAY_SIZE(wlan_candidate); j++)
            if (apple_s8000_regions_overlap(&wlan_candidate[i],
                                           &wlan_candidate[j]))
                return false;
        for (j = 0; j < ARRAY_SIZE(protected); j++)
            if (apple_s8000_regions_overlap(&wlan_candidate[i],
                                           &protected[j]))
                return false;
    }
    return true;
}

static int apple_s8000_preflight_private_port_metadata(
    struct platform_device *pdev)
{
    struct device_node *node = pdev->dev.of_node;
    const struct resource *res;
    u32 port, mapper, refclk_perst;
    size_t i;

    /* These artificial research properties are NOT Apple native-DT keys.
     * Enabling this synthetic node does not make the hardware supported.
     */
    if (!node ||
        !of_property_read_bool(node, "research,hardware-activation-blocked"))
        return -EINVAL;

    if (of_property_read_u32(node, "research,pcie-port-index", &port) ||
        of_property_read_u32(node, "research,dart1-mapper-index", &mapper) ||
        of_property_read_u32(node, "research,refclk-to-perst-delay-us",
                             &refclk_perst))
        return -EINVAL;

    if (port != 1 || mapper != 0 || refclk_perst != 100)
        return -ERANGE; /* Original Apple XNU _IODelay microseconds, NOT milliseconds. */

    /* Resource descriptors only; NOT ioremap, readl or MMIO access. */
    for (i = 0; i < ARRAY_SIZE(wlan_candidate); i++) {
        res = platform_get_resource_byname(pdev, IORESOURCE_MEM,
                                           wlan_candidate_names[i]);
        if (!res)
            return -EINVAL;

        if (res->start != wlan_candidate[i].start ||
            resource_size(res) != wlan_candidate[i].size)
            return -ERANGE;
    }

    if (platform_get_resource(pdev, IORESOURCE_MEM,
                              ARRAY_SIZE(wlan_candidate)))
        return -ERANGE; /* No fourth window, even if disjoint. */

    return 0; /* This is JUST metadata validity, never activation. */
}

static int apple_s8000_guard_probe(struct platform_device *pdev)
{
    int ret;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;

    if (!apple_s8000_port1_metadata_isolated())
        return -ERANGE;

    ret = apple_s8000_preflight_private_port_metadata(pdev);
    if (ret)
        return ret;

    dev_info(&pdev->dev,
             "N71 S8000 port1/DART1 descriptor preflight passed; hardware BLOCKED\n");

    /* Mandatory final refusal: no host, no MSI, no DART DMA, no Wi-Fi. */
    return -EOPNOTSUPP;
}

static const struct of_device_id apple_s8000_guard_of_match[] = {
    { .compatible = "apple,s8000-pcie-research-blocked" },
    { }
};
MODULE_DEVICE_TABLE(of, apple_s8000_guard_of_match);

static struct platform_driver apple_s8000_guard_driver = {
    .probe = apple_s8000_guard_probe,
    .driver = {
        .name = "apple-s8000-pcie-research-guard",
        .of_match_table = apple_s8000_guard_of_match,
    },
};
module_platform_driver(apple_s8000_guard_driver);

MODULE_DESCRIPTION("N71 S8000 PCIe WLAN port1 metadata-only preflight, ALWAYS BLOCKED");
MODULE_LICENSE("GPL");
