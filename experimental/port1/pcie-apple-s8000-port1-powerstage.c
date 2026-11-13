// SPDX-License-Identifier: GPL-2.0
/*
 * N71 S8000 WLAN port1 power-domain-only EXPERIMENTAL stage.
 * DEFAULT INERT. Requires an alternative DTB with explicit property,
 * status=okay, and allow_power_test=1 at module insertion.
 *
 * Only the PMGR genpd service is used: reference, auxiliary and WLAN
 * link1. The link1 parent pcie is managed by genpd. Never powers
 * link0 storage, link2 baseband or link3 directly. No PCI host/MMIO
 * access, no GPIO requests, no reset, no DART or DMA, no link training.
 * Physical power activation still carries a hardware risk; use only
 * on owner-supervised, recoverable, RAM-only Linux boots.
 */
#include <linux/device.h>
#include <linux/errno.h>
#include <linux/ioport.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/string.h>

static bool allow_power_test;
module_param(allow_power_test, bool, 0400);
MODULE_PARM_DESC(allow_power_test,
                 "owner supervised N71 port1-only genpd test (default off)");

static const char * const n71_power_domains[] = {
    "ref", "aux", "link1",
};

struct n71_port1_powerstage {
    struct dev_pm_domain_list *attached;
};

static int n71_port1_check_descriptors(struct platform_device *pdev)
{
    static const struct {
        const char *name;
        resource_size_t start, size;
    } windows[] = {
        { "root-common", 0x600000000ULL, 0x8000ULL },
        { "port1-control", 0x602000000ULL, 0x4000ULL },
        { "port1-aux", 0x602004000ULL, 0x4000ULL },
        { "config-shared", 0x610000000ULL, 0x1000000ULL },
    };
    static const struct {
        const char *name;
        u32 line;
    } pins[] = {
        { "apple,perst-pin", 161 },
        { "apple,clkreq-pin", 165 },
        { "apple,device-wake-pin", 73 },
    };
    struct device_node *np = pdev->dev.of_node;
    struct resource *res;
    u32 id, value;
    unsigned int i;

    if (!np || !of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000") ||
        !of_property_read_bool(np, "apple,explicit-supervised-power-test"))
        return -ENODEV;
    if (of_property_read_u32(np, "apple,port-index", &id) || id != 1)
        return -EINVAL;
    for (i = 0; i < ARRAY_SIZE(windows); i++) {
        res = platform_get_resource_byname(pdev, IORESOURCE_MEM,
                                            windows[i].name);
        if (!res || res->start != windows[i].start ||
            resource_size(res) != windows[i].size)
            return -EINVAL;
    }
    for (i = 0; i < ARRAY_SIZE(pins); i++) {
        if (of_property_read_u32(np, pins[i].name, &value) ||
            value != pins[i].line)
            return -EINVAL;
    }
    if (of_property_count_u32_elems(np, "power-domains") != 3 ||
        of_property_count_strings(np, "power-domain-names") != 3)
        return -EINVAL;
    for (i = 0; i < ARRAY_SIZE(n71_power_domains); i++) {
        const char *name;

        if (of_property_read_string_index(np, "power-domain-names", i,
                                          &name) ||
            strcmp(name, n71_power_domains[i]))
            return -EINVAL;
    }
    return 0;
}

static int n71_port1_powerstage_probe(struct platform_device *pdev)
{
    const struct dev_pm_domain_attach_data power = {
        .pd_names = n71_power_domains,
        .num_pd_names = ARRAY_SIZE(n71_power_domains),
        .pd_flags = PD_FLAG_ATTACH_POWER_ON | PD_FLAG_DETACH_POWER_OFF,
    };
    struct n71_port1_powerstage *state;
    int err;

    if (!allow_power_test)
        return -EOPNOTSUPP;
    err = n71_port1_check_descriptors(pdev);
    if (err)
        return err;
    state = devm_kzalloc(&pdev->dev, sizeof(*state), GFP_KERNEL);
    if (!state)
        return -ENOMEM;
    err = dev_pm_domain_attach_list(&pdev->dev, &power, &state->attached);
    if (err)
        return dev_err_probe(&pdev->dev, err,
                             "port1-only power domains failed, no PCIe access\n");
    platform_set_drvdata(pdev, state);
    dev_info(&pdev->dev,
             "port1 genpd ref/aux/link1 attached; NO MMIO, reset, DMA or PCI scan\n");
    return 0;
}

static void n71_port1_powerstage_remove(struct platform_device *pdev)
{
    struct n71_port1_powerstage *state = platform_get_drvdata(pdev);

    if (state && state->attached)
        dev_pm_domain_detach_list(state->attached);
}

static const struct of_device_id n71_port1_powerstage_match[] = {
    { .compatible = "apple,n71-s8000-pcie-port1-powerstage" },
    { }
};
MODULE_DEVICE_TABLE(of, n71_port1_powerstage_match);

static struct platform_driver n71_port1_powerstage_driver = {
    .probe = n71_port1_powerstage_probe,
    .remove = n71_port1_powerstage_remove,
    .driver = {
        .name = "n71-s8000-port1-powerstage",
        .of_match_table = n71_port1_powerstage_match,
    },
};
module_platform_driver(n71_port1_powerstage_driver);

MODULE_DESCRIPTION("Supervised N71 S8000 WLAN port1 genpd-only experiment");
MODULE_LICENSE("GPL");
