// SPDX-License-Identifier: GPL-2.0
/*
 * Only for the phandle-bootstrapped owner RAM N71 Samsung FDT.
 * Adds ONE disabled PCIe powerstage descriptor, tests phandle resolution,
 * removes it on rmmod. NEVER attaches any genpd or touches actual hardware.
 */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/string.h>

#include "n71-s8000-port1-powerstage-runtime-disabled-blob.h"

#define N71_GUARD "/soc/pcie-port1-preflight@602000000"
#define N71_POWERSTAGE "/soc/pcie-port1-powerstage@602000000"
#define N71_PMGR "/soc/power-management@20e000000"

static const struct {
    const char *path;
    u32 phandle;
} n71_links[] = {
    { N71_PMGR "/power-controller@80148", 0x3a },
    { N71_PMGR "/power-controller@80318", 0x3b },
    { N71_PMGR "/power-controller@80328", 0x3c },
};

static int n71_changeset_id;
static bool n71_changeset_active;

static bool n71_provider_qualified(unsigned int i)
{
    struct device_node *node = of_find_node_by_path(n71_links[i].path);
    u32 cells;
    bool good = false;

    if (node && of_device_is_compatible(node, "apple,s8000-pmgr-pwrstate") &&
        node->phandle == n71_links[i].phandle &&
        !of_property_read_u32(node, "#power-domain-cells", &cells) &&
        cells == 0)
        good = true;
    of_node_put(node);
    return good;
}

static bool n71_inserted_node_qualified(void)
{
    struct device_node *node = of_find_node_by_path(N71_POWERSTAGE);
    unsigned int i;
    bool good;

    if (!node)
        return false;
    good = of_device_is_compatible(node,
               "apple,n71-s8000-pcie-port1-powerstage") &&
           !of_device_is_available(node) &&
           !of_property_read_bool(node, "apple,explicit-supervised-power-test") &&
           of_property_count_u32_elems(node, "power-domains") == 3 &&
           of_property_count_strings(node, "power-domain-names") == 3;
    for (i = 0; good && i < ARRAY_SIZE(n71_links); i++) {
        struct device_node *provider;
        const char *domain;
        u32 ref;

        if (of_property_read_u32_index(node, "power-domains", i, &ref) ||
            ref != n71_links[i].phandle ||
            of_property_read_string_index(node, "power-domain-names", i,
                                          &domain)) {
            good = false;
            break;
        }
        if (strcmp(domain, i == 0 ? "ref" : i == 1 ? "aux" : "link1")) {
            good = false;
            break;
        }
        provider = of_parse_phandle(node, "power-domains", i);
        if (!provider || of_node_cmp(provider->full_name, n71_links[i].path))
            good = false;
        of_node_put(provider);
    }
    of_node_put(node);
    return good;
}

static int __init n71_powerstage_overlay_init(void)
{
    struct device_node *guard, *already;
    unsigned int i;
    int err;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;
    guard = of_find_node_by_path(N71_GUARD);
    if (!guard)
        return -ENODEV;
    err = -EPERM;
    if (!of_device_is_compatible(guard,
              "apple,s8000-pcie-research-blocked") ||
        !of_property_read_bool(guard,
              "research,hardware-activation-blocked"))
        goto out_guard;
    of_node_put(guard);

    for (i = 0; i < ARRAY_SIZE(n71_links); i++)
        if (!n71_provider_qualified(i))
            return -ENODEV;

    already = of_find_node_by_path(N71_POWERSTAGE);
    if (already) {
        of_node_put(already);
        return -EEXIST;
    }
    if (n71_port1_powerstage_dtbo_len != sizeof(n71_port1_powerstage_dtbo))
        return -EINVAL;
    err = of_overlay_fdt_apply(n71_port1_powerstage_dtbo,
                               sizeof(n71_port1_powerstage_dtbo),
                               &n71_changeset_id, NULL);
    if (err) {
        if (n71_changeset_id)
            of_overlay_remove(&n71_changeset_id);
        return err;
    }
    n71_changeset_active = true;
    if (!n71_inserted_node_qualified()) {
        err = of_overlay_remove(&n71_changeset_id);
        n71_changeset_active = err != 0;
        pr_err("n71-powerstage-overlay: node validation failed; rollback rc=%d\n", err);
        return -EINVAL;
    }
    pr_info("n71-powerstage-overlay: PMGR ref/aux/link1 phandles resolve; node DISABLED; no hardware actions\n");
    return 0;

out_guard:
    of_node_put(guard);
    return err;
}

static void __exit n71_powerstage_overlay_exit(void)
{
    int err;

    if (!n71_changeset_active)
        return;
    err = of_overlay_remove(&n71_changeset_id);
    if (err)
        pr_err("n71-powerstage-overlay: could not remove disabled descriptor rc=%d\n", err);
    else {
        n71_changeset_active = false;
        pr_info("n71-powerstage-overlay: disabled descriptor removed\n");
    }
}

module_init(n71_powerstage_overlay_init);
module_exit(n71_powerstage_overlay_exit);
MODULE_DESCRIPTION("N71 S8000 disabled port1 runtime FDT provider resolution");
MODULE_LICENSE("GPL");
