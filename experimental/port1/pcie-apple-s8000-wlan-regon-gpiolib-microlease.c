// SPDX-License-Identifier: GPL-2.0
/* N71 Samsung A9: Native GPIOLIB PMU GPIO10 WLAN REG_ON 25ms microlease.
 * Does NOT touch unrelated PMIC outputs (BT PMIC GPIO8), NAND, PERST,
 * PCIe controller, any PCIe power domain, DART, DMA or physical MMIO write.
 * GPIO output readback is LOGICAL (register), not proof of pin voltage.
 */
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/gpio/consumer.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include "n71-native-wlan-reg-on-25ms-blob-20261113.h"

#define N71_ORIGINAL_PCIE_BLOCK "/soc/pcie-port1-preflight@602000000"
#define N71_GPIO10_PROVIDER "/soc/i2c@20a110000/pmic@74/gpio@900"
#define N71_NATIVE_WLAN_NODE "/soc/n71-native-wlan-reg-on-microlease"
#define N71_AP_PINCTRL_MMIO 0x20f100000ULL
#define N71_AP_PINCTRL_BYTES 0x1000

static bool armed;
module_param(armed, bool, 0400);
MODULE_PARM_DESC(armed, "owner-supervised GPIO10 WLAN REG_ON 25ms, default false");
static bool probed;
static int probe_result=-EINPROGRESS;
static int overlay_id;
static bool overlay_present;

static bool n71_original_guard_ok(void)
{
    struct device_node *block, *provider;
    bool yes;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return false;
    block=of_find_node_by_path(N71_ORIGINAL_PCIE_BLOCK);
    yes=block && of_device_is_compatible(block,
                "apple,s8000-pcie-research-blocked") &&
        of_property_read_bool(block,"research,hardware-activation-blocked");
    of_node_put(block);
    if (!yes) return false;
    provider=of_find_node_by_path(N71_GPIO10_PROVIDER);
    yes=provider && provider->phandle==0x09 &&
        of_device_is_compatible(provider,"apple,antigua-pmic-gpio") &&
        of_property_read_bool(provider,"gpio-controller");
    of_node_put(provider);
    return yes;
}

static bool n71_gpio_reference_matches(struct device_node *np)
{
    struct of_phandle_args parsed={0};
    struct device_node *expected;
    bool okay=false;
    int ret;

    if (!np || !of_device_is_available(np) ||
        !of_device_is_compatible(np,
                  "research,n71-s8000-native-wlan-regon-gpio10-microlease") ||
        !of_property_read_bool(np,"research,pmic-gpio10-only"))
        return false;
    ret=of_parse_phandle_with_args(np,"wlan-reg-on-gpios",
                                   "#gpio-cells",0,&parsed);
    if (ret) return false;
    expected=of_find_node_by_path(N71_GPIO10_PROVIDER);
    okay=expected && parsed.np==expected && parsed.args_count==2 &&
         parsed.args[0]==10 && parsed.args[1]==0;
    of_node_put(expected);
    of_node_put(parsed.np);
    return okay;
}

