// SPDX-License-Identifier: GPL-2.0
/*
 * N71 S8000 storage port0: owner-supervised, one-shot 25ms PMGR power lease.
 *
 * EXACTLY ONE hardware action when armed: request genpd "pcie_link0" ON
 * using the Linux PMGR driver; synchronously release it after 25ms.
 * NO endpoint PERST, NO PCIe bridge transactions, NO DART0 changes,
 * NO NVMe commands, NO filesystem, NAND, iOS partition, or DMA writes.
 * The code never creates a PCI device and it never resets an endpoint.
 *
 * This uses of_genpd_add_device with the provider *node pointer*, because
 * the live S8000 DT does not assign a phandle to power-controller@80320.
 * No DT overlay is needed; no shared DT properties are altered.
 */
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/pci.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/regmap.h>
#include <linux/mfd/syscon.h>
#include <linux/bits.h>

#define PWR_BASE "/soc/power-management@20e000000"
#define ROOT_PCI_GUARD "/soc/pcie-port1-preflight@602000000"
#define PHANDLE_ROOT 0x2c
#define PORT0_OFF 0x80320U
#define PORT1_OFF 0x80328U
#define ROOT_OFF 0x80310U
#define AUX_OFF 0x80318U
#define REF_OFF 0x80148U
#define PORT2_OFF 0x80330U
#define PORT3_OFF 0x80338U
#define ROOT_COMMON_PHYS 0x600000000ULL
#define DWELL_MS 25U
#define ACTUAL(r) (((r) >> 4) & 15U)
#define TARGET(r) ((r) & 15U)

static bool armed;
static bool sample_root;
module_param(armed, bool, 0400);
module_param(sample_root, bool, 0400);
MODULE_PARM_DESC(armed, "requires owner authorization and encrypted iOS backup; default inert");
MODULE_PARM_DESC(sample_root, "read-only stock-proven S8000 PCIe root status during power lease");

static struct platform_device *n71_consumer;
static bool n71_bound;
static bool n71_pm_enabled;
static bool n71_unreleased;
static struct device_node *n71_p0;

static struct {
    u32 root, ref, aux, p0, p1, p2, p3;
} baseline;

static int n71_snapshot(struct regmap *map, bool pre)
{
    u32 root, ref, aux, p0, p1, p2, p3;
    int r;

#define READ_REG(off, variable) do { r = regmap_read(map, (off), &(variable)); if (r) return r; } while (0)
    READ_REG(ROOT_OFF, root);
    READ_REG(REF_OFF, ref);
    READ_REG(AUX_OFF, aux);
    READ_REG(PORT0_OFF, p0);
    READ_REG(PORT1_OFF, p1);
    READ_REG(PORT2_OFF, p2);
    READ_REG(PORT3_OFF, p3);
#undef READ_REG

    if (pre) {
        baseline.root=root; baseline.ref=ref; baseline.aux=aux;
        baseline.p0=p0; baseline.p1=p1; baseline.p2=p2; baseline.p3=p3;
        pr_info("n71-s3e-p0: PRE: p0 actual=%u target=%u p1=%u root=%u aux=%u ref=%u p2=%u p3=%u\n",
                ACTUAL(p0), TARGET(p0), ACTUAL(p1), ACTUAL(root),
                ACTUAL(aux), ACTUAL(ref), ACTUAL(p2), ACTUAL(p3));
        if (ACTUAL(p0)!=0 || TARGET(p0)!=0 ||
            ACTUAL(p1)!=15 || ACTUAL(root)!=15 ||
            ACTUAL(aux)!=15 || ACTUAL(ref)!=15 ||
            ACTUAL(p2)!=0 || ACTUAL(p3)!=0)
            return -EBUSY;
    } else {
        pr_info("n71-s3e-p0: POST: p0 actual=%u target=%u p1=%u root=%u aux=%u ref=%u p2=%u p3=%u\n",
                ACTUAL(p0), TARGET(p0), ACTUAL(p1), ACTUAL(root),
                ACTUAL(aux), ACTUAL(ref), ACTUAL(p2), ACTUAL(p3));
        if (ACTUAL(p0)!=0 || TARGET(p0)!=0 ||
            root!=baseline.root || ref!=baseline.ref ||
            aux!=baseline.aux || p1!=baseline.p1 ||
            p2!=baseline.p2 || p3!=baseline.p3)
            return -EUCLEAN;
    }
    return 0;
}

