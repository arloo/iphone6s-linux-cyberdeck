// SPDX-License-Identifier: GPL-2.0
/* One-shot exact N71/S8000 PCIe GPIO line register snapshot.
 * Linux Apple pinctrl is already bound. ZERO GPIO requests or writes.
 * No PMGR, PCIe, PHY, PERST manipulation, DMA, DART, or iOS NAND access.
 */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>

#define N71_PINCTRL_MMIO 0x20f100000ULL
#define N71_PINCTRL_SIZE 0x1000

static int __init n71_gpio_pin_ro_init(void)
{
    static const struct {
        unsigned int pin;
        const char *label;
    } lines[] = {
        { 73, "wifi_device_wake" },
        { 160, "storage_perst_control" },
        { 161, "wifi_perst_control" },
        { 162, "baseband_perst_control" },
        { 164, "storage_clkreq_control" },
        { 165, "wifi_clkreq_control" },
        { 166, "baseband_clkreq_control" },
    };
    void __iomem *base;
    struct device_node *pinctrl;
    u32 v;
    int i;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return -ENODEV;
    pinctrl = of_find_node_by_path("/soc/pinctrl@20f100000");
    if (!pinctrl)
        pinctrl = of_find_node_by_path("/soc/pinctrl@20f100000");
    if (!pinctrl)
        return -ENODEV;
    if (!of_device_is_compatible(pinctrl, "apple,s8000-pinctrl")) {
        of_node_put(pinctrl);
        return -ENODEV;
    }
    of_node_put(pinctrl);
    base = ioremap(N71_PINCTRL_MMIO, N71_PINCTRL_SIZE);
    if (!base)
        return -ENOMEM;
    for (i = 0; i < ARRAY_SIZE(lines); i++) {
        v = readl((u8 __iomem *)base + 4 * lines[i].pin);
        pr_info("n71-pinctrl-ro: %s pin=%u raw=0x%08x data=%u mode=%u periph=%u pull=%u input_enable=%u lock=%u\n",
                lines[i].label, lines[i].pin, v, !!(v & 1),
                (v >> 1) & 7, (v >> 5) & 3, (v >> 7) & 3,
                !!(v & BIT(9)), !!(v & BIT(21)));
    }
    iounmap(base);
    return 0;
}

static void __exit n71_gpio_pin_ro_exit(void)
{
    pr_info("n71-pinctrl-ro: unloaded\n");
}
module_init(n71_gpio_pin_ro_init);
module_exit(n71_gpio_pin_ro_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only A9 Samsung N71 WLAN PERST CLKREQ raw pin register snapshot");
