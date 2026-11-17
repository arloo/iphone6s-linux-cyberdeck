// SPDX-License-Identifier: GPL-2.0
/* Read-only N71/S8000 stock Apple PCIe shared root port-local 0x4020.
 *
 * Genuine S800xPCIe root vslot 2040 computes offset 0x4020+0x40*port
 * and writes value 3. This module does NOT perform that write.
 * Port0 must be OFF and native port1 WLAN must be fully operational.
 * Sample port0, WLAN port1 and baseband port2 registers at identical
 * offsets, plus the existing root ID5 link status for comparison.
 * No clock/PHY/PERST/power/DART/NVMMU/DMA/NAND changes.
 */
#include <linux/init.h>
#include <linux/errno.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/io.h>
#include <linux/err.h>
#include <linux/regmap.h>
#include <linux/mfd/syscon.h>
#define ROOT_MMIO 0x600000000ULL
#define ROOT_SIZE 0x8000U
#define PMGR "/soc/power-management@20e000000"
#define GUARD "/soc/pcie-port1-preflight@602000000"
#define ACTUAL(x) (((x)>>4)&15U)
static bool armed;
module_param(armed,bool,0400);
MODULE_PARM_DESC(armed,"explicit live N71/S8000 read-only root register sample");
static int __init n71_root4020_init(void)
{
    struct device_node *node,*guard;
    struct regmap *pm;
    void __iomem *root;
    struct pci_dev *wifi;
    u32 p0,p1,p2,p3,main,aux,ref;
    u32 r0,r1,r2,r3,id5p0,id5p1,shared;
    int ret;
    if (!armed) {
        pr_info("n71-s3e-root4020-ro: UNARMED no MMIO\n");
        return 0;
    }
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -EPERM;
    guard=of_find_node_by_path(GUARD);
    ret=guard &&
        of_device_is_compatible(guard,"apple,s8000-pcie-research-blocked") &&
        of_property_read_bool(guard,"research,hardware-activation-blocked");
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
#define READ_P(off,v) do {ret=regmap_read(pm,(off),&(v));if(ret)return ret;} while(0)
    READ_P(0x80310,main);
    READ_P(0x80320,p0);
    READ_P(0x80328,p1);
    READ_P(0x80330,p2);
    READ_P(0x80338,p3);
    READ_P(0x80318,aux);
    READ_P(0x80148,ref);
#undef READ_P
    if (ACTUAL(main)!=15 || (p0&0xff)!=0 ||
        ACTUAL(p1)!=15 || ACTUAL(p2)!=0 || ACTUAL(p3)!=0 ||
        ACTUAL(aux)!=15 || ACTUAL(ref)!=15)
        return -EBUSY;
    root=ioremap(ROOT_MMIO,ROOT_SIZE);
    if (!root) return -ENOMEM;
    r0=readl((u8 __iomem *)root+0x4020);
    r1=readl((u8 __iomem *)root+0x4060);
    r2=readl((u8 __iomem *)root+0x40a0);
    r3=readl((u8 __iomem *)root+0x40e0);
    id5p0=readl((u8 __iomem *)root+0x16c);
    id5p1=readl((u8 __iomem *)root+0x1ac);
    shared=readl((u8 __iomem *)root+0x2c);
    iounmap(root);
    pr_info("n71-s3e-root4020-ro: PHYSICAL_PORT_CONTROL_READ_ONLY p0_4020=%08x wifi1_4060=%08x baseband2_40a0=%08x port3_40e0=%08x\n",
        r0,r1,r2,r3);
    pr_info("n71-s3e-root4020-ro: PHYSICAL_LINK_STATUS p0_id5=%08x p1_id5=%08x shared=%08x no_register_writes\n",
        id5p0,id5p1,shared);
    if (r1==0xffffffffU || id5p1!=1U)
        return -EIO;
    return 0;
}
static void __exit n71_root4020_exit(void)
{
    pr_info("n71-s3e-root4020-ro: module removed, never changed HW\n");
}
module_init(n71_root4020_init);
module_exit(n71_root4020_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71/S8000 original Apple PCIe root port0/1 control register read only");
