// SPDX-License-Identifier: GPL-2.0
/*
 * Samsung S8000 N71: bounded read-only stock PCIe PHY visibility pilot.
 *
 * The original Apple 'apcie' ADT resource index 10 gives the COMMON PHY
 * window 0x600008000/0x4000. The listed offsets are verified original
 * 32-bit RMW tunable offsets, i.e. Apple firmware also READS them.
 *
 * No PCIe port0 power lease, reset, DMA, DART, NVMMU, NAND, root register
 * or PHY register writes. Live, known-good WLAN port1 stays ON, port0 OFF.
 * Fail closed unless exact Apple N71 S8000, live BCM4350 and original PMGR.
 */
#include <linux/err.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/regmap.h>

#define N71_ROOT_PHYS 0x600000000ULL
#define N71_PHY_PHYS 0x600008000ULL
#define N71_DART1_PHYS 0x602008000ULL
#define N71_PMGR_PATH "/soc/power-management@20e000000"
#define N71_RESEARCH_GUARD "/soc/pcie-port1-preflight@602000000"
#define ACTUAL(state) (((state) >> 4) & 0xfU)
static bool armed;
module_param(armed, bool, 0400);
MODULE_PARM_DESC(armed, "read-only real Apple PHY and WLAN DART1 MMIO, default off");

static const u32 n71_stock_phy_offsets[] = {
    0x1a18U, 0x1a58U, 0x0108U, 0x0118U, 0x011cU, 0x0308U, 0x0318U, 0x031cU, 0x0518U, 0x051cU, 0x0718U, 0x071cU, 0x0918U, 0x091cU, 0x0a24U, 0x0a34U, 0x0a40U, 0x0a44U, 0x0c24U, 0x0c34U, 0x0c40U, 0x0c44U, 0x0e24U, 0x0e34U, 0x0e40U, 0x0e44U, 0x1024U, 0x1034U, 0x1040U, 0x1044U, 0x1224U, 0x1234U, 0x1240U, 0x1244U, 0x0b4cU, 0x0b50U, 0x0d4cU, 0x0d50U, 0x0f50U, 0x1150U, 0x1350U,
};

static int __init n71_stock_phy_ro_init(void)
{
    struct device_node *node, *guard;
    struct pci_dev *wlan;
    struct regmap *pmgr;
    void __iomem *root = NULL, *phy = NULL, *dart1 = NULL;
    u32 pcie = 0, p0 = 0, p1 = 0, phy_values[ARRAY_SIZE(n71_stock_phy_offsets)];
    u32 original_root_p0, original_root_p1, root_p0, root_p1;
    u32 dart1_cmd, dart1_tcr;
    unsigned int valid = 0, i;
    int err;

    if (!armed) {
        pr_info("n71-s3e-phy-ro: UNARMED no MMIO access\n");
        return 0;
    }
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -EPERM;
    guard = of_find_node_by_path(N71_RESEARCH_GUARD);
    err = guard && of_device_is_compatible(
        guard, "apple,s8000-pcie-research-blocked") &&
        of_property_read_bool(guard, "research,hardware-activation-blocked");
    of_node_put(guard);
    if (!err)
        return -EPERM;
    wlan = pci_get_device(0x14e4, 0x43a3, NULL);
    if (!wlan)
        return -ENODEV;
    pci_dev_put(wlan);
    node = of_find_node_by_path(N71_PMGR_PATH);
    if (!node)
        return -ENODEV;
    pmgr = syscon_node_to_regmap(node);
    of_node_put(node);
    if (IS_ERR(pmgr))
        return PTR_ERR(pmgr);
    if (regmap_read(pmgr, 0x80310, &pcie) ||
        regmap_read(pmgr, 0x80320, &p0) ||
        regmap_read(pmgr, 0x80328, &p1))
        return -EIO;
    if (ACTUAL(pcie) != 15 || ACTUAL(p0) != 0 ||
        ACTUAL(p1) != 15 || (p0 & 0xf) != 0)
        return -EBUSY;
    root = ioremap(N71_ROOT_PHYS, 0x1000);
    phy = ioremap(N71_PHY_PHYS, 0x4000);
    dart1 = ioremap(N71_DART1_PHYS, 0x1000);
    if (!root || !phy || !dart1) {
        err = -ENOMEM;
        goto out;
    }
    original_root_p0 = readl((u8 __iomem *)root + 0x16c);
    original_root_p1 = readl((u8 __iomem *)root + 0x1ac);
    dart1_cmd = readl((u8 __iomem *)dart1 + 0x00);
    dart1_tcr = readl((u8 __iomem *)dart1 + 0x0c);
    if (original_root_p0 != 0 || original_root_p1 != 1 ||
        dart1_cmd == 0xffffffffU || dart1_tcr == 0xffffffffU) {
        err = -EPERM;
        goto out;
    }
    for (i = 0; i < ARRAY_SIZE(n71_stock_phy_offsets); ++i) {
        phy_values[i] = readl((u8 __iomem *)phy + n71_stock_phy_offsets[i]);
        if (phy_values[i] != 0xffffffffU)
            ++valid;
    }
    root_p0 = readl((u8 __iomem *)root + 0x16c);
    root_p1 = readl((u8 __iomem *)root + 0x1ac);
    if (root_p0 != original_root_p0 || root_p1 != original_root_p1) {
        err = -EUCLEAN;
        goto out;
    }
    pr_info("n71-s3e-phy-ro: REAL_PHY_STOCK_REGISTERS_READ_ONLY count=%zu valid_non_ff=%u root0=%08x root1=%08x wlan_dart_cmd=%08x wlan_dart_tcr=%08x\n",
        ARRAY_SIZE(n71_stock_phy_offsets), valid, root_p0, root_p1,
        dart1_cmd, dart1_tcr);
    for (i = 0; i < ARRAY_SIZE(n71_stock_phy_offsets); ++i)
        pr_info("n71-s3e-phy-ro: OFFSET_%04x value=%08x; verified_stock_RMW_read_only no_clock_writes\n",
            n71_stock_phy_offsets[i], phy_values[i]);
    err = valid ? 0 : -EIO;
out:
    if (dart1)
        iounmap(dart1);
    if (phy)
        iounmap(phy);
    if (root)
        iounmap(root);
    if (err)
        pr_err("n71-s3e-phy-ro: READ_ONLY_DIAGNOSTIC_REJECTED rc=%d; no hardware writes\n",err);
    return err;
}
static void __exit n71_stock_phy_ro_exit(void)
{
    pr_info("n71-s3e-phy-ro: UNLOADED no device or power state changed\n");
}
module_init(n71_stock_phy_ro_init);
module_exit(n71_stock_phy_ro_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 S8000 stock Apple PCIe shared PHY tunable register visibility read-only");
