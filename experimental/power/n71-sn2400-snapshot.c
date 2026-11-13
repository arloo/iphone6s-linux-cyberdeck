// SPDX-License-Identifier: GPL-2.0-only
/* N71 SN2400 observation through the existing mux driver's regmap. */
#include <linux/device.h>
#include <linux/errno.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regmap.h>
static int __init n71_sn2400_snapshot_init(void)
{
    static const unsigned int regs[] = { 0x07, 0x09, 0x0d, 0x10, 0x1d };
    struct device *dev;
    struct regmap *map;
    unsigned int i, value;
    int ret = -ENODEV;
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000")) return -ENODEV;
    dev = bus_find_device_by_name(&i2c_bus_type, NULL, "1-0075");
    if (!dev) return -ENODEV;
    if (!dev->of_node || !of_device_is_compatible(dev->of_node, "ti,sn2400")) goto out;
    map = dev_get_regmap(dev, NULL);
    if (!map) goto out;
    for (i = 0; i < ARRAY_SIZE(regs); i++) {
        ret = regmap_read(map, regs[i], &value);
        if (ret) goto out;
        pr_info("n71-sn2400-snapshot: reg=%02x value=%02x READ_ONLY\n", regs[i], value);
    }
    pr_info("n71-sn2400-snapshot: COMPLETE no register writes\n");
out:
    put_device(dev);
    return ret;
}
static void __exit n71_sn2400_snapshot_exit(void) {}
module_init(n71_sn2400_snapshot_init);
module_exit(n71_sn2400_snapshot_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 SN2400 selected-register read-only snapshot");
