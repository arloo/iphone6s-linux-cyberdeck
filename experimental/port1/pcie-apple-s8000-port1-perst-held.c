// SPDX-License-Identifier: GPL-2.0
/* N71/S8000: bounded PERST-low WLAN/PMGR/ID3 experiment.
 * Stages <=15 hold PERST LOW; stages16/18 are bounded release/reassert trials.
 * Stages<=26 avoid native PCI enumeration; stage27 scans only WLAN without binding.
 * No submitted endpoint DMA; selected DART state only.
 * Stage8 only reads the original DART1 packed TCR once under endpoint reset.
 * Source and physical test are board-specific; no analog voltage claim.
 */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/sizes.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/debugfs.h>
#include <linux/pci.h>
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
#include "n71-dart-ttbr-disabled-trial.h"
#include "n71-dart-owned-roots-trial.h"
#include "n71-port-local-trial.h"
#include "n71-port-aux-trial.h"
#include "n71-port-gating-trial.h"
#include "n71-port-calibration-trial.h"
#include "n71-port-config-readonly.h"
#include "n71-port-endpoint-id-trial.h"
#include "n71-endpoint-config-snapshot.h"
#include "n71-endpoint-bar-size-trial.h"
#include "n71-endpoint-mmio-trial.h"
#include "n71-endpoint-otp-snapshot.h"
#ifdef N71_PRIVATE_PORT1_CALIBRATION
#include "n71-private-port1-calibration.h"
#endif

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

/* No DART reset or PCI host access; stages16/18 briefly release PERST. */
static bool armed;
static unsigned int stage;
static bool n71_probed;
module_param(armed, bool, 0400);
module_param(stage, uint, 0400);
MODULE_PARM_DESC(armed, "exclusive PERST-low test, default false");
MODULE_PARM_DESC(stage, "0=PERST only,1=add WLAN,2=add PMGR status,3=ID3 status,4=ID2 enable,5=common init only,6=common+ID2,7=stable 250ms,8=add read-only DART1 TCR,9=read TTBR/command/fault,10=SID0 TTBR zero/restore,11=add TCR0 pulse under reset,12=SID0 TLB invalidate,13=owned empty roots,14=250ms owned-root dwell,15=port-local control,16=bounded PERST release/reassert,17=root aux diagnostic,18=REFCLK gating with release,19=owner original tuning,20=read-only port1 root PCI header,21=temporary WLAN bus1 endpoint ID,22=endpoint BAR/capability snapshot,23=bounded BAR sizing with decode OFF,24=memory-only chip ID read,25=quarantined OTP snapshot,26=ChipCommon metadata only,27=native PCI enumeration without binding");

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

