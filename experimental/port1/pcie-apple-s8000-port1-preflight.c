// SPDX-License-Identifier: GPL-2.0
/*
 * N71/S8000 PCIe port1 read-only *resource* preflight, NOT a PCI host.
 * Source topology: owner-confirmed Apple N71 ADT + original iOS resource order.
 * Only inspects Linux DT resource descriptors and GPIO property cell numbers.
 * It NEVER maps MMIO, requests/changes GPIOs, toggles power/reset/clocks,
 * enumerates PCI, attaches DMA, touches DART, or registers an IRQ.
 *
 * This experimental match MUST NOT be used as a generic Apple PCIe driver.
 * Activation requires separate proof of power, PHY, requester SID and reset
 * noninterference, and an intentionally different compatible/driver.
 */
#include <linux/device.h>
#include <linux/errno.h>
#include <linux/ioport.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#define N71_PORT1_INDEX 1U

struct n71_port1_mmio_window {
    const char *name;
    resource_size_t start;
    resource_size_t bytes;
};

static const struct n71_port1_mmio_window n71_port1_windows[] = {
    { "root-common",     0x600000000ULL, 0x8000ULL },
    { "port1-control",   0x602000000ULL, 0x4000ULL },
    { "port1-aux",       0x602004000ULL, 0x4000ULL },
    { "config-shared",   0x610000000ULL, 0x1000000ULL },
};

struct n71_port1_pin {
    const char *name;
    u32 line;
};

static const struct n71_port1_pin n71_port1_pins[] = {
    { "apple,perst-pin", 161 },
    { "apple,clkreq-pin", 165 },
    { "apple,device-wake-pin", 73 },
};

static int n71_port1_preflight_probe(struct platform_device *pdev)
{
    struct device_node *np = pdev->dev.of_node;
    struct resource *res;
    u32 id, actual;
    unsigned int i;
    int err;

    if (!np || !of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000") ||
        !of_property_read_bool(np, "apple,observer-only"))
        return -ENODEV;

    err = of_property_read_u32(np, "apple,port-index", &id);
    if (err || id != N71_PORT1_INDEX)
        return -EINVAL;

    /* Descriptor-only: platform_get_resource_byname does NOT ioremap. */
    for (i = 0; i < ARRAY_SIZE(n71_port1_windows); i++) {
        const struct n71_port1_mmio_window *w = &n71_port1_windows[i];

        res = platform_get_resource_byname(pdev, IORESOURCE_MEM, w->name);
        if (!res || res->start != w->start ||
            resource_size(res) != w->bytes)
            return dev_err_probe(&pdev->dev, -EINVAL,
                                 "unqualified %s resource descriptor\n",
                                 w->name);
    }

    /* These source-derived indices are not GPIO polarity proof and are
     * intentionally NOT passed to gpiod_get or a line-request interface.
     */
    for (i = 0; i < ARRAY_SIZE(n71_port1_pins); i++) {
        const struct n71_port1_pin *p = &n71_port1_pins[i];

        err = of_property_read_u32(np, p->name, &actual);
        if (err || actual != p->line)
            return dev_err_probe(&pdev->dev, -EINVAL,
                                 "unqualified %s GPIO descriptor\n",
                                 p->name);
    }

    dev_info(&pdev->dev,
             "N71 S8000 port1 descriptors qualified; PCIe host and DMA remain OFF\n");
    return 0;
}

static const struct of_device_id n71_port1_preflight_match[] = {
    { .compatible = "apple,n71-s8000-pcie-port1-preflight" },
    { }
};
MODULE_DEVICE_TABLE(of, n71_port1_preflight_match);

static struct platform_driver n71_port1_preflight_driver = {
    .probe = n71_port1_preflight_probe,
    .driver = {
        .name = "n71-s8000-pcie-port1-preflight",
        .of_match_table = n71_port1_preflight_match,
    },
};
module_platform_driver(n71_port1_preflight_driver);

MODULE_DESCRIPTION("N71/S8000 PCIe port1 DT-only preflight (no hardware access)");
MODULE_LICENSE("GPL");
