// SPDX-License-Identifier: GPL-2.0-only
/* N71/S8000 bounded SN2400 input-limit trial.
 * Register definitions and 90mA+10mA/code derived from Paul Praschl's
 * apple_sn2400_charger driver, Orchard commit 8ea3182ac02f1c4da22dce8c082eb0df5f7083d3.
 * Adaptation: change only an already-enabled 90mA input; keep original
 * charge-current/voltage controls; rollback requested after 30 seconds (2-second monitor cadence).
 */
#include <linux/device.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>
#include <linux/workqueue.h>
#include <linux/jiffies.h>
#include <linux/mutex.h>
#define REG_STATUS 0x07
#define REG_INPUT 0x09
#define REG_CONTROL 0x10
#define REG_ADC_CTL 0x11
#define REG_ADC_DATA 0x12
static bool armed;
static unsigned int input_ua = 300000;
module_param(armed, bool, 0400);
module_param(input_ua, uint, 0400);
static struct device *chip_dev;
static struct regmap *chip_map;
static struct power_supply *battery;
static unsigned int saved_input;
static bool changed;
static int baseline_uv;
static unsigned long deadline;
static DEFINE_MUTEX(trial_lock);
static struct delayed_work monitor;
static int battery_ok(void)
{
    union power_supply_propval cap, temp, voltage;
    int ret;
    ret = power_supply_get_property(battery, POWER_SUPPLY_PROP_CAPACITY, &cap);
    if (ret) return ret;
    ret = power_supply_get_property(battery, POWER_SUPPLY_PROP_TEMP, &temp);
    if (ret) return ret;
    ret = power_supply_get_property(battery, POWER_SUPPLY_PROP_VOLTAGE_NOW, &voltage);
    if (ret) return ret;
    if (cap.intval <= 10 || temp.intval < 100 || temp.intval >= 400 ||
        voltage.intval < 3300000 || voltage.intval > 4200000) return -ERANGE;
    return 0;
}
static int vbus_read(int *uv)
{
    unsigned int value;
    int ret = regmap_write(chip_map, REG_ADC_CTL, BIT(4));
    if (ret) return ret;
    ret = regmap_read_poll_timeout(chip_map, REG_ADC_CTL, value,
                                  !(value & BIT(4)), 5000, 100000);
    if (ret) return ret;
    ret = regmap_read(chip_map, REG_ADC_DATA, &value);
    if (!ret) *uv = value * 25000;
    return ret;
}
static int restore_input(const char *reason)
{
    unsigned int value = 0;
    int ret;
    if (!changed) return 0;
    ret = regmap_write(chip_map, REG_INPUT, saved_input);
    if (!ret) ret = regmap_read(chip_map, REG_INPUT, &value);
    if (!ret && value != saved_input) ret = -EIO;
    if (!ret) changed = false;
    pr_info("n71-sn2400-trial: RESTORE reason=%s input=%02x rc=%d\n", reason, value, ret);
    return ret;
}
static void monitor_work(struct work_struct *work)
{
    unsigned int status, value;
    int uv = 0, ret;
    mutex_lock(&trial_lock);
    if (!changed) goto out;
    if (time_after_eq(jiffies, deadline)) {
        restore_input("30s-expired");
        goto out;
    }
    ret = battery_ok();
    if (!ret) ret = regmap_read(chip_map, REG_STATUS, &status);
    if (!ret && !(status & BIT(5))) ret = -ENOLINK;
    if (!ret) ret = vbus_read(&uv);
    if (!ret && (uv < 4400000 || uv > 5500000 || baseline_uv - uv > 400000)) ret = -ERANGE;
    if (!ret) ret = regmap_read(chip_map, REG_INPUT, &value);
    if (!ret && value != (input_ua - 90000) / 10000) ret = -EIO;
    if (ret) {
        pr_err("n71-sn2400-trial: MONITOR_STOP rc=%d VBUS_uV=%d\n", ret, uv);
        restore_input("monitor-stop");
        goto out;
    }
    pr_info("n71-sn2400-trial: MONITOR VBUS_uV=%d status=%02x input_uA=%u\n", uv, status, input_ua);
    schedule_delayed_work(&monitor, msecs_to_jiffies(2000));
out:
    mutex_unlock(&trial_lock);
}
static int __init trial_init(void)
{
    unsigned int status, control, adc;
    int ret;
    INIT_DELAYED_WORK(&monitor, monitor_work);
    if (input_ua != 300000 && input_ua != 500000) return -EINVAL;
    if (!armed) {
        pr_info("n71-sn2400-trial: UNARMED no hardware access\n");
        return 0;
    }
    if (!of_machine_is_compatible("apple,n71") || !of_machine_is_compatible("apple,s8000")) return -ENODEV;
    chip_dev = bus_find_device_by_name(&i2c_bus_type, NULL, "1-0075");
    if (!chip_dev) return -ENODEV;
    ret = -ENODEV;
    if (!chip_dev->of_node || !of_device_is_compatible(chip_dev->of_node, "ti,sn2400")) goto fail;
    chip_map = dev_get_regmap(chip_dev, NULL);
    if (!chip_map) goto fail;
    battery = power_supply_get_by_name("bq27540-0");
    if (!battery) goto fail;
    ret = battery_ok();
    if (ret) goto fail;
    ret = regmap_read(chip_map, REG_STATUS, &status);
    if (!ret) ret = regmap_read(chip_map, REG_CONTROL, &control);
    if (!ret) ret = regmap_read(chip_map, REG_INPUT, &saved_input);
    if (!ret) ret = regmap_read(chip_map, REG_ADC_CTL, &adc);
    if (ret) goto fail;
    pr_info("n71-sn2400-trial: BASE status=%02x control=%02x input=%02x adc=%02x\n",
            status, control, saved_input, adc);
    if ((status & 0xa0) != 0xa0 || control != 0x04 || saved_input != 0 || adc != 0) { ret = -EPERM; goto fail; }
    ret = vbus_read(&baseline_uv);
    if (ret) goto fail;
    if (baseline_uv < 4400000 || baseline_uv > 5500000) { ret = -ERANGE; goto fail; }
    changed = true;
    ret = regmap_write(chip_map, REG_INPUT, (input_ua - 90000) / 10000);
    if (!ret) ret = regmap_read(chip_map, REG_INPUT, &control);
    if (!ret && control != (input_ua - 90000) / 10000) ret = -EIO;
    if (ret) {
        if (restore_input("write-failed")) {
            /* Keep code and device references resident for explicit cleanup. */
            deadline = jiffies;
            pr_err("n71-sn2400-trial: ROLLBACK_FAILED module retained for cleanup\n");
            return 0;
        }
        goto fail;
    }
    deadline = jiffies + msecs_to_jiffies(30000);
    schedule_delayed_work(&monitor, msecs_to_jiffies(2000));
    pr_info("n71-sn2400-trial: APPLIED input_uA=%u original_uA=90000 VBUS_uV=%d automatic_restore_ms=30000\n", input_ua, baseline_uv);
    return 0;
fail:
    if (battery) { power_supply_put(battery); battery = NULL; }
    if (chip_dev) { put_device(chip_dev); chip_dev = NULL; }
    return ret;
}
static void __exit trial_exit(void)
{
    cancel_delayed_work_sync(&monitor);
    mutex_lock(&trial_lock);
    restore_input("module-exit");
    mutex_unlock(&trial_lock);
    if (battery) power_supply_put(battery);
    if (chip_dev) put_device(chip_dev);
}
module_init(trial_init);
module_exit(trial_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 SN2400 30-second input-current trial with automatic rollback");