struct n71_owned_tables {
    struct device *dev;
    void *page[4];
    dma_addr_t dma[4];
    bool mapped[4];
    u32 word[4];
};
static struct n71_owned_tables n71_tables;
static bool n71_roots_quarantined;
static void n71_owned_free(struct n71_owned_tables *t)
{
    unsigned int i;
    for (i = 0; i < 4; i++) {
        if (t->mapped[i])
            dma_unmap_single(t->dev, t->dma[i], PAGE_SIZE, DMA_TO_DEVICE);
        if (t->page[i]) free_page((unsigned long)t->page[i]);
    }
    if (t->dev) put_device(t->dev);
    memset(t, 0, sizeof(*t));
}
static int n71_owned_alloc(struct device *dev, struct n71_owned_tables *t, void __iomem *dart)
{
    unsigned int i, j;
    int ret;
    if (PAGE_SIZE < SZ_4K || (PAGE_SIZE % SZ_4K) || of_find_property(dev->of_node, "iommus", NULL))
        return -EPERM;
    ret = dma_coerce_mask_and_coherent(dev, DMA_BIT_MASK(36));
    if (ret) return ret;
    t->dev = get_device(dev);
    for (i = 0; i < 4; i++) {
        phys_addr_t pa;
        t->page[i] = (void *)__get_free_page(GFP_KERNEL);
        if (!t->page[i]) { ret = -ENOMEM; goto fail; }
        pa = virt_to_phys(t->page[i]);
        t->word[i] = n71_dart_owned_ttbr(pa);
        if (!t->word[i]) { ret = -EPERM; goto fail; }
        /* Kernel pages may be 16 KiB while each DART root is 4 KiB.
         * Reject overlap anywhere in the allocation BEFORE explicit zeroing. */
        for (j = 0; j < 16; j++) {
            phys_addr_t old_pa = (phys_addr_t)(readl((u8 __iomem *)dart + 0x40 + 4*j) & 0x00ffffffU) << 12;
            if (old_pa >= pa && old_pa < pa + PAGE_SIZE) { ret = -EBUSY; goto fail; }
        }
        memset(t->page[i], 0, PAGE_SIZE);
        for (j = 0; j < i; j++)
            if (t->word[j] == t->word[i]) { ret = -EPERM; goto fail; }
        t->dma[i] = dma_map_single(dev, t->page[i], PAGE_SIZE, DMA_TO_DEVICE);
        if (dma_mapping_error(dev, t->dma[i])) { ret = -EIO; goto fail; }
        t->mapped[i] = true;
        /* This synthetic device must use direct identity DMA; reject a bounce
         * buffer or an IOVA instead of encoding it as a physical TTBR. */
        if (t->dma[i] != pa) { ret = -EPERM; goto fail; }
        dma_sync_single_for_device(dev, t->dma[i], PAGE_SIZE, DMA_TO_DEVICE);
    }
    dma_wmb();
    pr_info("n71-perst-held: OWNED_ROOTS_ALLOCATED roots=4 table_bytes=16384 backing_bytes=%lu zero=1 direct_dma=1 pa36=1 addresses_redacted\n", 4UL * PAGE_SIZE);
    return 0;
fail:
    n71_owned_free(t);
    return ret;
}

