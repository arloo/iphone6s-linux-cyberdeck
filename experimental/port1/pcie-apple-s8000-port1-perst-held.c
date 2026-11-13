// SPDX-License-Identifier: GPL-2.0
/* N71/S8000: bounded PERST-low WLAN/PMGR/ID3 experiment.
 * Never drives PERST HIGH, writes DART or scans PCI.
 * Stage8 only reads the original DART1 packed TCR once under endpoint reset.
 * Source and physical test are board-specific; no analog voltage claim.
 */
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/gpio/consumer.h>
#include <linux/regmap.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>

#include "n71-s8000-port1-perst-held-blob.h"

#define N71_STATUS_SNAPSHOT_NODE "/soc/n71-port1-perst-held"
#define N71_PCI_GUARD "/soc/pcie-port1-preflight@602000000"
#define N71_PMGR "/soc/power-management@20e000000"
#define N71_HOLD_MS 25
#define N71_ROOT_COMMON_PHYS 0x600000000ULL
#define N71_ROOT_SHARED_REGISTER 0x2cU
#define N71_ROOT_PORT1_REGISTER 0x1acU
#define N71_ROOT_IOREMAP_BYTES 0x1000U
#define N71_PINCTRL_PHYS 0x20f100000ULL
#define N71_PINCTRL_BYTES 0x1000U

/* There is no PERST release mode, DART write or PCI host access. */
static bool armed;
static unsigned int stage;
static bool n71_probed;
module_param(armed, bool, 0400);
module_param(stage, uint, 0400);
MODULE_PARM_DESC(armed, "exclusive PERST-low test, default false");
MODULE_PARM_DESC(stage, "0=PERST only,1=add WLAN,2=add PMGR status,3=ID3 status,4=ID2 enable,5=common init only,6=common+ID2,7=stable 250ms,8=add read-only DART1 TCR,9=read TTBR/command/fault; never release PERST");

static const struct {
    const char *name;
    const char *path;
    u32 phandle;
} n71_domains[] = {
    { "ref", N71_PMGR "/power-controller@80148", 0x3a },
    { "aux", N71_PMGR "/power-controller@80318", 0x3b },
    { "link1", N71_PMGR "/power-controller@80328", 0x3c },
    { "root", N71_PMGR "/power-controller@80310", 0x2c },
};

static int n71_overlay_id;
static bool n71_overlay_present;
static bool n71_driver_registered;
static int n71_probe_result = -EINPROGRESS;

static bool n71_validate_nodes(void)
{
    struct device_node *guard, *node;
    unsigned int i;
    bool ok;

    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000"))
        return false;
    guard = of_find_node_by_path(N71_PCI_GUARD);
    ok = guard && of_device_is_compatible(guard,
            "apple,s8000-pcie-research-blocked") &&
         of_property_read_bool(guard,
            "research,hardware-activation-blocked");
    of_node_put(guard);
    if (!ok)
        return false;
    for (i = 0; i < ARRAY_SIZE(n71_domains); i++) {
        u32 cells;
        node = of_find_node_by_path(n71_domains[i].path);
        ok = node && node->phandle == n71_domains[i].phandle &&
             of_device_is_compatible(node, "apple,s8000-pmgr-pwrstate") &&
             !of_property_read_u32(node, "#power-domain-cells", &cells) &&
             cells == 0;
        of_node_put(node);
        if (!ok)
            return false;
    }
    return true;
}

static bool n71_validate_probe(struct device *dev)
{
    struct device_node *node = dev->of_node;
    unsigned int i;

    if (!node || !of_device_is_compatible(node,
            "research,n71-s8000-pcie-perst-held") ||
        !of_device_is_available(node) ||
        !of_property_read_bool(node, "research,owner-supervised-perst-held") ||
        of_property_count_u32_elems(node, "power-domains") != 4 ||
        of_property_count_strings(node, "power-domain-names") != 4 ||
        dev->pm_domain)
        return false;
    for (i = 0; i < ARRAY_SIZE(n71_domains); i++) {
        struct device_node *provider, *expected;
        const char *name;
        bool match;

        provider = of_parse_phandle(node, "power-domains", i);
        expected = of_find_node_by_path(n71_domains[i].path);
        match = provider && expected && provider == expected &&
                !of_property_read_string_index(node,
                        "power-domain-names", i, &name) &&
                !strcmp(name, n71_domains[i].name);
        of_node_put(provider);
        of_node_put(expected);
        if (!match)
            return false;
    }
    return true;
}

