// SPDX-License-Identifier: GPL-2.0
/* N71 Samsung A9: one-shot Wi-Fi port1 three-domain PMGR microlease, NO PCIe link or DMA.
 * The unarmed mode only applies/removes a synthetic DT overlay.
 * Armed mode powers sequentially ref, aux and link1 (parent pcie follows link1) for 25ms, then
 * requests synchronous runtime suspend and detaches, even on error.
 * Ref, aux, link1 and shared parent pcie overlap for 25ms; storage link0, baseband link2 and link3 are NEVER requested.
 * Actual electrical safety is NOT proven; use only with supervised owner
 * RAM-only boot/recovery, original PCIe block, and independent power audit.
 */
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>

#include "n71-s8000-port1-triplet-microlease-blob.h"

#define N71_TRIPLET_TEST_NODE "/soc/n71-port1-triplet-microlease"
#define N71_PCI_GUARD "/soc/pcie-port1-preflight@602000000"
#define N71_PMGR "/soc/power-management@20e000000"
#define N71_HOLD_MS 25

static bool armed;
module_param(armed, bool, 0400);
MODULE_PARM_DESC(armed, "owner-supervised 25ms ref aux link1 lease (default false)");

static const struct {
    const char *name;
    const char *path;
    u32 phandle;
} n71_domains[] = {
    { "ref", N71_PMGR "/power-controller@80148", 0x3a },
    { "aux", N71_PMGR "/power-controller@80318", 0x3b },
    { "link1", N71_PMGR "/power-controller@80328", 0x3c },
    { "root", N71_PMGR "/power-controller@80310", 0x2c },
};

static int n71_overlay_id;
static bool n71_overlay_present;
static bool n71_driver_registered;
static int n71_probe_result = -EINPROGRESS;

static bool n71_validate_nodes(void)
{
    struct device_node *guard, *node;
    unsigned int i;
    bool ok;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return false;
    guard = of_find_node_by_path(N71_PCI_GUARD);
    ok = guard && of_device_is_compatible(guard,
            "apple,s8000-pcie-research-blocked") &&
         of_property_read_bool(guard,
            "research,hardware-activation-blocked");
    of_node_put(guard);
    if (!ok)
        return false;
    for (i = 0; i < ARRAY_SIZE(n71_domains); i++) {
        u32 cells;
        node = of_find_node_by_path(n71_domains[i].path);
        ok = node && node->phandle == n71_domains[i].phandle &&
             of_device_is_compatible(node, "apple,s8000-pmgr-pwrstate") &&
             !of_property_read_u32(node, "#power-domain-cells", &cells) &&
             cells == 0;
        of_node_put(node);
        if (!ok)
            return false;
    }
    return true;
}

static bool n71_validate_probe(struct device *dev)
{
    struct device_node *node = dev->of_node;
    unsigned int i;

    if (!node || !of_device_is_compatible(node,
            "research,n71-s8000-pcie-triplet-microlease") ||
        !of_device_is_available(node) ||
        !of_property_read_bool(node, "research,owner-supervised-triplet-only") ||
        of_property_count_u32_elems(node, "power-domains") != 4 ||
        of_property_count_strings(node, "power-domain-names") != 4 ||
        dev->pm_domain)
        return false;
    for (i = 0; i < ARRAY_SIZE(n71_domains); i++) {
        struct device_node *provider, *expected;
        const char *name;
        bool match;

        provider = of_parse_phandle(node, "power-domains", i);
        expected = of_find_node_by_path(n71_domains[i].path);
        match = provider && expected && provider == expected &&
                !of_property_read_string_index(node,
                        "power-domain-names", i, &name) &&
                !strcmp(name, n71_domains[i].name);
        of_node_put(provider);
        of_node_put(expected);
        if (!match)
            return false;
    }
    return true;
}