static bool n71_board_gate(void)
{
    struct device_node *guard;
    struct pci_dev *wlan;
    bool okay;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return false;

    guard=of_find_node_by_path(ROOT_PCI_GUARD);
    okay=guard && of_device_is_compatible(guard,
             "apple,s8000-pcie-research-blocked") &&
         of_property_read_bool(guard,"research,hardware-activation-blocked");
    of_node_put(guard);
    if (!okay)
        return false;

    wlan=pci_get_device(0x14e4,0x43a3,NULL);
    okay=!!wlan;
    if (wlan) pci_dev_put(wlan);
    return okay;
}

static bool n71_provider_gate(struct device_node *node)
{
    struct device_node *parent, *root;
    const char *label;
    u32 offset, root_ph;
    bool valid;

    if (!node || !of_device_is_compatible(node,"apple,s8000-pmgr-pwrstate") ||
        of_property_read_string(node,"label",&label) ||
        strcmp(label,"pcie_link0") ||
        of_property_read_u32(node,"reg",&offset) || offset!=PORT0_OFF ||
        of_property_read_u32(node,"#power-domain-cells",&offset) || offset!=0 ||
        node->phandle)
        return false;

    parent=of_parse_phandle(node,"power-domains",0);
    root=of_find_node_by_path(PWR_BASE "/power-controller@80310");
    valid=parent && root && parent==root &&
          !of_property_read_u32(root,"phandle",&root_ph) &&
          root_ph==PHANDLE_ROOT;
    of_node_put(parent);
    of_node_put(root);
    return valid;
}

static void n71_safe_detach(void)
{
    if (!n71_consumer || IS_ERR(n71_consumer))
        return;
    if (n71_unreleased)
        return; /* do not detach a live genpd consumer on error */
    if (n71_pm_enabled) {
        pm_runtime_disable(&n71_consumer->dev);
        n71_pm_enabled=false;
    }
    if (n71_bound) {
        pm_genpd_remove_device(&n71_consumer->dev);
        n71_bound=false;
    }
    platform_device_unregister(n71_consumer);
    n71_consumer=NULL;
}