static int n71_wlan_native_probe(struct platform_device *pdev)
{
    struct gpio_desc *reg_on;
    void __iomem *ap;
    u32 perst=0,clkreq=0,perst_after=0,clkreq_after=0;
    int before=-1,high=-1,low=-1;
    int result=-EPERM;

    /* A failed platform probe must NEVER repeat an armed pulse. */
    if (probed)
        return -ENODEV;
    probed=true;
    probe_result=-EPERM;
    if (!n71_original_guard_ok() ||
        !n71_gpio_reference_matches(pdev->dev.of_node) ||
        pdev->dev.pm_domain)
        return -EPERM;
    if (!armed) {
        pr_info("n71-native-wlan-regon: unarmed; GPIO10 not requested, PMU unchanged\n");
        probe_result=0;
        return -ENODEV;
    }
    ap=ioremap(N71_AP_PINCTRL_MMIO,N71_AP_PINCTRL_BYTES);
    if (!ap)
        return -ENOMEM;
    perst=readl((u8 __iomem *)ap+4*161);
    clkreq=readl((u8 __iomem *)ap+4*165);
    if (perst!=0x00072200 || clkreq!=0x00076a21) {
        pr_err("n71-native-wlan-regon: AP GPIO guard mismatch perst=%08x clkreq=%08x\n",perst,clkreq);
        goto unmap;
    }
    /* This requests EXACTLY PMU GPIO10, only if no other consumer owns it.
     * The pmic driver refuses to change the firmware-configured pin mode. */
    reg_on=gpiod_get(&pdev->dev,"wlan-reg-on",GPIOD_OUT_LOW);
    if (IS_ERR(reg_on)) {
        result=PTR_ERR(reg_on);
        goto unmap;
    }
    before=gpiod_get_value_cansleep(reg_on);
    if (before!=0) {
        result=before<0?before:-EPERM;
        goto restore;
    }
    gpiod_set_value_cansleep(reg_on,1);
    high=gpiod_get_value_cansleep(reg_on);
    /* If the high read fails, LOW is still mandatory. No unbounded wait. */
    if (high==1)
        msleep(25);
restore:
    gpiod_set_value_cansleep(reg_on,0);
    low=gpiod_get_value_cansleep(reg_on);
    perst_after=readl((u8 __iomem *)ap+4*161);
    clkreq_after=readl((u8 __iomem *)ap+4*165);
    pr_info("n71-native-wlan-regon: LOGICAL_GPIO10 before=%d high=%d after=%d AP_PERST=%08x AP_CLKREQ=%08x\n",
        before,high,low,perst_after,clkreq_after);
    if (before==0 && high==1 && low==0 &&
        perst_after==perst && clkreq_after==clkreq) {
        result=0;
        pr_info("n71-native-wlan-regon: native GPIOLIB exclusive GPIO10 pulse complete, restored LOW; not a voltage measurement\n");
    } else if (!result)
        result=-EIO;
    gpiod_put(reg_on);
unmap:
    iounmap(ap);
    probe_result=result;
    return -ENODEV; /* no lasting binding */
}

static const struct of_device_id n71_match[]={
    { .compatible="research,n71-s8000-native-wlan-regon-gpio10-microlease" },
    { }
};
static struct platform_driver n71_native_driver={
    .probe=n71_wlan_native_probe,
    .driver={.name="n71-native-wlan-regon", .of_match_table=n71_match},
};

static int __init n71_native_init(void)
{
    struct device_node *prior;
    int err,cleanup;

    if (!n71_original_guard_ok() ||
        sizeof(n71_native_wlan_gpio10_dtbo)!=n71_native_wlan_gpio10_dtbo_len)
        return -ENODEV;
    prior=of_find_node_by_path(N71_NATIVE_WLAN_NODE);
    if (prior) {of_node_put(prior);return -EEXIST;}
    err=of_overlay_fdt_apply(n71_native_wlan_gpio10_dtbo,
                              sizeof(n71_native_wlan_gpio10_dtbo),
                              &overlay_id,NULL);
    if (err) return err;
    overlay_present=true;
    err=platform_driver_register(&n71_native_driver);
    if (!err)platform_driver_unregister(&n71_native_driver);
    if (!err && (!probed || probe_result))
        err=probed ? probe_result : -ENODEV;
    cleanup=of_overlay_remove(&overlay_id);
    if (!cleanup) overlay_present=false;
    if (cleanup) {
        pr_err("n71-native-wlan-regon: overlay rollback failed rc=%d\n",cleanup);
        return 0; /* pin module until rmmod retry */
    }
    return err;
}
static void __exit n71_native_exit(void)
{
    if (overlay_present)of_overlay_remove(&overlay_id);
}
module_init(n71_native_init);
module_exit(n71_native_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Owner RAM-only, exclusive native PMIC GPIO10 WLAN REG_ON 25ms proof");
