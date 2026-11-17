// SPDX-License-Identifier: GPL-2.0
/*
 * Apple iPhone 6s N71/Samsung S8000 storage physical platform inventory.
 *
 * Register REAL, stock-verified A9 DART0 and NVMe-MMU0 MMIO resources with
 * Linux's platform-device model. This is NOT an NVMe/disk driver: no MMIO
 * access, no devm_ioremap, no DMA, no PCIe rescan, no reset release and no
 * PMGR write. Everything is temporary and opt-in, with clean unregister.
 *
 * Genuine owner-private Apple Device Tree evidence:
 *   /arm-io/dart-apcie0    phandle 0x80, reg (0x601008000, 0x4000)
 *   /arm-io/nvme-mmu0     phandle 0x82, reg (0x601004000, 0x4000)
 *                          and (0x601000000, 0x4000)
 *   /arm-io/apcie/pci-bridge0/s3e iommu-parent (0x81,0x81,0x82).
 *
 * No platform devices are declared for these controllers in the current
 * N71 Linux DT. Registration creates real kernel device objects but does
 * not claim the currently gated silicon is accessible, initialized or
 * authorized to produce DMA transactions.
 */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/ioport.h>
#include <linux/kernel.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/regmap.h>
#include <linux/string.h>
#include <linux/types.h>

#define N71_PMGR_PATH "/soc/power-management@20e000000"
#define N71_P0_NODE N71_PMGR_PATH "/power-controller@80320"
#define N71_PCI_GUARD "/soc/pcie-port1-preflight@602000000"
#define N71_P0_PMGR_REG 0x80320U
#define N71_DART0_BASE 0x601008000ULL
#define N71_NVMMU0_BASE 0x601004000ULL
#define N71_NVMMU0_PORT0_BASE 0x601000000ULL
#define N71_REG_SIZE 0x4000U

static bool armed;
static bool attach_domains;
module_param(armed, bool, 0400);
module_param(attach_domains, bool, 0400);
MODULE_PARM_DESC(attach_domains, "attach both devices to existing pcie_link0 genpd WITHOUT requesting power");
MODULE_PARM_DESC(armed, "explicit N71 storage device registration (default off)");

static struct platform_device *n71_dart0_dev;
static struct platform_device *n71_nvmmu0_dev;
static int n71_port0_power_off(void);
static bool n71_dart0_attached;
static bool n71_nvmmu0_attached;

static int n71_attach_power_domains(void)
{
    struct of_phandle_args spec = {};
    struct device_node *node;
    struct device_node *parent;
    const char *label;
    u32 offset;
    int ret;

    /* The stock PMGR node has *no* DT phandle. Resolve by exact FDT
     * node path, never by guessing a PMGR device index or physical addr.
     */
    node = of_find_node_by_path(N71_P0_NODE);
    if (!node)
        return -ENODEV;
    if (!of_device_is_compatible(node, "apple,s8000-pmgr-pwrstate") ||
        node->phandle ||
        of_property_read_string(node, "label", &label) ||
        strcmp(label, "pcie_link0") ||
        of_property_read_u32(node, "reg", &offset) ||
        offset != N71_P0_PMGR_REG ||
        of_property_read_u32(node, "#power-domain-cells", &offset) ||
        offset != 0) {
        ret = -EPERM;
        goto out;
    }
    parent = of_parse_phandle(node, "power-domains", 0);
    if (!parent || !of_device_is_compatible(parent,
                   "apple,s8000-pmgr-pwrstate")) {
        of_node_put(parent);
        ret = -EPERM;
        goto out;
    }
    of_node_put(parent);

    spec.np = node;
    spec.args_count = 0;
    ret = of_genpd_add_device(&spec, &n71_dart0_dev->dev);
    if (ret)
        goto out;
    n71_dart0_attached = true;
    if (!n71_dart0_dev->dev.pm_domain) {
        ret = -EIO;
        goto out;
    }
    ret = of_genpd_add_device(&spec, &n71_nvmmu0_dev->dev);
    if (ret)
        goto out;
    n71_nvmmu0_attached = true;
    if (!n71_nvmmu0_dev->dev.pm_domain) {
        ret = -EIO;
        goto out;
    }
    /* genpd attach does not call power_on(). Check both PMGR target and
     * actual value remain zero. Never call pm_runtime_get/enable.
     */
    ret = n71_port0_power_off();
    if (!ret)
        pr_info("n71-s3e-genpd: PHYSICAL_DART0_NVMMU0_ATTACHED_TO_EXISTING_GENPD; power remains OFF; no DMA\n");
out:
    of_node_put(node);
    return ret;
}

