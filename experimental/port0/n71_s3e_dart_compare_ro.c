// SPDX-License-Identifier: GPL-2.0
/*
 * N71 Samsung S8000: compare active WLAN DART1 with inactive storage DART0
 * and storage NVMMU0 using strictly read-only MMIO. No MMIO writes, PCI
 * reconfiguration, PMGR changes, storage commands or endpoint reset.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/errno.h>

#define N71_DART0     0x601008000ULL
#define N71_DART1     0x602008000ULL
#define N71_NVMMU0    0x601004000ULL
#define N71_PORT0     0x601000000ULL
#define N71_ROOT      0x600000000ULL

static bool armed;
module_param(armed, bool, 0400);
MODULE_PARM_DESC(armed, "default false; only physical N71 read-only register comparison");

static u32 sample(void __iomem *base, unsigned int offset)
{
    return readl((u8 __iomem *)base + offset);
}
static int __init n71_compare_init(void)
{
    struct pci_dev *wlan;
    struct device_node *guard;
    void __iomem *dart0=NULL, *dart1=NULL, *nvmmu=NULL, *port0=NULL, *root=NULL;
    u32 wifi_cmd, wifi_tcr, wifi_fault;
    u32 storage_cmd, storage_tcr, storage_fault, nv_ctrl, nv_init;
    u32 port0_fifo, p0_id5, p1_id5;
    int ret=0;

    if (!armed) {
        pr_info("n71-s3e-compare: UNARMED; no MMIO\n");
        return 0;
    }
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -EPERM;
    guard=of_find_node_by_path("/soc/pcie-port1-preflight@602000000");
    if (!guard || !of_device_is_compatible(guard,
          "apple,s8000-pcie-research-blocked") ||
        !of_property_read_bool(guard,"research,hardware-activation-blocked")) {
        of_node_put(guard);
        return -EPERM;
    }
    of_node_put(guard);
    wlan=pci_get_device(0x14e4,0x43a3,NULL);
    if (!wlan) return -ENODEV;
    pci_dev_put(wlan);

    root=ioremap(N71_ROOT,0x1000);
    dart1=ioremap(N71_DART1,0x1000);
    dart0=ioremap(N71_DART0,0x1000);
    nvmmu=ioremap(N71_NVMMU0,0x1000);
    port0=ioremap(N71_PORT0,0x1000);
    if (!root || !dart1 || !dart0 || !nvmmu || !port0) {
        ret=-ENOMEM;
        goto out;
    }
    p0_id5=sample(root,0x12c);
    p1_id5=sample(root,0x1ac);
    if (p0_id5 != 0 || p1_id5 != 1) {
        ret=-EBUSY;
        goto out;
    }
    wifi_cmd=sample(dart1,0x00);
    wifi_tcr=sample(dart1,0x0c);
    wifi_fault=sample(dart1,0x10);
    storage_cmd=sample(dart0,0x00);
    storage_tcr=sample(dart0,0x0c);
    storage_fault=sample(dart0,0x10);
    nv_ctrl=sample(nvmmu,0x00);
    nv_init=sample(nvmmu,0x04);
    port0_fifo=sample(port0,0x22c);
    pr_info("n71-s3e-compare: NATIVE_WIFI_DART1 cmd=%08x tcr=%08x fault=%08x\n",
            wifi_cmd,wifi_tcr,wifi_fault);
    pr_info("n71-s3e-compare: STORAGE_DART0 cmd=%08x tcr=%08x fault=%08x\n",
            storage_cmd,storage_tcr,storage_fault);
    pr_info("n71-s3e-compare: STORAGE_NVMMU0 ctrl=%08x init=%08x port0_fifo=%08x\n",
            nv_ctrl,nv_init,port0_fifo);
    if (wifi_cmd==0xffffffffU || wifi_tcr==0xffffffffU) {
        pr_err("n71-s3e-compare: WLAN DART1 register aperture unexpectedly invalid\n");
        ret=-EIO;
    } else if (storage_cmd==0xffffffffU && storage_tcr==0xffffffffU &&
               nv_ctrl==0xffffffffU && port0_fifo==0xffffffffU) {
        pr_info("n71-s3e-compare: DART1_VALID_STORAGE_APERTURES_INACCESSIBLE_PASS; no writes\n");
    } else {
        pr_info("n71-s3e-compare: STORAGE_APERTURES_CHANGED; investigation only, NO DMA\n");
    }
out:
    if (port0) iounmap(port0);
    if (nvmmu) iounmap(nvmmu);
    if (dart0) iounmap(dart0);
    if (dart1) iounmap(dart1);
    if (root) iounmap(root);
    return ret;
}
static void __exit n71_compare_exit(void) {}
module_init(n71_compare_init);
module_exit(n71_compare_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71/S8000 read-only DART1 vs DART0/NVMMU0 register comparison");
