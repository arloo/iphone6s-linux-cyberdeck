// SPDX-License-Identifier: GPL-2.0
/*
 * N71 Samsung S8000 Apple PCIe port1 register +0x210 comparator.
 *
 * Read one original Apple port-local register on already-active WLAN,
 * to contextualize stock port vslot1504 conditional read/write.
 * NO WRITE to MMIO, PMGR, PCIe config, GPIO, DART, NVMMU or NAND.
 * Storage port0 must remain powered OFF. Wi-Fi link1 must remain ON.
 * One owner-armed run only. No link reset or train.
 */
#include <linux/init.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/pci.h>
#include <linux/err.h>
#include <linux/regmap.h>
#include <linux/mfd/syscon.h>

#define PMGR_PATH "/soc/power-management@20e000000"
#define PCIE_GUARD "/soc/pcie-port1-preflight@602000000"
#define P1_MMIO 0x602000000ULL
#define ROOT_MMIO 0x600000000ULL
#define P1_WINDOW 0x4000U
#define ROOT_WINDOW 0x1000U
#define ACTUAL(v) (((v)>>4)&0xfu)
#define TARGET(v) ((v)&0xfu)
static bool armed;
module_param(armed,bool,0400);
MODULE_PARM_DESC(armed,"real N71/S8000 read-only register0x210 on existing WLAN port1");

static int __init n71_p1_210_ro_init(void)
{
    struct device_node *g=NULL,*p=NULL;
    struct pci_dev *wlan=NULL;
    struct regmap *pm=NULL;
    void __iomem *root=NULL,*port=NULL;
    u32 main,ref,aux,p0,p1,p2,p3,r1id5,p1ctl,p1stat,reg210;
    int ret=0;
    if (!armed) {
        pr_info("n71-p1-0210-ro: UNARMED no register accesses\n");
        return 0;
    }
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -EPERM;
    g=of_find_node_by_path(PCIE_GUARD);
    if (!g || !of_device_is_compatible(g,"apple,s8000-pcie-research-blocked") ||
        !of_property_read_bool(g,"research,hardware-activation-blocked")) {
        of_node_put(g);
        return -EPERM;
    }
    of_node_put(g);
    wlan=pci_get_device(0x14e4,0x43a3,NULL);
    if (!wlan) return -ENODEV;
    pci_dev_put(wlan);
    p=of_find_node_by_path(PMGR_PATH);
    if (!p) return -ENODEV;
    pm=syscon_node_to_regmap(p);
    of_node_put(p);
    if (IS_ERR(pm)) return PTR_ERR(pm);
#define R(off,var) do{ret=regmap_read(pm,(off),&(var));if(ret)return ret;}while(0)
    R(0x80310,main);
    R(0x80318,aux);
    R(0x80148,ref);
    R(0x80320,p0);
    R(0x80328,p1);
    R(0x80330,p2);
    R(0x80338,p3);
#undef R
    if (ACTUAL(main)!=15 || ACTUAL(ref)!=15 || ACTUAL(aux)!=15 ||
        TARGET(p0)!=0 || ACTUAL(p0)!=0 ||
        ACTUAL(p1)!=15 || ACTUAL(p2)!=0 || ACTUAL(p3)!=0)
        return -EBUSY;
    root=ioremap(ROOT_MMIO,ROOT_WINDOW);
    if (!root) return -ENOMEM;
    r1id5=readl((u8 __iomem *)root+0x1ac);
    iounmap(root);
    if (r1id5!=1) return -EPERM;
    port=ioremap(P1_MMIO,P1_WINDOW);
    if (!port) return -ENOMEM;
    /* Source-proven stock port-local 0x210: one single sample.
     * No automatic polling/reads after this, no corresponding write.
     */
    reg210=readl((u8 __iomem *)port+0x210);
    p1ctl=readl((u8 __iomem *)port+0x80);
    p1stat=readl((u8 __iomem *)port+0x88);
    iounmap(port);
    pr_info("n71-p1-0210-ro: STOCK_LOCAL_0210_READ_ONLY wifi_port1=%08x ctl80=%08x status88=%08x p1root_id5=%08x storage_port0_OFF=yes\n",
        reg210,p1ctl,p1stat,r1id5);
    if (reg210==0xffffffffu || p1stat==0xffffffffu) {
        pr_err("n71-p1-0210-ro: PHYSICAL_READ_REJECTED_INVALID_MMIO\n");
        return -EIO;
    }
    return 0;
}
static void __exit n71_p1_210_ro_exit(void)
{
    pr_info("n71-p1-0210-ro: unloaded; no physical state changed\n");
}
module_init(n71_p1_210_ro_init);
module_exit(n71_p1_210_ro_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71/S8000 real active WLAN root port1 local 0x210 register one-shot read-only");