static void n71_detach_power_domains(void)
{
    int ret;
    if (n71_nvmmu0_attached) {
        ret = pm_genpd_remove_device(&n71_nvmmu0_dev->dev);
        if (ret)
            pr_err("n71-s3e-genpd: DETACH_NVMMU0_FAILED rc=%d\n",ret);
        else
            n71_nvmmu0_attached = false;
    }
    if (n71_dart0_attached) {
        ret = pm_genpd_remove_device(&n71_dart0_dev->dev);
        if (ret)
            pr_err("n71-s3e-genpd: DETACH_DART0_FAILED rc=%d\n",ret);
        else
            n71_dart0_attached = false;
    }
}


static const struct resource dart0_resources[] = {
    {
        .name = "n71-s8000-physical-dart0",
        .start = N71_DART0_BASE,
        .end = N71_DART0_BASE + N71_REG_SIZE - 1,
        .flags = IORESOURCE_MEM,
    },
};
static const struct resource nvmmu0_resources[] = {
    {
        .name = "n71-s8000-physical-nvmmu0-tcb",
        .start = N71_NVMMU0_BASE,
        .end = N71_NVMMU0_BASE + N71_REG_SIZE - 1,
        .flags = IORESOURCE_MEM,
    },
    {
        .name = "n71-s8000-physical-nvmmu0-port0",
        .start = N71_NVMMU0_PORT0_BASE,
        .end = N71_NVMMU0_PORT0_BASE + N71_REG_SIZE - 1,
        .flags = IORESOURCE_MEM,
    },
};

static bool n71_board_guard(void)
{
    struct device_node *guard;
    struct pci_dev *wlan;
    bool valid;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return false;

    guard = of_find_node_by_path(N71_PCI_GUARD);
    valid = guard &&
            of_device_is_compatible(guard, "apple,s8000-pcie-research-blocked") &&
            of_property_read_bool(guard, "research,hardware-activation-blocked");
    of_node_put(guard);
    if (!valid)
        return false;

    wlan = pci_get_device(0x14e4, 0x43a3, NULL);
    valid = wlan != NULL;
    pci_dev_put(wlan);
    return valid;
}

static int n71_port0_power_off(void)
{
    struct device_node *node;
    struct regmap *regmap;
    u32 state;
    int err;

    node = of_find_node_by_path(N71_PMGR_PATH);
    if (!node)
        return -ENODEV;
    regmap = syscon_node_to_regmap(node);
    of_node_put(node);
    if (IS_ERR(regmap))
        return PTR_ERR(regmap);

    err = regmap_read(regmap, N71_P0_PMGR_REG, &state);
    if (err)
        return err;
    /* Actual state (bits 7:4) and requested target (bits 3:0) off. */
    if (state & 0xff)
        return -EBUSY;
    return 0;
}

static int n71_storage_probe(struct platform_device *pdev)
{
    struct resource *r;
    int expected;
    int i;

    if (!strcmp(pdev->name, "n71-a9-dart0"))
        expected = 1;
    else if (!strcmp(pdev->name, "n71-a9-nvmmu0"))
        expected = 2;
    else
        return -ENODEV;

    for (i = 0; i < expected; i++) {
        r = platform_get_resource(pdev, IORESOURCE_MEM, i);
        if (!r || resource_size(r) != N71_REG_SIZE)
            return -EINVAL;
        if (expected == 1 && r->start != N71_DART0_BASE)
            return -EINVAL;
        if (expected == 2 && i == 0 && r->start != N71_NVMMU0_BASE)
            return -EINVAL;
        if (expected == 2 && i == 1 &&
            r->start != N71_NVMMU0_PORT0_BASE)
            return -EINVAL;
    }
    if (platform_get_resource(pdev, IORESOURCE_MEM, expected))
        return -EINVAL;

    /* This is a real platform-device registration, NOT a live hardware
     * activation. The next driver phase must explicitly request a safe
     * genpd runtime lease and verify register reachability before DMA.
     */
    dev_info(&pdev->dev,
             "N71 physical storage-controller resources registered: %d regions; no MMIO/clock/PMGR/DMA/NAND access\n",
             expected);
    return 0;
}

