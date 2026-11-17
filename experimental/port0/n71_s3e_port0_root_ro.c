// SPDX-License-Identifier: GPL-2.0
/* N71/S8000 stock-verified shared Apple PCIe root MMIO single read-only sample.
 * Root is already powered by the ACTIVE WiFi PCIe link1.
 * Port0 is left POWERED OFF. No DART, no PERST, no PCI scan, no DMA.
 * Apple stock IORegistry resource index 9: 0x600000000 / 0x8000.
 * Selector offsets from original Apple S800xPCIe root methods:
 * port0 0x140/154/164/16c; port1 0x180/194/1a4/1ac.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/io.h>
#include <linux/err.h>
#include <linux/regmap.h>
#include <linux/mfd/syscon.h>
#define ROOT_MMIO 0x600000000ULL
#define PMGR "/soc/power-management@20e000000"
#define GUARD "/soc/pcie-port1-preflight@602000000"
#define ACTUAL(x) (((x)>>4)&15U)
static bool armed;
module_param(armed,bool,0400);
static int __init n71_p0_read_init(void)
{
    struct device_node *node,*guard;
    struct regmap *pm;
    void __iomem *root;
    struct pci_dev *wifi;
    u32 p0,p1,p2,p3,main;
    u32 shared,p0_id2,p0_id3,p0_id4,p0_id5,p1_id2,p1_id5;
    int ret;
    if (!armed) { pr_info("n71-s3e-root-ro: UNARMED no physical MMIO access\n"); return 0; }
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000")) return -EPERM;
    guard=of_find_node_by_path(GUARD);
    ret=guard && of_device_is_compatible(guard,"apple,s8000-pcie-research-blocked")
        && of_property_read_bool(guard,"research,hardware-activation-blocked");
    of_node_put(guard);
    if (!ret) return -EPERM;
    wifi=pci_get_device(0x14e4,0x43a3,NULL);
    if (!wifi) return -EPERM;
    pci_dev_put(wifi);
    node=of_find_node_by_path(PMGR);
    if (!node) return -ENODEV;
    pm=syscon_node_to_regmap(node);
    of_node_put(node);
    if (IS_ERR(pm)) return PTR_ERR(pm);
    if ((ret=regmap_read(pm,0x80310,&main)) ||
        (ret=regmap_read(pm,0x80320,&p0)) ||
        (ret=regmap_read(pm,0x80328,&p1)) ||
        (ret=regmap_read(pm,0x80330,&p2)) ||
        (ret=regmap_read(pm,0x80338,&p3))) return ret;
    if (ACTUAL(main)!=15 || ACTUAL(p0)!=0 || ACTUAL(p1)!=15 ||
        ACTUAL(p2)!=0 || ACTUAL(p3)!=0) return -EBUSY;
    root=ioremap(ROOT_MMIO,0x1000);
    if (!root) return -ENOMEM;
    shared=readl((u8 __iomem *)root+0x2c);
    p0_id2=readl((u8 __iomem *)root+0x140);
    p0_id3=readl((u8 __iomem *)root+0x154);
    p0_id4=readl((u8 __iomem *)root+0x164);
    p0_id5=readl((u8 __iomem *)root+0x16c);
    p1_id2=readl((u8 __iomem *)root+0x180);
    p1_id5=readl((u8 __iomem *)root+0x1ac);
    iounmap(root);
    if (shared==0xffffffffU || p0_id2==0xffffffffU || p1_id5==0xffffffffU)
        return -EIO;
    pr_info("n71-s3e-root-ro: PHYSICAL_ROOT_REG_READ_PASS shared_status=%08x p0_id2=%08x p0_id3=%08x p0_id4=%08x p0_id5=%08x p1_id2=%08x p1_id5=%08x\n",
        shared,p0_id2,p0_id3,p0_id4,p0_id5,p1_id2,p1_id5);
    pr_info("n71-s3e-root-ro: P0_LINK_STATUS_BIT0=%u P1_LINK_STATUS_BIT0=%u; no writes/PCIe reset/DART/DMA/NVMe\n",
        p0_id5&1U,p1_id5&1U);
    return 0;
}
static void __exit n71_p0_read_exit(void) { }
module_init(n71_p0_read_init);
module_exit(n71_p0_read_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("S8000 stock Apple PCIe shared root port0/1 physical status read only");
