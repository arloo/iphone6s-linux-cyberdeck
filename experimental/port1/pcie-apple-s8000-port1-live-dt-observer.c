// SPDX-License-Identifier: GPL-2.0
/*
 * N71 S8000 port1 LIVE FDT descriptor-only observer.
 * Safe for the existing physically verified 2026 RAM-only, PCIe-blocked DT.
 * Does not bind a platform device, turn on domains, request GPIOs, map MMIO,
 * touch PCI/DART or ever access device register contents.
 *
 * Evidence only: matching FDT descriptors DOES NOT establish safe clocks,
 * physical DART requester/SID isolation, PCIe link or working Wi-Fi.
 */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/ioport.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/string.h>

#define N71_PORT1_PATH "/soc/pcie-port1-preflight@602000000"
#define N71_BLOCKED_COMPAT "apple,s8000-pcie-research-blocked"

struct n71_live_window {
    const char *name;
    resource_size_t base, length;
};

static const struct n71_live_window n71_live_windows[] = {
    { "port1-reg-a", 0x602000000ULL, 0x4000ULL },
    { "port1-reg-b", 0x602004000ULL, 0x4000ULL },
    { "dart1-reg", 0x602008000ULL, 0x4000ULL },
};

static int __init n71_port1_live_dt_observer_init(void)
{
    struct device_node *np;
    struct resource res;
    u32 val;
    unsigned int i;
    int ret = -EINVAL;

    /* Source pin: never bind a generic Apple or TSMC A9 machine. */
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;

    np = of_find_node_by_path(N71_PORT1_PATH);
    if (!np)
        return -ENODEV;

    /* Runtime FDT *must* explicitly prevent hardware activation. */
    if (!of_device_is_compatible(np, N71_BLOCKED_COMPAT) ||
        !of_property_read_bool(np, "research,hardware-activation-blocked") ||
        of_property_count_strings(np, "reg-names") !=
            ARRAY_SIZE(n71_live_windows) ||
        of_property_count_u32_elems(np, "reg") != 12)
        goto out;

    for (i = 0; i < ARRAY_SIZE(n71_live_windows); i++) {
        const struct n71_live_window *expected = &n71_live_windows[i];
        const char *regname;

        if (of_property_read_string_index(np, "reg-names", i, &regname) ||
            strcmp(regname, expected->name) ||
            of_address_to_resource(np, i, &res) ||
            res.start != expected->base ||
            resource_size(&res) != expected->length)
            goto out;
    }

    if (of_property_read_u32(np, "research,pcie-port-index", &val) ||
        val != 1 ||
        of_property_read_u32(np, "research,dart1-mapper-index", &val) ||
        val != 0 ||
        of_property_read_u32(np, "research,refclk-to-perst-delay-us", &val) ||
        val != 100)
        goto out;

    pr_info("n71-port1-observer: BLOCKED FDT port1 and DART1 windows verified; no hardware actions\n");
    ret = 0;
out:
    of_node_put(np);
    if (ret)
        pr_err("n71-port1-observer: FDT not qualified, no PCIe operation\n");
    return ret;
}

static void __exit n71_port1_live_dt_observer_exit(void)
{
    pr_info("n71-port1-observer: read-only observer unloaded\n");
}

module_init(n71_port1_live_dt_observer_init);
module_exit(n71_port1_live_dt_observer_exit);
MODULE_DESCRIPTION("Read-only N71 S8000 port1/DART1 live DT verifier");
MODULE_LICENSE("GPL");