static int __init n71_port0_init(void)
{
    struct regmap *map;
    void __iomem *root_mmio=NULL;
    struct of_phandle_args spec={};
    struct device_node *parent;
    u32 inside;
    int ret, rel, check;
    if (!armed) {
        pr_info("n71-s3e-p0: UNARMED inert, no PMGR access\n");
        return 0;
    }
    if (!n71_board_gate())
        return -EPERM;
    n71_p0=of_find_node_by_path(PWR_BASE "/power-controller@80320");
    if (!n71_provider_gate(n71_p0)) {
        ret=-EPERM;
        goto out_put;
    }
    parent=of_get_parent(n71_p0);
    map=syscon_node_to_regmap(parent);
    of_node_put(parent);
    if (IS_ERR(map)) {
        ret=PTR_ERR(map);
        goto out_put;
    }
    ret=n71_snapshot(map,true);
    if (ret) {
        pr_err("n71-s3e-p0: PREFAIL rc=%d, hardware untouched\n",ret);
        goto out_put;
    }
    if (sample_root) {
        root_mmio=ioremap(ROOT_COMMON_PHYS,0x1000);
        if (!root_mmio) { ret=-ENOMEM; goto out_put; }
    }
    n71_consumer=platform_device_register_simple("n71-s3e-p0-microlease",
                    PLATFORM_DEVID_NONE,NULL,0);
    if (IS_ERR(n71_consumer)) {
        ret=PTR_ERR(n71_consumer); n71_consumer=NULL; goto out_put;
    }
    spec.np=n71_p0; spec.args_count=0;
    ret=of_genpd_add_device(&spec,&n71_consumer->dev);
    if (ret) {
        pr_err("n71-s3e-p0: attach rejected rc=%d\n",ret);
        goto cleanup;
    }
    n71_bound=true;
    pm_runtime_enable(&n71_consumer->dev);
    n71_pm_enabled=true;
    ret=pm_runtime_resume_and_get(&n71_consumer->dev);
    if (ret) {
        pr_err("n71-s3e-p0: PMGR power-on failed rc=%d\n",ret);
        if (regmap_read(map,PORT0_OFF,&inside) ||
            ACTUAL(inside)!=0 || TARGET(inside)!=0)
            n71_unreleased=true;
        goto cleanup;
    }
    ret=regmap_read(map,PORT0_OFF,&inside);
    if (ret || ACTUAL(inside)!=15) {
        pr_err("n71-s3e-p0: power-on did not show actual=15 rc=%d\n",ret);
        if (!ret) ret=-EIO;
    } else {
        pr_info("n71-s3e-p0: PHYSICAL_LINK0_POWER_ON actual=15 target=%u dwell=25ms endpoint_reset_unchanged=yes no_DART_no_DMA_no_NVMe\n",
            TARGET(inside));
        msleep(DWELL_MS);
        if (root_mmio) {
            u32 p0_link=readl((u8 __iomem *)root_mmio+0x12c);
            u32 p1_link=readl((u8 __iomem *)root_mmio+0x1ac);
            u32 shared=readl((u8 __iomem *)root_mmio+0x2c);
            pr_info("n71-s3e-p0: PHYSICAL_ROOT_DURING_P0_POWER p0_id5=%08x p0_bit0=%u p1_id5=%08x p1_bit0=%u shared=%08x no_pcie_reset_no_dma\n",
                p0_link,p0_link&1U,p1_link,p1_link&1U,shared);
        }
    }
    rel=pm_runtime_put_sync_suspend(&n71_consumer->dev);
    if (rel<0) {
        n71_unreleased=true;
        pr_err("n71-s3e-p0: POWER_RELEASE_ERROR rc=%d, consumer must remain pinned\n",rel);
        ret=rel;
        goto cleanup;
    }
    check=n71_snapshot(map,false);
    if (check) {
        n71_unreleased=true;
        ret=check;
        pr_err("n71-s3e-p0: POSTFAIL rc=%d, leave attached as safety fence\n",ret);
        goto cleanup;
    }
    if (!ret)
        pr_info("n71-s3e-p0: PHYSICAL_POWER_ON_OFF_PASS p0_actual=0 wifi_p1_preserved=yes p2_p3_preserved=yes\n");

cleanup:
    if (n71_unreleased) {
        /* A safety failure retains the device association (no unsafe unload). */
        __module_get(THIS_MODULE);
        pr_err("n71-s3e-p0: QUARANTINED module pinned; inspect power state before next boot\n");
    } else {
        n71_safe_detach();
    }
out_put:
    if (root_mmio) iounmap(root_mmio);
    of_node_put(n71_p0);n71_p0=NULL;
    /* Keep module resident if pin/quarantine must survive error. */
    if (n71_unreleased)
        return 0;
    return ret;
}

static void __exit n71_port0_exit(void)
{
    if (n71_unreleased) {
        pr_err("n71-s3e-p0: refuse unload of quarantined PMGR consumer\n");
        return;
    }
    n71_safe_detach();
}

module_init(n71_port0_init);
module_exit(n71_port0_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Apple S8000 port0 link power microlease, no NAND/DMA/PCI accesses");
