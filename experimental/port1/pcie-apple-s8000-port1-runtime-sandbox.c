// SPDX-License-Identifier: GPL-2.0
/* Runtime OF sandbox: an inert, reversible N71/S8000 single-node overlay.
 * The embedded FDT adds one disabled leaf with no hardware resources.
 * DOES NOT add PCI host, pinctrl, DART, PMGR phandles or a driver match.
 */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/string.h>

#include "n71-s8000-port1-runtime-sandbox-blob.h"

#define N71_SANDBOX_PATH "/soc/n71-port1-runtime-sandbox"
#define N71_ORIGINAL_BLOCK_PATH "/soc/pcie-port1-preflight@602000000"

static int n71_overlay_id;
static bool n71_overlay_applied;

static bool n71_inert_sandbox_node_qualified(struct device_node *np)
{
    const char *status;

    if (!np || !of_device_is_compatible(np,
                 "research,n71-s8000-port1-inert-sandbox") ||
        !of_property_read_bool(np, "research,observer-only") ||
        of_property_read_string(np, "status", &status) ||
        strcmp(status, "disabled") || of_device_is_available(np))
        return false;

    /* This sandbox cannot address any hardware or take a power domain. */
    return !of_find_property(np, "reg", NULL) &&
           !of_find_property(np, "ranges", NULL) &&
           !of_find_property(np, "power-domains", NULL) &&
           !of_find_property(np, "clocks", NULL) &&
           !of_find_property(np, "resets", NULL) &&
           !of_find_property(np, "iommus", NULL) &&
           !of_find_property(np, "interrupts", NULL) &&
           !of_find_property(np, "gpios", NULL) &&
           !of_find_property(np, "status-okay", NULL);
}

static int __init n71_runtime_sandbox_init(void)
{
    struct device_node *blocked, *sandbox;
    int err;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;

    blocked = of_find_node_by_path(N71_ORIGINAL_BLOCK_PATH);
    if (!blocked)
        return -ENODEV;
    err = -EPERM;
    if (!of_device_is_compatible(blocked,
               "apple,s8000-pcie-research-blocked") ||
        !of_property_read_bool(blocked,
               "research,hardware-activation-blocked"))
        goto out_blocked;
    of_node_put(blocked);

    sandbox = of_find_node_by_path(N71_SANDBOX_PATH);
    if (sandbox) {
        of_node_put(sandbox);
        return -EEXIST;
    }
    if (n71_port1_sandbox_dtbo_len != sizeof(n71_port1_sandbox_dtbo))
        return -EINVAL;

    err = of_overlay_fdt_apply(n71_port1_sandbox_dtbo,
                               sizeof(n71_port1_sandbox_dtbo),
                               &n71_overlay_id, NULL);
    if (err) {
        /* OF API may partially apply a changeset even on failure. */
        if (n71_overlay_id)
            of_overlay_remove(&n71_overlay_id);
        return err;
    }
    n71_overlay_applied = true;

    sandbox = of_find_node_by_path(N71_SANDBOX_PATH);
    err = n71_inert_sandbox_node_qualified(sandbox) ? 0 : -EINVAL;
    of_node_put(sandbox);
    if (err) {
        int rollback = of_overlay_remove(&n71_overlay_id);

        n71_overlay_applied = rollback != 0;
        pr_err("n71-port1-sandbox: validation failed, rollback rc=%d\n",
               rollback);
        return err;
    }
    pr_info("n71-port1-sandbox: disabled resource-free RAM overlay applied; PCIe remains blocked\n");
    return 0;

out_blocked:
    of_node_put(blocked);
    return err;
}

static void __exit n71_runtime_sandbox_exit(void)
{
    int err;

    if (!n71_overlay_applied)
        return;
    err = of_overlay_remove(&n71_overlay_id);
    if (err)
        pr_err("n71-port1-sandbox: failed to remove DT overlay rc=%d\n",
               err);
    else {
        n71_overlay_applied = false;
        pr_info("n71-port1-sandbox: disabled RAM overlay removed\n");
    }
}

module_init(n71_runtime_sandbox_init);
module_exit(n71_runtime_sandbox_exit);
MODULE_DESCRIPTION("Reversible, disabled N71 port1 OF overlay sandbox");
MODULE_LICENSE("GPL");