#define N71_AP_PROVIDER "/soc/pinctrl@20f100000"
#define N71_PMU_PROVIDER "/soc/i2c@20a110000/pmic@74/gpio@900"
#define N71_PERST_PIN 161U
#define N71_GPIO_MUTABLE_MASK (GENMASK(6, 5) | GENMASK(3, 0) | BIT(9))

static bool n71_gpio_ref_ok(struct device_node *np, const char *property,
                            const char *path, u32 phandle, u32 pin)
{
    struct of_phandle_args parsed = {};
    struct device_node *expected;
    bool okay;
    int ret = of_parse_phandle_with_args(np, property, "#gpio-cells", 0, &parsed);

    if (ret)
        return false;
    expected = of_find_node_by_path(path);
    okay = expected && parsed.np == expected && expected->phandle == phandle &&
           of_property_read_bool(expected, "gpio-controller") &&
           parsed.args_count == 2 && parsed.args[0] == pin && parsed.args[1] == 0;
    of_node_put(expected);
    of_node_put(parsed.np);
    return okay;
}

static int n71_microlease_probe(struct platform_device *pdev)
{
    static const char * const names[] = { "ref", "aux", "link1" };
    static const unsigned int protected_pins[] = { 73, 160, 162, 164, 165, 166 };
    static const unsigned int protected_ports[] = { 0, 2, 3 };
    static const unsigned int protected_reg_offsets[] = { 0x100, 0x114, 0x124, 0x12c };
    struct device *virt[ARRAY_SIZE(names)] = {};
    struct gpio_desc *perst = NULL, *wlan = NULL;
    struct device_node *ap_node;
    struct platform_device *ap_dev = NULL;
    struct regmap *map;
    void __iomem *ap = NULL, *root = NULL, *dart1 = NULL;
    u32 perst_saved, cached, protected_saved[ARRAY_SIZE(protected_pins)];
    u32 id1 = 0, id2 = 0, id3 = 0, id4 = 0, id5 = 0, after = 0;
    u32 lane_saved = 0, done_saved = 0, common_status = 0;
    u32 protected_root[3][4] = {};
    unsigned int j;
    bool common_changed = false;
    int common_poll = -EINPROGRESS;
    unsigned int attached = 0, resumed = 0, i;
    bool perst_changed = false, wlan_changed = false, id3_changed = false, id2_changed = false, id4_changed = false;
    int ret = -EPERM, err, poll_rc = -EINPROGRESS, high = -1, low = -1;

    if (n71_probed)
        return -ENODEV;
    n71_probed = true;
    n71_probe_result = -EPERM;
    if (!n71_validate_nodes() || !n71_validate_probe(&pdev->dev) ||
        !n71_gpio_ref_ok(pdev->dev.of_node, "perst-gpios", N71_AP_PROVIDER, 0x0a, 161) ||
        !n71_gpio_ref_ok(pdev->dev.of_node, "wlan-reg-on-gpios", N71_PMU_PROVIDER, 0x09, 10))
        return -EPERM;
    if (!armed) {
        n71_probe_result = 0;
        pr_info("n71-perst-held: UNARMED no GPIO requests, power or MMIO\n");
        return -ENODEV;
    }
    ap_node = of_find_node_by_path(N71_AP_PROVIDER);
    if (!ap_node || !of_device_is_compatible(ap_node, "apple,s8000-pinctrl")) {
        of_node_put(ap_node);
        return -ENODEV;
    }
    ap_dev = of_find_device_by_node(ap_node);
    of_node_put(ap_node);
    if (!ap_dev)
        return -ENODEV;
    map = dev_get_regmap(&ap_dev->dev, NULL);
    if (!map) {
        ret = -ENODEV;
        goto out;
    }
    ap = ioremap(N71_PINCTRL_PHYS, N71_PINCTRL_BYTES);
    if (!ap) {
        ret = -ENOMEM;
        goto out;
    }
    perst_saved = readl((u8 __iomem *)ap + 4 * N71_PERST_PIN);
    ret = regmap_read(map, 4 * N71_PERST_PIN, &cached);
    if (ret)
        goto out;
    if (perst_saved != 0x00072200 || cached != perst_saved ||
        readl((u8 __iomem *)ap + 4 * 165) != 0x00076a21) {
        ret = -EPERM;
        goto out;
    }
    for (i = 0; i < ARRAY_SIZE(protected_pins); i++)
        protected_saved[i] = readl((u8 __iomem *)ap + 4 * protected_pins[i]);
    /* ASIS reserves ownership without driving an unvalidated initial level. */
    perst = gpiod_get(&pdev->dev, "perst", GPIOD_ASIS);
    if (IS_ERR(perst)) {
        ret = PTR_ERR(perst);
        perst = NULL;
        goto out;
    }
    if (gpiod_is_active_low(perst) || gpiod_get_direction(perst) != 1 ||
        readl((u8 __iomem *)ap + 4 * N71_PERST_PIN) != perst_saved) {
        ret = -EPERM;
        goto out;
    }
    /* ACTIVE HIGH descriptor means logical zero is electrical LOW/PERST#. */
    perst_changed = true;
    ret = gpiod_direction_output(perst, 0);
    if (ret)
        goto restore;
    after = readl((u8 __iomem *)ap + 4 * N71_PERST_PIN);
    if (after != ((perst_saved & ~0x6fU) | 2U) ||
        gpiod_get_direction(perst) != 0 || gpiod_get_value_cansleep(perst) != 0) {
        ret = -EIO;
        goto restore;
    }
    pr_info("n71-perst-held: PERST161 RESERVED OUTPUT_LOW raw=%08x stage=%u\n", after, stage);
    ret = 0;
    if (!stage) {
        msleep(25);
        goto restore;
    }
    wlan = gpiod_get(&pdev->dev, "wlan-reg-on", GPIOD_ASIS);
    if (IS_ERR(wlan)) {
        ret = PTR_ERR(wlan);
        wlan = NULL;
        goto restore;
    }
    if (gpiod_is_active_low(wlan) || gpiod_get_direction(wlan) != 0 ||
        gpiod_get_value_cansleep(wlan) != 0) {
        ret = -EPERM;
        goto restore;
    }
    wlan_changed = true;
    gpiod_set_value_cansleep(wlan, 1);
    high = gpiod_get_value_cansleep(wlan);
    if (high != 1) {
        ret = high < 0 ? high : -EIO;
        goto restore;
    }
    /* Broadcom WLAN settles while endpoint reset is asserted throughout. */
    msleep(25);
    if (stage == 1)
        goto restore;
    for (i = 0; i < ARRAY_SIZE(names); i++) {
        virt[i] = dev_pm_domain_attach_by_name(&pdev->dev, names[i]);
        if (IS_ERR_OR_NULL(virt[i])) {
            ret = virt[i] ? PTR_ERR(virt[i]) : -ENODEV;
            goto restore;
        }
        attached++;
        ret = pm_runtime_resume_and_get(virt[i]);
        if (ret)
            goto restore;
        resumed++;
        pr_info("n71-perst-held: PMGR %s ON with PERST_LOW\n", names[i]);
        usleep_range(150, 300);
    }
    root = ioremap(N71_ROOT_COMMON_PHYS, N71_ROOT_IOREMAP_BYTES);
    if (!root) {
        ret = -ENOMEM;
        goto restore;
    }
    /* Original S8000 common initializer writes 0x4=lane_cfg|0x10,
     * polls shared 0x2c bit0, then writes 0x38=1. OBSERVATION ONLY. */
    pr_info("n71-perst-held: COMMON_READONLY lane_ctl=%08x common_done=%08x\n",
            readl((u8 __iomem *)root + 0x004),
            readl((u8 __iomem *)root + 0x038));
    id1 = readl((u8 __iomem *)root + 0x02c);
    id2 = readl((u8 __iomem *)root + 0x180);
    id3 = readl((u8 __iomem *)root + 0x194);
    id4 = readl((u8 __iomem *)root + 0x1a4);
    id5 = readl((u8 __iomem *)root + 0x1ac);
    pr_info("n71-perst-held: SNAPSHOT id1=%08x id2=%08x id3=%08x id4=%08x id5=%08x CLKREQ=%08x\n",
            id1, id2, id3, id4, id5, readl((u8 __iomem *)ap + 4 * 165));
    /* Common READY bit0 can remain latched after INIT rollback/power OFF. */
    if ((id1 & ~BIT(0)) != 0x10 || id2 != 0x01000100 || id3 != 0x100 || id4 != 0 || id5 != 0 ||
        readl((u8 __iomem *)ap + 4 * N71_PERST_PIN) != 0x00072202) {
        ret = -EPERM;
        goto restore;
    }
    if (stage >= 5) {
        lane_saved = readl((u8 __iomem *)root + 0x004);
        done_saved = readl((u8 __iomem *)root + 0x038);
        if (lane_saved != 1 || done_saved != 0) {
            ret = -EPERM;
            goto restore;
        }
        /* Common INIT is SHARED. Keep original lane selection=1 unchanged,
         * require all other port control bits disabled and PMGR peers OFF
         * (the USB runner separately proves genpd state before and after). */
        for (i = 0; i < ARRAY_SIZE(protected_ports); i++) {
            for (j = 0; j < ARRAY_SIZE(protected_reg_offsets); j++)
                protected_root[i][j] = readl((u8 __iomem *)root +
                    protected_reg_offsets[j] + protected_ports[i] * 0x80);
            pr_info("n71-perst-held: PROTECTED_PORT%u id2=%08x id3=%08x id4=%08x id5=%08x\n",
                    protected_ports[i], protected_root[i][0], protected_root[i][1],
                    protected_root[i][2], protected_root[i][3]);
            if ((protected_root[i][0] & BIT(0)) ||
                (protected_root[i][1] & BIT(0)) ||
                (protected_root[i][2] & BIT(0)) || protected_root[i][3]) {
                ret = -EPERM;
                goto restore;
            }
        }
        /* Exact ORIGINAL N71 S8000 root vslot1768 (a9 code+0x714),
         * original ADT lane-cfg=1: write 0x4=0x11, poll 0x2c bit0,
         * then 0x38=1. No S8003 PHY block or foreign tunables imported. */
        common_changed = true;
        writel(lane_saved | BIT(4), (u8 __iomem *)root + 0x004);
        if (readl((u8 __iomem *)root + 0x004) != (lane_saved | BIT(4))) {
            ret = -EIO;
            goto restore;
        }
        common_poll = readl_poll_timeout((u8 __iomem *)root + 0x02c,
                          common_status, common_status & BIT(0), 10, 250000);
        pr_info("n71-perst-held: COMMON_INIT status=%08x READY=%u POLL_RC=%d\n",
                common_status, !!(common_status & BIT(0)), common_poll);
        if (!common_poll) {
            writel(1, (u8 __iomem *)root + 0x038);
            if (readl((u8 __iomem *)root + 0x038) != 1) {
                ret = -EIO;
                goto restore;
            }
        }
        if (stage == 5 || common_poll)
            goto restore;
    }
    if (stage >= 3) {
        id3_changed = true;
        writel(id3 | BIT(0), (u8 __iomem *)root + 0x194);
        if (readl((u8 __iomem *)root + 0x194) != (id3 | BIT(0))) {
            ret = -EIO;
            goto restore;
        }
        if (stage == 4 || stage >= 6) {
            /* Original N71 inherited port slot1528 -> root1976 sets ID2 bit0
             * AFTER ID3 power and 100us delay, BEFORE ID5 ready polling.
             * Physical PERST161 remains exclusively driven LOW throughout. */
            usleep_range(100, 150);
            id2_changed = true;
            writel(id2 | BIT(0), (u8 __iomem *)root + 0x180);
            if (readl((u8 __iomem *)root + 0x180) != (id2 | BIT(0))) {
                ret = -EIO;
                goto restore;
            }
        }
        /* Opaque original ID5 bit0; bounded, never copy XNU's infinite loop. */
        poll_rc = readl_poll_timeout((u8 __iomem *)root + 0x1ac, after,
                                     after & BIT(0), 10, stage >= 4 ? 250000 : 20000);
        pr_info("n71-perst-held: ROOT_START id5=%08x READY=%u POLL_RC=%d PERST=%08x\n",
                after, !!(after & BIT(0)), poll_rc,
                readl((u8 __iomem *)ap + 4 * N71_PERST_PIN));
        if (stage >= 7 && !poll_rc) {
            /* ORIGINAL root1992: port1 ID2 bit8 clear, then root1968:
             * port1 ID4 bit0 set. Endpoint AP PERST161 NEVER goes high. */
            writel((id2 | BIT(0)) & ~BIT(8), (u8 __iomem *)root + 0x180);
            if (readl((u8 __iomem *)root + 0x180) != ((id2 | BIT(0)) & ~BIT(8))) {
                ret = -EIO;
                goto restore;
            }
            usleep_range(100, 150);
            id4_changed = true;
            writel(id4 | BIT(0), (u8 __iomem *)root + 0x1a4);
            if (readl((u8 __iomem *)root + 0x1a4) != (id4 | BIT(0))) {
                ret = -EIO;
                goto restore;
            }
            for (i = 0; i < 25; i++) {
                msleep(10);
                if (!(readl((u8 __iomem *)root + 0x1ac) & BIT(0)) ||
                    (readl((u8 __iomem *)root + 0x02c) & 0x11) != 0x11 ||
                    readl((u8 __iomem *)ap + 4 * N71_PERST_PIN) != 0x00072202) {
                    ret = -EIO;
                    goto restore;
                }
            }
            pr_info("n71-perst-held: PORT1_READY_STABLE_250MS samples=25 ID2=%08x ID3=%08x ID4=%08x ID5=%08x PERST=%08x\n",
                readl((u8 __iomem *)root + 0x180), readl((u8 __iomem *)root + 0x194),
                readl((u8 __iomem *)root + 0x1a4), readl((u8 __iomem *)root + 0x1ac),
                readl((u8 __iomem *)ap + 4 * N71_PERST_PIN));
            if (stage >= 8) {
                /* Original N71 DART1 resource=0x602008000/0x4000.
                 * Original S5L8960X read at +0xC, four packed TCR bytes.
                 * CPU READ ONLY: no driver probe/reset, TTBR, IOVA or SID guess.
                 * Endpoint remains reset and every other port disabled. */
                dart1 = ioremap(0x602008000ULL, 0x1000);
                if (!dart1) {
                    ret = -ENOMEM;
                    goto restore;
                }
                after = readl((u8 __iomem *)dart1 + 0x00c);
                pr_info("n71-perst-held: DART1_TCR_READONLY packed=%08x stream_bytes=%02x,%02x,%02x,%02x translate_enable_bits=%08x; NO_DMA_TEST\n",
                    after, after & 0xff, (after >> 8) & 0xff,
                    (after >> 16) & 0xff, (after >> 24) & 0xff,
                    after & 0x80808080U);
                /* Require the whole packed register, not just enable bits:
                 * unknown control bits or any active stream block progression.
                 * This matches the S5L8960X driver's tcr_disabled=0 but does
                 * not establish physical requester routing/fault containment. */
                if (after != 0) {
                    pr_err("n71-perst-held: DART1_STATE_REJECTED; endpoint stays reset\n");
                    ret = -EBUSY;
                    goto restore;
                }
                pr_info("n71-perst-held: DART1_ALL_FOUR_STREAMS_DISABLED_STATE_PASS; DMA isolation still untested\n");
                if (stage == 9) {
                    u32 nonzero = 0, valid = 0, entry, cmd, fault;
                    unsigned int n;
                    for (n = 0; n < 16; n++) {
                        entry = readl((u8 __iomem *)dart1 + 0x40 + 4 * n);
                        if (entry) nonzero |= BIT(n);
                        if (entry & BIT(31)) valid |= BIT(n);
                    }
                    cmd = readl((u8 __iomem *)dart1 + 0x00);
                    fault = readl((u8 __iomem *)dart1 + 0x10);
                    pr_info("n71-perst-held: DART1_TTBR_SNAPSHOT nonzero_mask=%04x valid_mask=%04x command=%08x fault=%08x PERST=%08x READ_ONLY\n",
                            nonzero, valid, cmd, fault,
                            readl((u8 __iomem *)ap + 4 * N71_PERST_PIN));
                    if (readl((u8 __iomem *)ap + 4 * N71_PERST_PIN) != 0x00072202) {
                        ret = -EIO;
                        goto restore;
                    }
                }
                iounmap(dart1);
                dart1 = NULL;
            }
        }
    }
    /* Timeout is a completed negative experiment, not claimed PHY activation. */
restore:
    if (id4_changed) {
        writel(id4, (u8 __iomem *)root + 0x1a4);
        if (readl((u8 __iomem *)root + 0x1a4) != id4)
            ret = -EIO;
    }
    if (id2_changed) {
        writel(id2, (u8 __iomem *)root + 0x180);
        if (readl((u8 __iomem *)root + 0x180) != id2)
            ret = -EIO;
    }
    if (id3_changed) {
        writel(id3, (u8 __iomem *)root + 0x194);
        if (readl((u8 __iomem *)root + 0x194) != id3)
            ret = -EIO;
    }
    if (common_changed) {
        writel(done_saved, (u8 __iomem *)root + 0x038);
        writel(lane_saved, (u8 __iomem *)root + 0x004);
        if (readl((u8 __iomem *)root + 0x038) != done_saved ||
            readl((u8 __iomem *)root + 0x004) != lane_saved)
            ret = -EIO;
        for (i = 0; i < ARRAY_SIZE(protected_ports); i++)
            for (j = 0; j < ARRAY_SIZE(protected_reg_offsets); j++)
                if (readl((u8 __iomem *)root + protected_reg_offsets[j] +
                       protected_ports[i] * 0x80) != protected_root[i][j]) {
                    pr_err("n71-perst-held: protected root port%u register%u changed\n",
                            protected_ports[i], j);
                    ret = -EIO;
                }
        pr_info("n71-perst-held: COMMON_RESTORED lane=%08x done=%08x protected_port_controls_unchanged=%u\n",
                readl((u8 __iomem *)root + 0x004),
                readl((u8 __iomem *)root + 0x038), ret == 0);
    }
    /* WLAN LOW BEFORE power teardown; PERST remains actively LOW. */
    if (wlan_changed) {
        gpiod_set_value_cansleep(wlan, 0);
        low = gpiod_get_value_cansleep(wlan);
        if (low != 0)
            ret = -EIO;
        pr_info("n71-perst-held: WLAN_GPIO10 logical high=%d restored_low=%d\n", high, low);
    }
    for (i = resumed; i > 0; i--) {
        err = pm_runtime_put_sync_suspend(virt[i - 1]);
        if (err < 0 && !ret)
            ret = err;
    }
    for (i = attached; i > 0; i--)
        dev_pm_domain_detach(virt[i - 1], true);
    if (perst_changed) {
        after = readl((u8 __iomem *)ap + 4 * N71_PERST_PIN);
        if (after != 0x00072202)
            ret = -EIO;
        /* Restore through the SAME provider regmap to keep its cache coherent.
         * Only direction/data/mux/input-enable bits that GPIO APIs may change.
         * This restores original mode0 rather than normalizing it to mode7. */
        err = regmap_update_bits(map, 4 * N71_PERST_PIN,
                                  N71_GPIO_MUTABLE_MASK, perst_saved & N71_GPIO_MUTABLE_MASK);
        if (err)
            ret = err;
        after = readl((u8 __iomem *)ap + 4 * N71_PERST_PIN);
        if (after != perst_saved)
            ret = -EIO;
        pr_info("n71-perst-held: PERST_RESTORED raw=%08x expected=%08x\n", after, perst_saved);
        for (i = 0; i < ARRAY_SIZE(protected_pins); i++) {
            if (readl((u8 __iomem *)ap + 4 * protected_pins[i]) != protected_saved[i]) {
                pr_err("n71-perst-held: protected pin changed pin=%u\n", protected_pins[i]);
                ret = -EIO;
            }
        }
    }
out:
    if (wlan)
        gpiod_put(wlan);
    if (perst)
        gpiod_put(perst);
    if (dart1)
        iounmap(dart1);
    if (root)
        iounmap(root);
    if (ap)
        iounmap(ap);
    if (ap_dev)
        put_device(&ap_dev->dev);
    n71_probe_result = ret;
    pr_info("n71-perst-held: COMPLETE rc=%d stage=%u ID5_READY=%u POLL_RC=%d; endpoint reset NEVER released, no DART writes/DMA/PCI scan\n",
            ret, stage, poll_rc == 0, poll_rc);
    return -ENODEV;
}