static int n71_microlease_probe(struct platform_device *pdev)
{
    static const char * const names[] = { "ref", "aux", "link1" };
    struct device *virt[ARRAY_SIZE(names)] = {};
    unsigned int attached = 0, resumed = 0, i;
    int ret, release_ret;

    n71_probe_result = -EPERM;
    if (!armed || !n71_validate_nodes() ||
        !n71_validate_probe(&pdev->dev))
        return -EPERM;

    /* Multiple domain refs stop the platform core powering one implicitly.
     * Only this supervised probe requests runtime-PM power ON, sequentially. */
    ret = 0;
    for (i = 0; i < ARRAY_SIZE(names); i++) {
        virt[i] = dev_pm_domain_attach_by_name(&pdev->dev, names[i]);
        if (IS_ERR_OR_NULL(virt[i])) {
            ret = virt[i] ? PTR_ERR(virt[i]) : -ENODEV;
            goto rollback;
        }
        attached++;
        ret = pm_runtime_resume_and_get(virt[i]);
        if (ret)
            goto rollback;
        resumed++;
        pr_info("n71-triplet-lease: runtime-PM domain %s ON (step %u/3)\n",
                names[i], i + 1);
        /* The original 100us refclock-to-PERST interval does not apply:
         * PERST is NEVER touched in this PMGR-only experiment. */
        if (i != ARRAY_SIZE(names) - 1)
            usleep_range(150, 300);
    }
    pr_info("n71-triplet-lease: ref aux link1 concurrently ON; 25ms bounded dwell\n");
    msleep(N71_HOLD_MS);

rollback:
    /* Release activity and detach in strictly reversed order, including
     * partial failures. Never leave PMGR virtual consumers installed. */
    for (i = resumed; i > 0; i--) {
        release_ret = pm_runtime_put_sync_suspend(virt[i - 1]);
        if (release_ret < 0 && !ret)
            ret = release_ret;
    }
    for (i = attached; i > 0; i--)
        dev_pm_domain_detach(virt[i - 1], true);
    n71_probe_result = ret;
    if (ret)
        pr_err("n71-triplet-lease: PMGR triplet error rc=%d; reverse detach completed\n", ret);
    else
        pr_info("n71-triplet-lease: ref aux link1 25ms lease complete; all three suspended/detached; no PCIe MMIO/PHY/DART\n");
    return -ENODEV;
}

static const struct of_device_id n71_triplet_of_match[] = {
    { .compatible = "research,n71-s8000-pcie-triplet-microlease" },
    { }
};
MODULE_DEVICE_TABLE(of, n71_triplet_of_match);

static struct platform_driver n71_triplet_driver = {
    .probe = n71_microlease_probe,
    .driver = {
        .name = "n71-s8000-triplet-microlease",
        .of_match_table = n71_triplet_of_match,
    },
};

static int __init n71_microlease_init(void)
{
    struct device_node *existing;
    int ret, roll;

    if (!n71_validate_nodes() ||
        sizeof(n71_triplet_microlease_dtbo) != n71_triplet_microlease_dtbo_len)
        return -ENODEV;
    existing = of_find_node_by_path(N71_TRIPLET_TEST_NODE);
    if (existing) {
        of_node_put(existing);
        return -EEXIST;
    }
    ret = of_overlay_fdt_apply(n71_triplet_microlease_dtbo,
                               sizeof(n71_triplet_microlease_dtbo),
                               &n71_overlay_id, NULL);
    if (ret) {
        if (n71_overlay_id)
            of_overlay_remove(&n71_overlay_id);
        return ret;
    }
    n71_overlay_present = true;
    ret = platform_driver_register(&n71_triplet_driver);
    if (!ret) {
        n71_driver_registered = true;
        platform_driver_unregister(&n71_triplet_driver);
        n71_driver_registered = false;
    }
    if (armed && !ret && n71_probe_result)
        ret = n71_probe_result;
    roll = of_overlay_remove(&n71_overlay_id);
    if (!roll)
        n71_overlay_present = false;
    else
        pr_err("n71-triplet-lease: could not remove synthetic DT node rc=%d\n", roll);
    if (roll)
        return 0; /* keep module data pinned; retry cleanup on rmmod */
    if (ret)
        return ret;
    pr_info("n71-triplet-lease: synthetic DT added/removed, armed=%d, result=%d\n",
            armed, n71_probe_result);
    return 0;
}

static void __exit n71_microlease_exit(void)
{
    int ret;

    if (n71_driver_registered)
        platform_driver_unregister(&n71_triplet_driver);
    if (!n71_overlay_present)
        return;
    ret = of_overlay_remove(&n71_overlay_id);
    if (ret)
        pr_err("n71-triplet-lease: overlay removal failed rc=%d\n", ret);
}

module_init(n71_microlease_init);
module_exit(n71_microlease_exit);
MODULE_DESCRIPTION("Supervised 25ms sequential ref aux link1 S8000 PMGR microlease, default inert");
MODULE_LICENSE("GPL");
