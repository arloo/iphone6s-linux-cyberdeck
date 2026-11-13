// SPDX-License-Identifier: GPL-2.0
/* Owner-supervised N71 Samsung A9 WLAN REG_ON PMU GPIO10 microlease.
 * Exactly one PMIC D2255 output bit (0x914 BIT0) is touched, then restored.
 * Does not register a gpiochip, power PCIe, touch BT GPIO8 or modify RTC.
 */
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>

static bool armed;
module_param(armed, bool, 0400);
MODULE_PARM_DESC(armed,"owner-supervised 25ms WLAN REG_ON GPIO10 level pulse; default false");
static bool visited;
static int probe_result=-EINPROGRESS;

static int n71_wlan_power_probe(struct platform_device *pdev)
{
    struct regmap *map;
    unsigned int original=0, bt_before=0, st_before=0;
    unsigned int on=0, st_on=0, off=0, st_off=0, bt_after=0;
    int ret=0, rollback;

    /* A failed platform probe can be retried; never pulse more than once
     * during this module insertion. */
    if (visited)
        return -ENODEV;
    visited=true;
    probe_result=-EPERM;
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000") ||
        !of_device_is_compatible(pdev->dev.of_node,"apple,antigua-pmic-gpio") ||
        !pdev->dev.parent ||
        !of_device_is_compatible(pdev->dev.parent->of_node,"apple,antigua-pmic"))
        return -ENODEV;
    map=dev_get_regmap(pdev->dev.parent,NULL);
    if (!map)
        return -ENODEV;
    ret=regmap_read(map,0x914,&original); /* PMIC GPIO10 */
    if (ret)
        goto out;
    ret=regmap_read(map,0x910,&bt_before); /* PMIC GPIO8, read-only */
    if (ret)
        goto out;
    ret=regmap_read(map,0x187,&st_before); /* GPIO10 pad sampled bit2 */
    if (ret)
        goto out;
    if (original!=0x80 || bt_before!=0x80 || (st_before&BIT(2))) {
        ret=-EPERM;
        goto out;
    }
    if (!armed) {
        pr_info("n71-wlan-regon: PMU GPIO10=0x80 LOW; unarmed read-only PASS\n");
        probe_result=0;
        return -ENODEV;
    }
    /* Existing GPIO Apple PMIC driver uses precisely this one-bit update.
     * Boot firmware has already configured pin10 as an output (0x80).
     * No pin mode changes, no access to any other PMIC output. */
    ret=regmap_update_bits(map,0x914,BIT(0),BIT(0));
    if (ret)
        goto rollback;
    ret=regmap_read(map,0x914,&on);
    if (ret)
        goto rollback;
    msleep(25);
    ret=regmap_read(map,0x187,&st_on);
    if (ret)
        goto rollback;
rollback:
    /* Regardless of readback errors, request LOW again before returning. */
    rollback=regmap_update_bits(map,0x914,BIT(0),0);
    if (!ret && rollback)
        ret=rollback;
    if (regmap_read(map,0x914,&off) && !ret)
        ret=-EIO;
    if (regmap_read(map,0x187,&st_off) && !ret)
        ret=-EIO;
    if (regmap_read(map,0x910,&bt_after) && !ret)
        ret=-EIO;
    pr_info("n71-wlan-regon: PMU WLAN cfg=%02x -> %02x -> %02x, pad10 before=%u on=%u after=%u, BTcfg before=%02x after=%02x\n",
            original,on,off,!!(st_before&BIT(2)),!!(st_on&BIT(2)),
            !!(st_off&BIT(2)),bt_before,bt_after);
    if (!ret && (on!=0x81 || off!=0x80 || bt_after!=bt_before ||
                 (st_off&BIT(2))))
        ret=-EIO;
    if (!ret)
        pr_info("n71-wlan-regon: PMIC_GPIO10 WLAN REG_ON latch HIGH 25ms then LOW; pad voltage not independently proven\n");
out:
    probe_result=ret;
    return -ENODEV;
}

static const struct of_device_id n71_wlan_pm_match[] = {
    { .compatible="apple,antigua-pmic-gpio" }, { }
};
static struct platform_driver n71_wlan_pm_driver = {
    .probe=n71_wlan_power_probe,
    .driver={.name="n71-wlan-pmu-gpio10-microlease",
             .of_match_table=n71_wlan_pm_match},
};
static int __init n71_wlan_pm_init(void)
{
    int ret;
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;
    ret=platform_driver_register(&n71_wlan_pm_driver);
    if (ret)
        return ret;
    platform_driver_unregister(&n71_wlan_pm_driver);
    if (!visited || probe_result)
        return probe_result ? probe_result : -ENODEV;
    return 0;
}
static void __exit n71_wlan_pm_exit(void)
{
    pr_info("n71-wlan-regon: released no persistent PMIC resources\n");
}
module_init(n71_wlan_pm_init);
module_exit(n71_wlan_pm_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Owner-only N71 Samsung PMIC GPIO10 WLAN REG_ON bounded high-low pulse");
