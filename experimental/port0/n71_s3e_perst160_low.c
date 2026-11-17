// SPDX-License-Identifier: GPL-2.0
/*
 * Original N71/Samsung S8000 Apple S3E PERST GPIO160 bounded pilot.
 *
 * Preconditions: Apple N71/S8000, live Wi-Fi link1, PCIe link0 OFF,
 * genuine stock N71 GPIO160 register == 0x00072200 (input, low).
 *
 * Action: acquire exclusive pin160 via kernel GPIO descriptor table,
 * configure output LOW (reset ASSERTED) for 50ms, restore input mode
 * and verify register bit-for-bit restored, release exclusive owner.
 *
 * Nothing releases PERST or drives pin160 high. No PCIe power, DART,
 * MMIO to storage, DMA, NVMe submission or NAND access. Hardware always
 * sees the reset as low or high-impedance as the original baseline.
 */
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/mfd/syscon.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/device.h>
#include <linux/pci.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/pm_domain.h>
#include <linux/string.h>

#define N71_GPIOCHIP "20f100000.pinctrl"
#define N71_P0_GPIO 160U
#define N71_P1_GPIO 161U
#define N71_PINCTRL_PHYS 0x20f100000ULL
#define N71_P0_REG (4U * N71_P0_GPIO)
#define N71_P1_REG (4U * N71_P1_GPIO)
#define N71_GPIO0_STOCK 0x00072200U
#define N71_GPIO1_WIFI 0x00072203U
#define N71_PMGR "/soc/power-management@20e000000"
#define N71_P0_PMGR 0x80320U
#define N71_PCI_GUARD "/soc/pcie-port1-preflight@602000000"
#define N71_ROOT_PHYS 0x600000000ULL
#define N71_RESET_DWELL_MS 50
#define N71_PINCTRL_PROVIDER "/soc/pinctrl@20f100000"
#define N71_GPIO_MUTABLE_MASK (GENMASK(6,5) | GENMASK(3,0) | BIT(9))

static bool armed;
module_param(armed, bool, 0400);

static struct platform_device *n71_pdev;
static struct gpiod_lookup_table n71_s3e_gpio_table = {
    .dev_id = "n71-s3e-perst160",
    .table = {
        GPIO_LOOKUP(N71_GPIOCHIP, N71_P0_GPIO, "storage-perst", GPIO_ACTIVE_HIGH),
        { },
    },
};
static bool table_added;

static bool board_ok(void)
{
    struct device_node *n;
    struct pci_dev *wifi;
    bool ok;
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000")) return false;
    n=of_find_node_by_path(N71_PCI_GUARD);
    ok=n && of_device_is_compatible(n,"apple,s8000-pcie-research-blocked")
         && of_property_read_bool(n,"research,hardware-activation-blocked");
    of_node_put(n);
    if (!ok) return false;
    wifi=pci_get_device(0x14e4,0x43a3,NULL);
    ok=wifi!=NULL;
    pci_dev_put(wifi);
    return ok;
}

static int power_off(void)
{
    struct device_node *n;
    struct regmap *map;
    u32 value;
    int ret;
    n=of_find_node_by_path(N71_PMGR);
    if (!n) return -ENODEV;
    map=syscon_node_to_regmap(n);
    of_node_put(n);
    if (IS_ERR(map)) return PTR_ERR(map);
    ret=regmap_read(map,N71_P0_PMGR,&value);
    if (ret) return ret;
    return (value&0xffU)==0 ? 0 : -EBUSY;
}