static const struct platform_device_id n71_storage_ids[] = {
    { .name = "n71-a9-dart0" },
    { .name = "n71-a9-nvmmu0" },
    { },
};
MODULE_DEVICE_TABLE(platform, n71_storage_ids);

static struct platform_driver n71_storage_inventory_driver = {
    .probe = n71_storage_probe,
    .id_table = n71_storage_ids,
    .driver = {
        .name = "n71-s8000-storage-platform-inventory",
    },
};

static struct platform_device *n71_add_device(const char *name,
                                              const struct resource *resources,
                                              unsigned int count)
{
    struct platform_device_info details = {
        .name = name,
        .id = PLATFORM_DEVID_AUTO,
        .res = resources,
        .num_res = count,
    };

    return platform_device_register_full(&details);
}

static int __init n71_platform_inventory_init(void)
{
    int err;

    if (!armed) {
        pr_info("n71-s3e-inventory: UNARMED; no device registration\n");
        return 0;
    }
    if (attach_domains && !armed)
        return -EPERM;
    if (!n71_board_guard())
        return -EPERM;
    err = n71_port0_power_off();
    if (err) {
        pr_err("n71-s3e-inventory: port0 is not verified powered off; abort\n");
        return err;
    }

    err = platform_driver_register(&n71_storage_inventory_driver);
    if (err)
        return err;

    n71_dart0_dev = n71_add_device("n71-a9-dart0",
                                   dart0_resources,
                                   ARRAY_SIZE(dart0_resources));
    if (IS_ERR(n71_dart0_dev)) {
        err = PTR_ERR(n71_dart0_dev);
        n71_dart0_dev = NULL;
        goto fail_driver;
    }
    n71_nvmmu0_dev = n71_add_device("n71-a9-nvmmu0",
                                    nvmmu0_resources,
                                    ARRAY_SIZE(nvmmu0_resources));
    if (IS_ERR(n71_nvmmu0_dev)) {
        err = PTR_ERR(n71_nvmmu0_dev);
        n71_nvmmu0_dev = NULL;
        goto fail_dart;
    }

    if (attach_domains) {
        err = n71_attach_power_domains();
        if (err) {
            pr_err("n71-s3e-genpd: ATTACH_REJECTED rc=%d; no power requested\n",err);
            n71_detach_power_domains();
            /* Do not free any domain-attached device if detach unexpectedly
             * fails, since its generic_pm_domain owns a live pointer.
             */
            if (n71_dart0_attached || n71_nvmmu0_attached) {
                __module_get(THIS_MODULE);
                pr_err("n71-s3e-genpd: QUARANTINE retained dev references; no unsafe unbind\n");
                return 0;
            }
            goto fail_nvmmu;
        }
    }
    /* Explicitly use system driver_override? No: this registration is a
     * resource/namespace inventory. It intentionally does not bind a driver
     * capable of changing the device's clock, PMGR or IOMMU state.
     */
    pr_info("n71-s3e-inventory: REAL_N71_DART0_AND_NVMMU0_PLATFORM_REGISTERED; port0 off, NAND intact\n");
    return 0;

fail_nvmmu:
    platform_device_unregister(n71_nvmmu0_dev);
    n71_nvmmu0_dev = NULL;
fail_dart:
    platform_device_unregister(n71_dart0_dev);
    n71_dart0_dev = NULL;
fail_driver:
    platform_driver_unregister(&n71_storage_inventory_driver);
    return err;
}

static void __exit n71_platform_inventory_exit(void)
{
    if (n71_nvmmu0_attached || n71_dart0_attached) {
        n71_detach_power_domains();
        if (n71_nvmmu0_attached || n71_dart0_attached) {
            pr_err("n71-s3e-genpd: DETACH_UNSUCCESSFUL; refuse to unregister devices\n");
            return;
        }
    }
    if (n71_nvmmu0_dev)
        platform_device_unregister(n71_nvmmu0_dev);
    if (n71_dart0_dev)
        platform_device_unregister(n71_dart0_dev);
    if (armed)
        platform_driver_unregister(&n71_storage_inventory_driver);
    pr_info("n71-s3e-inventory: detached both genuine physical resources; no NAND writes\n");
}

module_init(n71_platform_inventory_init);
module_exit(n71_platform_inventory_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("S8000 DART0 NVMMU0 real platform devices bound to powered-off genpd, no activation");