static const struct of_device_id n71_triplet_of_match[] = {
    { .compatible = "research,n71-s8000-pcie-perst-held" },
    { }
};
MODULE_DEVICE_TABLE(of, n71_triplet_of_match);

static struct platform_driver n71_triplet_driver = {
    .probe = n71_microlease_probe,
    .driver = {
        .name = "n71-s8000-perst-held",
        .of_match_table = n71_triplet_of_match,
    },
};

static int __init n71_microlease_init(void)
{
    struct device_node *existing;
    int ret, roll;

    if (stage > 9 || !n71_validate_nodes() ||
        sizeof(n71_status_snapshot_dtbo) != n71_status_snapshot_dtbo_len)
        return -ENODEV;
    existing = of_find_node_by_path(N71_STATUS_SNAPSHOT_NODE);
    if (existing) {
        of_node_put(existing);
        return -EEXIST;
    }
    ret = of_overlay_fdt_apply(n71_status_snapshot_dtbo,
                               sizeof(n71_status_snapshot_dtbo),
                               &n71_overlay_id, NULL);
    if (ret) {
        if (n71_overlay_id)
            of_overlay_remove(&n71_overlay_id);
        return ret;
    }
    n71_overlay_present = true;
    ret = platform_driver_register(&n71_triplet_driver);
    if (!ret) {
        n71_driver_registered = true;
        platform_driver_unregister(&n71_triplet_driver);
        n71_driver_registered = false;
    }
    if (!ret && (!n71_probed || n71_probe_result))
        ret = n71_probed ? n71_probe_result : -ENODEV;
    roll = of_overlay_remove(&n71_overlay_id);
    if (!roll)
        n71_overlay_present = false;
    else
        pr_err("n71-status-snapshot: could not remove synthetic DT node rc=%d\n", roll);
    if (roll)
        return 0; /* keep module data pinned; retry cleanup on rmmod */
    if (ret)
        return ret;
    pr_info("n71-status-snapshot: synthetic DT added/removed, armed=%d, result=%d\n",
            armed, n71_probe_result);
    return 0;
}

static void __exit n71_microlease_exit(void)
{
    int ret;

    if (n71_driver_registered)
        platform_driver_unregister(&n71_triplet_driver);
    if (!n71_overlay_present)
        return;
    ret = of_overlay_remove(&n71_overlay_id);
    if (ret)
        pr_err("n71-status-snapshot: overlay removal failed rc=%d\n", ret);
}

module_init(n71_microlease_init);
module_exit(n71_microlease_exit);
MODULE_DESCRIPTION("N71 S8000 exclusive PERST-low WLAN PMGR ID3 experiment; never releases endpoint reset");
MODULE_LICENSE("GPL");