struct n71_dart_trial_mmio { void __iomem *dart; void __iomem *ap; void __iomem *root; void __iomem *port; void __iomem *phy; void __iomem *cfg; void __iomem *endpoint; void __iomem *bar0; bool calibration; struct gpio_desc *perst_gpio; bool gating; bool aux; bool release; bool local; bool dwell; bool pulse; bool flush; bool owned; const u32 *roots; int pulse_rc; };
static unsigned int n71_trial_read(void *ctx, unsigned int off)
{ struct n71_dart_trial_mmio *m = ctx; return readl((u8 __iomem *)m->dart + off); }
static void n71_trial_write(void *ctx, unsigned int off, unsigned int value)
{ struct n71_dart_trial_mmio *m = ctx; writel(value, (u8 __iomem *)m->dart + off); }
static int n71_trial_perst(void *ctx)
{ struct n71_dart_trial_mmio *m = ctx; return readl((u8 __iomem *)m->ap + 4*161) == 0x00072202; }
static void n71_trial_delay(void *ctx) { msleep(25); }
static void n71_trial_tick(void *ctx) { udelay(1); }
static int n71_owned_active_hold(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    unsigned int i, j;
    for (i = 0; i < 25; i++) {
        msleep(10);
        if (!n71_trial_perst(ctx) || n71_trial_read(ctx, 0x0c) != 0x80 ||
            n71_trial_read(ctx, 0x00) != 0x102 ||
            (n71_trial_read(ctx, 0x10) & BIT(31)) ||
            readl((u8 __iomem *)m->root + 0x1ac) != 1 ||
            (readl((u8 __iomem *)m->root + 0x2c) & 0x11) != 0x11)
            return -EIO;
        for (j = 0; j < 4; j++)
            if (n71_trial_read(ctx, 0x40 + 4*j) != m->roots[j]) return -EIO;
    }
    pr_info("n71-perst-held: DART1_OWNED_ROOTS_ACTIVE_STABLE samples=25 TCR=00000080 command=00000102 PERST_LOW\n");
    return 0;
}
static unsigned int n71_port_read(void *ctx, unsigned int off)
{ struct n71_dart_trial_mmio *m = ctx; return readl((u8 __iomem *)m->port + off); }
static void n71_port_write(void *ctx, unsigned int off, unsigned int value)
{ struct n71_dart_trial_mmio *m = ctx; writel(value, (u8 __iomem *)m->port + off); }
static int n71_port_perst_level(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    u32 value = readl((u8 __iomem *)m->ap + 4*161);
    return value == 0x00072202 ? 0 : value == 0x00072203 ? 1 : -1;
}
static void n71_port_set_perst(void *ctx, int high)
{
    struct n71_dart_trial_mmio *m = ctx;
    gpiod_set_value_cansleep(m->perst_gpio, high);
    pr_info("n71-perst-held: PORT1_PERST_LEVEL requested=%d observed=%d\n", high, n71_port_perst_level(ctx));
}
static int n71_port_dart_ready(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    unsigned int j;
    if (n71_trial_read(ctx, 0x0c) != 0x80 || n71_trial_read(ctx, 0) != 0x102 ||
        (n71_trial_read(ctx, 0x10) & BIT(31)) ||
        readl((u8 __iomem *)m->root + 0x1ac) != 1 ||
        (readl((u8 __iomem *)m->root + 0x2c) & 0x11) != 0x11) return 0;
    for (j = 0; j < 4; j++)
        if (n71_trial_read(ctx, 0x40 + 4*j) != m->roots[j]) return 0;
    return 1;
}
static int n71_config_ready(void *ctx)
{
    return n71_port_perst_level(ctx) == 1 && n71_port_dart_ready(ctx) &&
           n71_port_read(ctx, 0x80) == 1 && (n71_port_read(ctx, 0x88) & 1);
}
static unsigned int n71_config_read(void *ctx, unsigned int off)
{
    struct n71_dart_trial_mmio *m = ctx;
    return readl((u8 __iomem *)m->cfg + off);
}
static void n71_root_bus_write(void *ctx, unsigned int value)
{
    struct n71_dart_trial_mmio *m = ctx;
    writel(value, (u8 __iomem *)m->cfg + 0x18);
}
static unsigned int n71_endpoint_read(void *ctx, unsigned int off)
{
    struct n71_dart_trial_mmio *m = ctx;
    return readl((u8 __iomem *)m->endpoint + off);
}
static void n71_endpoint_bar_write(void *ctx, unsigned int off, unsigned int value)
{
    struct n71_dart_trial_mmio *m = ctx;
    writel(value, (u8 __iomem *)m->endpoint + off);
}
static void n71_root_memory_write(void *ctx, unsigned int off, unsigned int value)
{ struct n71_dart_trial_mmio *m = ctx; writel(value, (u8 __iomem *)m->cfg + off); }
static void n71_root_command(void *ctx, unsigned int value)
{ struct n71_dart_trial_mmio *m = ctx; writew(value, (u8 __iomem *)m->cfg + 4); }
static void n71_endpoint_command(void *ctx, unsigned int value)
{ struct n71_dart_trial_mmio *m = ctx; writew(value, (u8 __iomem *)m->endpoint + 4); }
static unsigned int n71_chip_read(void *ctx)
{ struct n71_dart_trial_mmio *m = ctx; return readl(m->bar0); }
static u8 n71_otp_private[N71_OTP_MAX_BYTES];
static struct debugfs_blob_wrapper n71_otp_blob;
static struct dentry *n71_otp_file;
static unsigned int n71_chipcommon_read(void *ctx, unsigned int off)
{ struct n71_dart_trial_mmio *m = ctx; return readl((u8 __iomem *)m->bar0 + off); }
#include "n71-pci-core-enumerate.h"
static int n71_otp_observe(void *ctx)
{
    const struct n71_otp_ops o = { .ready = n71_config_ready, .read = n71_chipcommon_read };
    struct n71_otp_result r;
    int rc;
    if (stage == 27) return n71_pci_core_enumerate(ctx);
    if (stage == 26) {
        unsigned int caps, erom;
        if (!n71_config_ready(ctx)) return -EIO;
        pr_info("n71-perst-held: CHIPCOMMON_METADATA_BEGIN no_OTP_access\n");
        caps = n71_chipcommon_read(ctx, 4);
        pr_info("n71-perst-held: CHIPCOMMON_CAPABILITIES_READ value=%08x\n", caps);
        if (!n71_config_ready(ctx)) return -EIO;
        erom = n71_chipcommon_read(ctx, 0xfc);
        pr_info("n71-perst-held: CHIPCOMMON_METADATA_COMPLETE capabilities=%08x erom=%08x no_OTP_access\n", caps, erom);
        return n71_config_ready(ctx) ? 0 : -EIO;
    }
    if (stage != 25) return 0;
    rc = n71_endpoint_otp_snapshot(&o, ctx, n71_otp_private, &r);
    if (!rc) { n71_otp_blob.data = n71_otp_private; n71_otp_blob.size = r.bytes; }
    pr_info("n71-perst-held: ENDPOINT_OTP_SNAPSHOT rc=%d capabilities=%08x erom=%08x bytes=%u reads=%u PRIVATE_BYTES_NOT_LOGGED\n", rc, r.capabilities, r.erom, r.bytes, r.reads);
    return rc;
}
static int n71_mmio_observe(void *ctx)
{
    const struct n71_mmio_ops o = { .ready = n71_config_ready, .root_read = n71_config_read,
      .endpoint_read = n71_endpoint_read, .root_write = n71_root_memory_write,
      .endpoint_write = n71_endpoint_bar_write, .root_command = n71_root_command,
      .endpoint_command = n71_endpoint_command, .chip_read = n71_chip_read, .observe = n71_otp_observe };
    struct n71_mmio_result r;
    int rc = n71_endpoint_mmio_trial(&o, ctx, &r);
    pr_info("n71-perst-held: ENDPOINT_MMIO_TRIAL rc=%d chip=%08x chiprev=%u reads=%u restored=%u BUS_MASTER_NEVER_ENABLED\n",
            rc, r.chip, (r.chip >> 16) & 15, r.reads, r.restored);
    return rc;
}
static int n71_endpoint_bar_observe(void *ctx)
{
    const struct n71_bar_ops o = { .ready = n71_config_ready, .read = n71_endpoint_read, .write = n71_endpoint_bar_write };
    struct n71_bar_result r;
    int rc = n71_endpoint_bar_size_trial(&o, ctx, &r);
    pr_info("n71-perst-held: ENDPOINT_BAR_SIZE_TRIAL rc=%d size0=%x size2=%x mask0=%08x:%08x mask2=%08x:%08x restored=%u COMMAND_UNCHANGED_NO_MMIO_DMA\n",
            rc, r.size[0], r.size[1], r.mask_hi[0], r.mask_lo[0], r.mask_hi[1], r.mask_lo[1], r.restored);
    if (!rc && stage >= 24) rc = n71_mmio_observe(ctx);
    return rc;
}
static int n71_endpoint_extra_observe(void *ctx)
{
    const struct n71_snapshot_ops o = { .ready = n71_config_ready, .read = n71_endpoint_read };
    struct n71_snapshot r;
    int rc;
    if (stage < 22) return 0;
    rc = n71_endpoint_snapshot(&o, ctx, &r);
    pr_info("n71-perst-held: ENDPOINT_CONFIG_SNAPSHOT rc=%d header=%08x bars=%08x,%08x,%08x,%08x,%08x,%08x caps=%u pcie=%x link=%08x reads=%u no_BAR_write\n",
            rc, r.header, r.bars[0], r.bars[1], r.bars[2], r.bars[3], r.bars[4], r.bars[5], r.caps, r.pcie, r.link, r.reads);
    if (!rc && stage >= 23) rc = n71_endpoint_bar_observe(ctx);
    return rc;
}
static int n71_endpoint_observe(void *ctx)
{
    const struct n71_endpoint_ops o = { .ready = n71_config_ready,
        .root_read = n71_config_read, .root_bus_write = n71_root_bus_write,
        .endpoint_read = n71_endpoint_read, .observe = n71_endpoint_extra_observe };
    struct n71_endpoint_result r;
    int rc = n71_endpoint_id_trial(&o, ctx, &r);
    pr_info("n71-perst-held: ENDPOINT_ID_TRIAL rc=%d id=%08x command=%08x class_rev=%08x saved_bus=%08x restored=%u reads=%u BDF=01:00.0 command_untouched_DMA_not_submitted\n",
            rc, r.id, r.command, r.class_rev, r.saved_bus, r.restored, r.reads);
    return rc;
}
static int n71_config_observe(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    const struct n71_config_ro_ops o = { .ready = n71_config_ready, .read = n71_config_read };
    struct n71_config_ro_result r;
    int rc;
    if (!m->cfg) return 0;
    rc = n71_port_config_readonly(&o, ctx, &r);
    pr_info("n71-perst-held: ROOT_CONFIG_READONLY rc=%d id=%08x command=%08x class_rev=%08x buses=%08x reads=%u BDF=00:01.0 no_config_write_no_endpoint_request\n",
            rc, r.id, r.command, r.class_rev, r.buses, r.reads);
    if (!rc && m->endpoint) rc = n71_endpoint_observe(ctx);
    return rc;
}
static void n71_port_delay(void *ctx) { msleep(10); }
static unsigned int n71_aux_read(void *ctx, unsigned int off)
{ struct n71_dart_trial_mmio *m = ctx; return readl((u8 __iomem *)m->root + off); }
static void n71_aux_write(void *ctx, unsigned int off, unsigned int value)
{
    struct n71_dart_trial_mmio *m = ctx;
    u32 before = readl((u8 __iomem *)m->root + off);
    writel(value, (u8 __iomem *)m->root + off);
    pr_info("n71-perst-held: ROOT_AUX_WRITE off=%x before=%08x write=%08x after=%08x\n", off, before, value, readl((u8 __iomem *)m->root + off));
}
static unsigned int n71_calibration_read(void *ctx, unsigned int bank, unsigned int off)
{
    struct n71_dart_trial_mmio *m = ctx;
    void __iomem *base = bank == 0 ? m->root : bank == 1 ? m->phy : m->port;
    return readl((u8 __iomem *)base + off);
}
static void n71_calibration_write(void *ctx, unsigned int bank, unsigned int off, unsigned int value)
{
    struct n71_dart_trial_mmio *m = ctx;
    void __iomem *base = bank == 0 ? m->root : bank == 1 ? m->phy : m->port;
    writel(value, (u8 __iomem *)base + off);
}
static int n71_calibration_run(void *ctx, unsigned int *status, unsigned int *samples, unsigned int *restored)
{
    const struct n71_port_trial_ops p = {
        .read = n71_port_read, .write = n71_port_write, .perst_level = n71_port_perst_level,
        .set_perst = n71_port_set_perst, .dart_ready = n71_port_dart_ready, .delay = n71_port_delay, .observe = n71_config_observe,
    };
    const struct n71_port_aux_ops r = { .read = n71_aux_read, .write = n71_aux_write };
    unsigned int gate_restored;
    int rc = n71_port_gating_trial(&p, &r, ctx, status, samples, restored, &gate_restored);
    pr_info("n71-perst-held: PORT1_CALIBRATED_GATING rc=%d restored=%u\n", rc, gate_restored);
    return rc;
}
static int n71_port_active_hold(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    const struct n71_port_trial_ops ops = {
        .read = n71_port_read, .write = n71_port_write,
        .perst_level = n71_port_perst_level, .set_perst = n71_port_set_perst, .dart_ready = n71_port_dart_ready,
        .delay = n71_port_delay, .observe = n71_config_observe,
    };
    unsigned int status, samples, restored;
    int rc;
    if (m->calibration) {
#ifdef N71_PRIVATE_PORT1_CALIBRATION
        const struct n71_calib_ops c = {
            .read = n71_calibration_read, .write = n71_calibration_write,
            .perst_level = n71_port_perst_level, .dart_ready = n71_port_dart_ready,
            .run = n71_calibration_run,
        };
        unsigned int tuning_restored, written;
        rc = n71_port_calibration_trial(&c, ctx, n71_private_calibration,
                ARRAY_SIZE(n71_private_calibration), &status, &samples, &restored, &tuning_restored, &written);
        pr_info("n71-perst-held: ORIGINAL_TUNING_TRIAL rc=%d records=%zu written=%u restored=%u values_private\n", rc, ARRAY_SIZE(n71_private_calibration), written, tuning_restored);
#else
        return -EOPNOTSUPP;
#endif
    } else if (m->gating) {
        const struct n71_port_aux_ops root_ops = { .read = n71_aux_read, .write = n71_aux_write };
        unsigned int gating_restored;
        rc = n71_port_gating_trial(&ops, &root_ops, ctx, &status, &samples, &restored, &gating_restored);
        pr_info("n71-perst-held: PORT1_REFCLK_GATING_TRIAL rc=%d restored=%u other_port_id3_compared=3\n", rc, gating_restored);
    } else if (m->aux) {
        const struct n71_port_aux_ops aux = { .read = n71_aux_read, .write = n71_aux_write };
        unsigned int aux_restored;
        rc = n71_port_aux_trial(&ops, &aux, ctx, &status, &samples, &restored, &aux_restored);
        pr_info("n71-perst-held: PORT1_ROOT_AUX_TRIAL rc=%d restored=%u other_port_words_compared=3\n", rc, aux_restored);
    } else rc = n71_port_local_trial(&ops, ctx, m->release, &status, &samples, &restored);
    pr_info("n71-perst-held: PORT1_LOCAL_CONTROL_TRIAL rc=%d status88=%08x samples=%u restored=%u RESET_REASSERTED release_test=%u\n", rc, status, samples, restored, m->release);
    return rc;
}
static void n71_trial_hold(void *ctx)
{
    struct n71_dart_trial_mmio *m = ctx;
    const struct n71_dart_trial_ops o = {
        .read = n71_trial_read, .write = n71_trial_write,
        .perst_low = n71_trial_perst, .hold = n71_trial_delay, .tick = n71_trial_tick,
        .active_hold = m->local ? n71_port_active_hold : m->dwell ? n71_owned_active_hold : NULL,
    };
    if (m->owned) {
        unsigned int command, polls;
        m->pulse_rc = n71_dart_owned_roots_trial(&o, ctx, m->roots, &command, &polls);
        pr_info("n71-perst-held: DART1_OWNED_EMPTY_ROOTS rc=%d command=%08x polls=%u PERST_LOW no endpoint DMA\n", m->pulse_rc, command, polls);
    } else if (m->flush) {
        unsigned int command, polls;
        m->pulse_rc = n71_dart_tcr0_flush_trial(&o, ctx, &command, &polls);
        pr_info("n71-perst-held: DART1_SID0_TLB_INVALIDATE rc=%d command=%08x polls=%u PERST_LOW no DMA\n", m->pulse_rc, command, polls);
    } else if (m->pulse) {
        m->pulse_rc = n71_dart_tcr0_pulse(&o, ctx);
        pr_info("n71-perst-held: DART1_TCR0_PULSE rc=%d no TLB command or DMA\n", m->pulse_rc);
    } else n71_trial_delay(ctx);
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
    void __iomem *ap = NULL, *root = NULL, *dart1 = NULL, *port1 = NULL, *phy = NULL, *cfg = NULL, *endpoint = NULL, *bar0 = NULL;
    bool bar_region = false;
    u32 perst_saved, cached, protected_saved[ARRAY_SIZE(protected_pins)];
    u32 id1 = 0, id2 = 0, id3 = 0, id4 = 0, id5 = 0, after = 0;
    u32 lane_saved = 0, done_saved = 0, common_status = 0;
    u32 protected_root[3][4] = {};
    unsigned int j;
    bool common_changed = false, protected_controls_unchanged = true;
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
    root = ioremap(N71_ROOT_COMMON_PHYS, stage >= 17 ? 0x8000 : N71_ROOT_IOREMAP_BYTES);
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
                 * Initial snapshot is read-only; stages 10-14 below perform bounded writes.
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
                if (stage >= 9) {
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
                if (stage >= 10) {
                    if (stage >= 15) {
                        port1 = ioremap(0x602000000ULL, 0x4000);
                        if (!port1) { ret = -ENOMEM; goto restore; }
                        if (stage >= 19) {
                            phy = ioremap(0x600008000ULL, 0x4000);
                            if (!phy) { ret = -ENOMEM; goto restore; }
                        }
                    }
                    if (stage >= 20) {
                        /* Original Apple config address transform + original iOS reg:
                         * device1,function0,bus0 => shared ECAM + 0x8000.
                         * Root bridge header reads only, no global config writes.
                         */
                        cfg = ioremap(0x610008000ULL, 0x1000);
                        if (!cfg) { ret = -ENOMEM; goto restore; }
                    }
                    if (stage >= 21) {
                        endpoint = ioremap(0x610100000ULL, 0x1000);
                        if (!endpoint) { ret = -ENOMEM; goto restore; }
                    }
                    if (stage >= 24) {
                        if (!request_mem_region(0x7c0000000ULL, 0x800000, "n71-wlan-mmio-trial")) { ret = -EBUSY; goto restore; }
                        bar_region = true;
                        bar0 = ioremap(0x7c0000000ULL, 0x8000);
                        if (!bar0) { ret = -ENOMEM; goto restore; }
                    }
                    struct n71_dart_trial_mmio mm = { .dart = dart1, .ap = ap, .root = root, .port = port1, .phy = phy, .cfg = cfg, .endpoint = endpoint, .bar0 = bar0, .calibration = stage >= 19, .perst_gpio = perst, .gating = stage == 18, .aux = stage == 17, .release = stage >= 16, .local = stage >= 15, .dwell = stage == 14, .pulse = stage == 11, .flush = stage == 12, .owned = stage >= 13, .roots = n71_tables.word };
                    const struct n71_dart_trial_ops ops = {
                        .read = n71_trial_read, .write = n71_trial_write,
                        .perst_low = n71_trial_perst, .hold = n71_trial_hold,
                        .command_change_mask = stage >= 12 ? 0x00000f00U : 0,
                    };
                    unsigned int zero_ok, restore_ok;
                    int trial_rc;
                    if (stage >= 13) {
                        ret = n71_owned_alloc(&pdev->dev, &n71_tables, dart1);
                        if (ret) goto restore;
                        /* Never reuse a retained root's physical page, including
                         * a root belonging to another stream. */
                        for (i = 0; i < 16; i++)
                            for (j = 0; j < 4; j++)
                                if ((readl((u8 __iomem *)dart1 + 0x40 + 4*i) & 0x00ffffffU) ==
                                    (n71_tables.word[j] & 0x00ffffffU)) {
                                    n71_owned_free(&n71_tables);
                                    ret = -EBUSY;
                                    goto restore;
                                }
                    }
                    trial_rc = n71_dart_disabled_ttbr_trial(&ops, &mm, &zero_ok, &restore_ok);
                    if (stage >= 13) {
                        bool free_safe = restore_ok &&
                            readl((u8 __iomem *)dart1 + 0x0c) == 0 &&
                            !(readl((u8 __iomem *)dart1 + 0x00) & BIT(3));
                        bool pages_zero = true;
                        for (j = 0; j < 4; j++) {
                            dma_sync_single_for_cpu(n71_tables.dev, n71_tables.dma[j], PAGE_SIZE, DMA_TO_DEVICE);
                            if (memchr_inv(n71_tables.page[j], 0, PAGE_SIZE)) pages_zero = false;
                        }
                        if (free_safe) {
                            n71_owned_free(&n71_tables);
                            pr_info("n71-perst-held: OWNED_ROOTS_RELEASED after_restore=1 zero_unchanged=%u\n", pages_zero);
                        } else {
                            n71_roots_quarantined = true;
                            __module_get(THIS_MODULE);
                            pr_err("n71-perst-held: OWNED_ROOTS_QUARANTINED module pinned; no free or retry\n");
                        }
                        if (!free_safe || !pages_zero) mm.pulse_rc = -EIO;
                    }
                    pr_info("n71-perst-held: DART1_SID0_TTBR_DISABLED_TRIAL zero_pass=%u restore_pass=%u rc=%d; TCR_DISABLED PERST_LOW no DMA\n",
                            zero_ok, restore_ok, trial_rc);
                    if (trial_rc || mm.pulse_rc) { ret = -EIO; goto restore; }
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
                    protected_controls_unchanged = false;
                    pr_err("n71-perst-held: protected root port%u register%u changed\n",
                            protected_ports[i], j);
                    ret = -EIO;
                }
        pr_info("n71-perst-held: COMMON_RESTORED lane=%08x done=%08x protected_port_controls_unchanged=%u\n",
                readl((u8 __iomem *)root + 0x004),
                readl((u8 __iomem *)root + 0x038), protected_controls_unchanged);
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
    if (bar0)
        iounmap(bar0);
    if (bar_region)
        release_mem_region(0x7c0000000ULL, 0x800000);
    if (endpoint)
        iounmap(endpoint);
    if (cfg)
        iounmap(cfg);
    if (phy)
        iounmap(phy);
    if (port1)
        iounmap(port1);
    if (dart1)
        iounmap(dart1);
    if (root)
        iounmap(root);
    if (ap)
        iounmap(ap);
    if (ap_dev)
        put_device(&ap_dev->dev);
    n71_probe_result = ret;
    pr_info("n71-perst-held: COMPLETE rc=%d stage=%u ID5_READY=%u POLL_RC=%d; RESET_RELEASE_TEST=%u DART_TTBR_WRITE_TEST=%u native_pci_scan=%u no_submitted_DMA\n",
            ret, stage, poll_rc == 0, poll_rc, stage >= 16, stage >= 10, stage >= 27);
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

    #ifndef N71_PRIVATE_PORT1_CALIBRATION
    if (stage >= 19) return -EOPNOTSUPP;
    #endif
    /* OTP capture lost USB before any verified result; quarantine pending console evidence. */
    if (stage == 25) return -EOPNOTSUPP;
    if (stage > 27 || !n71_validate_nodes() ||
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
    if (n71_roots_quarantined)
        return 0; /* pin module and table pages after failed rollback */
    if (ret)
        return ret;
    if (n71_otp_blob.size)
        n71_otp_file = debugfs_create_blob("n71-wlan-otp-private", 0400, NULL, &n71_otp_blob);
    pr_info("n71-status-snapshot: synthetic DT added/removed, armed=%d, result=%d\n",
            armed, n71_probe_result);
    return 0;
}

static void __exit n71_microlease_exit(void)
{
    int ret;
    debugfs_remove(n71_otp_file);
    memzero_explicit(n71_otp_private, sizeof(n71_otp_private));

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
MODULE_DESCRIPTION("N71 S8000 exclusive PERST-low WLAN PMGR ID3 experiment; bounded endpoint reset trials with rollback");
MODULE_LICENSE("GPL");