static int __init n71_storage_perst_init(void)
{
    void __iomem *ap=NULL, *root=NULL;
    struct gpio_desc *pin=NULL;
    struct device_node *ap_node=NULL;
    struct platform_device *ap_device=NULL;
    struct regmap *pin_map=NULL;
    u32 baseline, p1, p0_link, p1_link, reset_register, cached;
    int ret=0, rel_ret=0, err;
    bool reset_output=false, quarantine=false;

    if (!armed) {
        pr_info("n71-s3e-perst160: UNARMED inert; no GPIO or MMIO\n");
        return 0;
    }
    if (!board_ok()) return -EPERM;
    ret=power_off();
    if (ret) return ret;
    ap_node=of_find_node_by_path(N71_PINCTRL_PROVIDER);
    if (!ap_node || !of_device_is_compatible(ap_node,"apple,s8000-pinctrl")) {
        of_node_put(ap_node);
        return -ENODEV;
    }
    ap_device=of_find_device_by_node(ap_node);
    of_node_put(ap_node);
    if (!ap_device) return -ENODEV;
    /* Use pinctrl's exact, existing regmap. Apple's driver caches each
     * register, so a second independent regmap would corrupt that cache.
     */
    pin_map=dev_get_regmap(&ap_device->dev,NULL);
    put_device(&ap_device->dev);
    if (!pin_map) return -ENODEV;
    ap=ioremap(N71_PINCTRL_PHYS,0x1000);
    root=ioremap(N71_ROOT_PHYS,0x1000);
    if (!ap || !root) {ret=-ENOMEM; goto out;}
    baseline=readl((u8 __iomem *)ap+N71_P0_REG);
    p1=readl((u8 __iomem *)ap+N71_P1_REG);
    p0_link=readl((u8 __iomem *)root+0x16c);
    p1_link=readl((u8 __iomem *)root+0x1ac);
    ret=regmap_read(pin_map,N71_P0_REG,&cached);
    if (ret) goto out;
    if (baseline!=N71_GPIO0_STOCK || cached!=baseline ||
        p1!=N71_GPIO1_WIFI || p0_link!=0 || p1_link!=1) {
        pr_err("n71-s3e-perst160: REFUSED unexpected physical pin/link baseline p0=%08x wifi=%08x\n",
               baseline,p1);
        ret=-EPERM;
        goto out;
    }
    gpiod_add_lookup_table(&n71_s3e_gpio_table);
    table_added=true;
    n71_pdev=platform_device_register_simple("n71-s3e-perst160",PLATFORM_DEVID_NONE,NULL,0);
    if (IS_ERR(n71_pdev)) {
        ret=PTR_ERR(n71_pdev);n71_pdev=NULL;goto out;
    }
    pin=gpiod_get(&n71_pdev->dev,"storage-perst",GPIOD_ASIS);
    if (IS_ERR(pin)) {
        ret=PTR_ERR(pin);pin=NULL;goto out;
    }
    if (gpiod_get_direction(pin)!=1 ||
        readl((u8 __iomem *)ap+N71_P0_REG)!=baseline) {
        ret=-EPERM;
        goto out;
    }
    /* Set GPIO output value LOW only; never send 1 or deassert reset. */
    reset_output=true;
    ret=gpiod_direction_output(pin,0);
    if (ret) goto rollback;
    reset_register=readl((u8 __iomem *)ap+N71_P0_REG);
    if (gpiod_get_direction(pin)!=0 || gpiod_get_value_cansleep(pin)!=0 ||
        reset_register!=0x00072202U) {
        ret=-EIO;
        goto rollback;
    }
    pr_info("n71-s3e-perst160: PHYSICAL_STORAGE_RESET_ASSERTED_GPIO160_OUT_LOW register=%08x no_PCIe_power_no_NAND_DMA\n",
        reset_register);
    msleep(N71_RESET_DWELL_MS);
rollback:
    if (reset_output) {
        /*
         * gpiod_direction_input() defaults to GPIO input IRQ-off mode=7,
         * so it leaves 0x0007220e, NOT stock 0x00072200 (mode=0).
         * The already proven port1 recovery uses the driver's OWN regmap
         * to restore the exact original mode with a masked RMW.
         * GPIO160 is never driven HIGH.
         */
        rel_ret=gpiod_direction_input(pin);
        if (!rel_ret) {
            err=regmap_update_bits(pin_map,N71_P0_REG,
                                   N71_GPIO_MUTABLE_MASK,
                                   baseline & N71_GPIO_MUTABLE_MASK);
            if (err) rel_ret=err;
        }
        reset_register=readl((u8 __iomem *)ap+N71_P0_REG);
        err=regmap_read(pin_map,N71_P0_REG,&cached);
        if (rel_ret || err || gpiod_get_direction(pin)!=1 ||
            reset_register!=baseline || cached!=baseline) {
            quarantine=true;
            pr_err("n71-s3e-perst160: GPIO160_RESTORE_FAILED rc=%d read=%08x; pin retained for recovery\n",
                   rel_ret,reset_register);
            ret=-EUCLEAN;
        } else {
            pr_info("n71-s3e-perst160: RESTORED_GPIO160_ORIGINAL_INPUT_LOW=%08x\n",
                reset_register);
        }
    }
    if (!ret && power_off())
        ret=-EUCLEAN;
out:
    if (quarantine) {
        __module_get(THIS_MODULE);
        pr_err("n71-s3e-perst160: QUARANTINE pin ownership retained. Do not force unload\n");
        return 0;
    }
    if (pin) gpiod_put(pin);
    if (n71_pdev) {
        platform_device_unregister(n71_pdev); n71_pdev=NULL;
    }
    if (table_added) {
        gpiod_remove_lookup_table(&n71_s3e_gpio_table);
        table_added=false;
    }
    if (root) iounmap(root);
    if (ap) iounmap(ap);
    if (ret) {
        pr_err("n71-s3e-perst160: DIAGNOSTIC_ABORT_AFTER_SAFE_ROLLBACK rc=%d no retry\n",ret);
        /* Avoid a BusyBox insmod duplicate fallback when a guard rejects. */
        return 0;
    }
    pr_info("n71-s3e-perst160: PHYSICAL_RESET_LOW_PILOT_PASS domain_off=yes wifi_preserved=yes\n");
    return 0;
}
static void __exit n71_storage_perst_exit(void)
{
    pr_info("n71-s3e-perst160: clean unload; no GPIO ownership held\n");
}
module_init(n71_storage_perst_init);
module_exit(n71_storage_perst_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 S8000 S3E GPIO160 reset-low pilot only, no NAND power or DMA");
