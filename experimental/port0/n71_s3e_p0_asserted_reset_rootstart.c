// SPDX-License-Identifier: GPL-2.0
/*
 * N71/S8000 owner-supervised storage port0 research pilot.
 * Default modes keep NAND GPIO160 OUTPUT LOW while temporarily powering
 * port0 and applying source-verified root controls. Optional DART0 modes
 * program Linux-owned empty roots and restore the inherited TTBR state.
 * Explicit endpoint_id_trial may release PERST only inside active empty
 * roots on all four DART0 streams. It reads three endpoint config words
 * through temporarily reserved bus2. Optional bar0_size_trial sizes and
 * restores BAR0 with decode/master OFF. Optional nvme_mmio_trial maps
 * an exclusively reserved BAR0 and reads five NVMe DWORDs with MSE only.
 * It then restores routing, reasserts
 * reset and restores local0x80 before the DART guard can be removed.
 * Root controls and PMGR return to baseline before restoring GPIO INPUT.
 * Failed rollback retains tables, module, power consumer and GPIO claim.
 * Optional nvmmu_owned_tables nests owned TCB/aux roots and bounded
 * invalidation around the endpoint observer, restoring inherited roots.
 * Optional ans_hmb_ro reads vendor HMB descriptors while both commands
 * are MSE-only and CC/CSTS are zero; GPIO141 is sampled without changes.
 * The separate ans_hmb_owned mode permits bounded SART/HMB writes.
 * Explicit ans_identify_once adds owned queues and a single Identify NS1,
 * with BME/CC.EN enabled only after all DMA owners and guards qualify.
 * No block I/O or NAND host-write opcode is available.
 */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/sizes.h>
#include "../port1/n71-dart-all-stream-owned-roots-trial.h"
#include "../port1/n71-port-local-trial.h"
#include "n71_s3e_endpoint_cfg_ro.h"
#include "n71_s3e_bar0_size.h"
#include "n71_s3e_nvme_mmio_ro.h"
#include "n71_s3e_ans_hmb_ro.h"
#include "n71_s3e_sart_hmb_owned.h"
#include "n71_s3e_nvmmu_owned_tables.h"
#include "n71_s3e_dma_retirement_boundary.h"
#include <linux/ioport.h>
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
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/of_platform.h>

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
#define DART0_PHYS 0x601008000ULL
#define NVMMU0_PHYS 0x601004000ULL
#define P0_PORT_PHYS 0x601000000ULL
#define P0_ROOT_ECAM_PHYS 0x610000000ULL
#define P0_EP_BUS2_ECAM_PHYS 0x610200000ULL
#define S3E_BAR0_CPU_PHYS 0x7c1000000ULL
#define S8000_PINCTRL_PHYS 0x20f100000ULL
#define DWELL_MS 25U
#define S8000_GPIO_CHIP "20f100000.pinctrl"
#define S8000_GPIO160_ORIGINAL 0x00072200U
#define S8000_GPIO160_ASSERTED_LOW 0x00072202U
#define S8000_GPIO161_WIFI 0x00072203U
#define S8000_PINCTRL_PROVIDER "/soc/pinctrl@20f100000"
#define S8000_GPIO160_OFFSET (4U * 160U)
#define S8000_GPIO_MUTABLE_MASK (GENMASK(6,5) | GENMASK(3,0) | BIT(9))
#define ACTUAL(r) (((r) >> 4) & 15U)
#define TARGET(r) ((r) & 15U)

static bool armed;
static bool sample_root;
static bool sample_iommu;
static bool stock_nvme_mode;
static bool rootstart_p0;
static bool assert_storage_reset;
static bool stock_late_controls;
static bool dart0_owned_roots;
static bool dart0_all_streams;
static bool observe_p0_config;
static bool endpoint_id_trial;
static bool bar0_size_trial;
static bool nvme_mmio_trial;
static bool nvmmu_owned_tables;
static bool ans_hmb_ro;
static bool ans_hmb_owned;
static bool ans_identify_once;
/* Conservative latch: set before an admin BME write; never clear on error,
 * shutdown or disable. The read-only opt-in remains a second denial signal. */
static bool n71_admin_dma_epoch_latched;
/* The queue-only retirement pilot is explicitly opt-in, never automatic.
 * It always retains all DMA, HMB, DART and NVMMU backing allocations. */
static bool ans_queue_retire_probe;
/* Read-only interrupt mask snapshots; not queue retirement permission. */
static bool ans_phase_trace_ro;
/* Optional post-stop RAM-only witness: detects late changes, never proves quiet. */
static bool ans_late_dma_probe_ro;
module_param(ans_late_dma_probe_ro, bool, 0400);
MODULE_PARM_DESC(ans_late_dma_probe_ro, "bounded post-stop CQ/data fingerprint observation; no DMA retirement authority");
module_param(ans_phase_trace_ro, bool, 0400);
MODULE_PARM_DESC(ans_phase_trace_ro, "read-only INTMS/PERST at CC transitions, never queue writes or DMA release");
module_param(ans_queue_retire_probe, bool, 0400);
MODULE_PARM_DESC(ans_queue_retire_probe, "one-shot post-shutdown NVMe admin queue register zeroing, only after all ownership/shutdown guards; DMA and power remain quarantined");
module_param(ans_identify_once, bool, 0400);
MODULE_PARM_DESC(ans_identify_once, "single Identify NS1 with owned HMB/DART queues/FlatDMA; explicitly permits bounded BME/CC.EN then qualified shutdown, no block I/O");
module_param(ans_hmb_owned, bool, 0400);
MODULE_PARM_DESC(ans_hmb_owned, "owned contiguous 8 MiB HMB/SART plus reversible HMB descriptor programming; controller and bus mastering remain OFF unless ans_identify_once is also enabled");
module_param(ans_hmb_ro, bool, 0400);
MODULE_PARM_DESC(ans_hmb_ro, "read ANS HMB descriptor only inside owned NVMMU/DART guards with MSE-only BAR0; no NVMe writes or bus mastering");
module_param(nvmmu_owned_tables, bool, 0400);
MODULE_PARM_DESC(nvmmu_owned_tables, "temporary owned NVMMU TCB/aux roots with bounded invalidate and complete restoration inside all-stream DART guard");
static void __iomem *n71_nvme_mmio;
static bool n71_nvme_region_held;
module_param(nvme_mmio_trial, bool, 0400);
MODULE_PARM_DESC(nvme_mmio_trial, "five read-only NVMe register words through isolated BAR0; MSE only, bus mastering OFF, complete PCI rollback");
module_param(bar0_size_trial, bool, 0400);
MODULE_PARM_DESC(bar0_size_trial, "probe and restore only S3E BAR0 geometry while both decode and bus mastering are disabled");
module_param(endpoint_id_trial, bool, 0400);
MODULE_PARM_DESC(endpoint_id_trial, "bounded NAND PERST release/reassert inside all-stream DART0 empty roots; bus2 temporary endpoint config ID reads only");
module_param(observe_p0_config, bool, 0400);
MODULE_PARM_DESC(observe_p0_config, "six read-only root0 PCI config/local samples while all DART0 empty roots active and NAND reset asserted");
module_param(dart0_all_streams, bool, 0400);
MODULE_PARM_DESC(dart0_all_streams, "extend empty-root transaction to all four exclusive DART0 streams; requires dart0_owned_roots and asserted NAND reset");
module_param(dart0_owned_roots, bool, 0400);
MODULE_PARM_DESC(dart0_owned_roots, "temporary Linux-owned empty SID0 DART0 roots and bounded TLB flush; NAND reset stays OUTPUT LOW; no endpoint DMA");
module_param(stock_late_controls, bool, 0400);
MODULE_PARM_DESC(stock_late_controls, "bounded port0 ID2 bit8 clear and ID4 bit0 set while NAND GPIO160 remains OUTPUT LOW; always reverse-restore");
module_param(assert_storage_reset, bool, 0400);
MODULE_PARM_DESC(assert_storage_reset, "exclusively hold storage GPIO160 OUTPUT LOW during port0 power and restore exact original input mode");
module_param(rootstart_p0, bool, 0400);
MODULE_PARM_DESC(rootstart_p0, "owner supervised S8000 port0 ID3 then ID2 under PERST low and synchronous rollback");
module_param(stock_nvme_mode, bool, 0400);
MODULE_PARM_DESC(stock_nvme_mode, "one-shot stock S8000 port0 NVMe mode0x24=1 with physical reset held, always rollback");
module_param(sample_iommu, bool, 0400);
MODULE_PARM_DESC(sample_iommu, "read existing DART0/NVMMU0 controller state only, while link0 PMGR on");
module_param(armed, bool, 0400);
module_param(sample_root, bool, 0400);
MODULE_PARM_DESC(armed, "requires owner authorization and encrypted iOS backup; default inert");
MODULE_PARM_DESC(sample_root, "read-only stock-proven S8000 PCIe root status during power lease");

static struct platform_device *n71_consumer;
static bool n71_bound;
static bool n71_pm_enabled;
static bool n71_unreleased;
static struct device_node *n71_p0;
static struct platform_device *n71_reset_pdev;
static struct gpio_desc *n71_reset_pin;
static struct regmap *n71_pinctrl_regmap;
static bool n71_reset_lookup_added;
static bool n71_reset_claimed;
static bool n71_pin_ref_held;
static struct gpiod_lookup_table n71_reset_gpio_lookup = {
    .dev_id = "n71-s3e-p0-reset",
    .table = {
        GPIO_LOOKUP(S8000_GPIO_CHIP, 160, "s3e-reset", GPIO_ACTIVE_HIGH),
        { },
    },
};

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

struct n71_owned_tables {
    struct device *dev;
    void *page[16];
    dma_addr_t dma[16];
    bool mapped[16];
    u32 word[16];
    unsigned int count;
};
static struct n71_owned_tables n71_tables;
static void n71_owned_free(struct n71_owned_tables *t)
{
    unsigned int i;
    for (i = 0; i < 16; i++) {
        if (t->mapped[i])
            dma_unmap_single(t->dev, t->dma[i], PAGE_SIZE, DMA_TO_DEVICE);
        if (t->page[i]) free_page((unsigned long)t->page[i]);
    }
    if (t->dev) put_device(t->dev);
    memset(t, 0, sizeof(*t));
}
static int n71_owned_alloc(struct device *dev, struct n71_owned_tables *t, void __iomem *dart, unsigned int count)
{
    unsigned int i, j;
    int ret;
    if ((count!=4 && count!=16) || PAGE_SIZE < SZ_4K || (PAGE_SIZE % SZ_4K) || of_find_property(dev->of_node, "iommus", NULL))
        return -EPERM;
    ret = dma_coerce_mask_and_coherent(dev, DMA_BIT_MASK(36));
    if (ret) return ret;
    t->dev = get_device(dev);
    t->count=count;
    for (i = 0; i < count; i++) {
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
    pr_info("n71-s3e-p0: OWNED_ROOTS_ALLOCATED roots=%u table_bytes=%lu backing_bytes=%lu zero=1 direct_dma=1 pa36=1 addresses_redacted\n", count, (unsigned long)count*SZ_4K, (unsigned long)count*PAGE_SIZE);
    return 0;
fail:
    n71_owned_free(t);
    return ret;
}

struct n71_storage_dart_context {
    void __iomem *dart;
    void __iomem *pinctrl;
    int inner_rc;
    bool all_streams;
    void __iomem *cfg,*local,*endpoint,*nvmmu;
    phys_addr_t inherited_dart_pa[16];
    phys_addr_t inherited_nvmmu_pa[2];
};
static unsigned int n71_storage_dart_read(void *ctx, unsigned int off)
{
    struct n71_storage_dart_context *m=ctx;
    return readl((u8 __iomem *)m->dart+off);
}
static void n71_storage_dart_write(void *ctx, unsigned int off, unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    /* Restrict writes to command, packed TCR and SID0's four TTBR cells. */
    if (WARN_ON_ONCE(off!=0 && off!=0x0c &&
            (off<0x40 || off>(m->all_streams ? 0x7c : 0x4c) || (off & 3)))) return;
    writel(val,(u8 __iomem *)m->dart+off);
}
static int n71_storage_dart_perst(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    return n71_reset_claimed && n71_reset_pin &&
        readl((u8 __iomem *)m->pinctrl+S8000_GPIO160_OFFSET)==
            S8000_GPIO160_ASSERTED_LOW &&
        gpiod_get_direction(n71_reset_pin)==0 &&
        gpiod_get_value_cansleep(n71_reset_pin)==0;
}
static void n71_storage_dart_tick(void *ctx) { udelay(1); }
static void n71_storage_dart_delay(void *ctx) { udelay(100); }
static int n71_storage_full_dart_guard(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int j;
    if (!m->all_streams || readl((u8 __iomem *)m->dart+0x0c)!=0x80808080U ||
        readl(m->dart)!=0xf02U ||
        (readl((u8 __iomem *)m->dart+0x10)&BIT(31))) return 0;
    for (j=0;j<16;j++)
        if (readl((u8 __iomem *)m->dart+0x40+4*j)!=n71_tables.word[j]) return 0;
    return 1;
}
static int n71_storage_reset_level(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    u32 v=readl((u8 __iomem *)m->pinctrl+S8000_GPIO160_OFFSET);
    if (!n71_reset_claimed || !n71_reset_pin ||
        gpiod_get_direction(n71_reset_pin)!=0) return -1;
    return v==S8000_GPIO160_ASSERTED_LOW ? 0 :
           v==(S8000_GPIO160_ASSERTED_LOW|1U) ? 1 : -1;
}
static void n71_storage_set_reset(void *ctx,int high)
{
    if (high && (!endpoint_id_trial || !n71_storage_full_dart_guard(ctx))) return;
    gpiod_set_value_cansleep(n71_reset_pin,high);
    pr_info("n71-s3e-p0: NAND_PERST_BOUNDED_TRIAL requested=%d observed=%d\n",
            high,n71_storage_reset_level(ctx));
}
static unsigned int n71_storage_local_read(void *ctx,unsigned int off)
{
    struct n71_storage_dart_context *m=ctx;
    return readl((u8 __iomem *)m->local+off);
}
static void n71_storage_local_write(void *ctx,unsigned int off,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE(off!=0x80 || val>1)) return;
    writel(val,(u8 __iomem *)m->local+off);
}
static void n71_storage_link_tick(void *ctx) {msleep(4);}
static int n71_storage_endpoint_ready(void *ctx)
{
    return n71_storage_reset_level(ctx)==1 && n71_storage_full_dart_guard(ctx) &&
        n71_storage_local_read(ctx,0x80)==1 &&
        (n71_storage_local_read(ctx,0x88)&1);
}
static unsigned int n71_storage_root_read(void *ctx,unsigned int off)
{
    struct n71_storage_dart_context *m=ctx;
    return readl((u8 __iomem *)m->cfg+off);
}
static void n71_storage_root_bus_write(void *ctx,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    writel(val,(u8 __iomem *)m->cfg+0x18);
}
static unsigned int n71_storage_endpoint_read(void *ctx,unsigned int off)
{
    struct n71_storage_dart_context *m=ctx;
    return readl((u8 __iomem *)m->endpoint+off);
}
static void n71_storage_endpoint_bar_write(void *ctx,unsigned int off,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE(off!=0x10 && off!=0x14)) return;
    writel(val,(u8 __iomem *)m->endpoint+off);
}
static void n71_storage_root_window(void *ctx,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    writel(val,(u8 __iomem *)m->cfg+0x20);
}
static void n71_storage_root_command(void *ctx,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE(val!=0 && val!=2)) return;
    writew(val,(u8 __iomem *)m->cfg+4);
}
static void n71_storage_endpoint_command(void *ctx,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE(val!=0 && val!=2)) return;
    writew(val,(u8 __iomem *)m->endpoint+4);
}
static unsigned int n71_storage_nvme_read(void *ctx,unsigned int off)
{
    if (WARN_ON_ONCE(!n71_nvme_mmio ||
        (off!=0 && off!=4 && off!=8 && off!=0x14 && off!=0x1c))) return ~0U;
    return readl((u8 __iomem *)n71_nvme_mmio+off);
}
struct n71_nvmmu_owned_memory {
    struct device *dev;
    void *page[2];
    dma_addr_t dma[2];
    bool mapped[2];
};
static struct n71_nvmmu_owned_memory n71_nvmmu_memory;
static struct {
    void *page;
    dma_addr_t dma;
    bool mapped;
    u64 inherited_pa,inherited_size;
} n71_hmb_memory;
static int n71_storage_ans_hmb_ready(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    if (!ans_hmb_ro || !nvmmu_owned_tables || !m->nvmmu ||
        !n71_nvme_mmio || !n71_nvmmu_memory.dev ||
        !n71_nvmmu_memory.mapped[0] || !n71_nvmmu_memory.mapped[1] ||
        !n71_storage_endpoint_ready(ctx) ||
        (n71_storage_root_read(ctx,4)&0xffffU)!=2 ||
        (n71_storage_endpoint_read(ctx,4)&0xffffU)!=2 ||
        n71_storage_nvme_read(ctx,0x14) || n71_storage_nvme_read(ctx,0x1c) ||
        readl(m->nvmmu)!=1 || readl((u8 __iomem *)m->nvmmu+4)!=0)
        return 0;
    return readl((u8 __iomem *)m->nvmmu+8)==lower_32_bits(n71_nvmmu_memory.dma[0]) &&
        readl((u8 __iomem *)m->nvmmu+0x0c)==upper_32_bits(n71_nvmmu_memory.dma[0]) &&
        readl((u8 __iomem *)m->nvmmu+0x10)==lower_32_bits(n71_nvmmu_memory.dma[1]) &&
        readl((u8 __iomem *)m->nvmmu+0x14)==upper_32_bits(n71_nvmmu_memory.dma[1]);
}
static unsigned int n71_storage_ans_hmb_read(void *ctx,unsigned int off)
{
    if (WARN_ON_ONCE(!n71_storage_ans_hmb_ready(ctx) ||
        (off!=0x1808 && off!=0x1810 && off!=0x1814 && off!=0x1818))) return ~0U;
    return readl((u8 __iomem *)n71_nvme_mmio+off);
}
static int n71_storage_hmb_owned_ready(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    return n71_hmb_memory.page && n71_hmb_memory.mapped &&
        n71_storage_ans_hmb_ready(ctx) &&
        readl((u8 __iomem *)m->nvmmu+0x20)==1 &&
        readl((u8 __iomem *)m->nvmmu+0x24)==0xbc000000U &&
        readl((u8 __iomem *)m->nvmmu+0x28)==0xbc700000U &&
        readl((u8 __iomem *)m->nvmmu+0x2c)==(n71_hmb_memory.dma>>20);
}
#include "n71_s3e_admin_identify_once.h"
static int n71_storage_hmb_descriptor_owned(void *ctx)
{
    int rc=0;
    unsigned int req;
    if (!n71_storage_hmb_owned_ready(ctx)) return -EPERM;
    req=n71_storage_ans_hmb_read(ctx,0x1808);
    if (req!=SZ_8M || n71_storage_ans_hmb_read(ctx,0x1810) ||
        n71_storage_ans_hmb_read(ctx,0x1814) ||
        n71_storage_ans_hmb_read(ctx,0x1818)) return -EPROTO;
    /* Explicit Identify mode follows Apple's INIT-before-HMB sequence. */
    if (ans_identify_once) {
        writel(0,(u8 __iomem *)n71_nvme_mmio+0x1800);
        readl((u8 __iomem *)n71_nvme_mmio+0x1800);
    }
    /* HMB-only mode never writes INIT, CC or a doorbell. */
    writel(0,(u8 __iomem *)n71_nvme_mmio+0x1814);
    writel(0xbc000000U,(u8 __iomem *)n71_nvme_mmio+0x1810);
    writel(SZ_8M,(u8 __iomem *)n71_nvme_mmio+0x1818);
    if (!n71_storage_hmb_owned_ready(ctx) ||
        n71_storage_ans_hmb_read(ctx,0x1810)!=0xbc000000U ||
        n71_storage_ans_hmb_read(ctx,0x1814) ||
        n71_storage_ans_hmb_read(ctx,0x1818)!=SZ_8M) rc=-EIO;
    if (!rc && ans_identify_once) rc=n71_storage_admin_identify_once(ctx);
    if (rc==-3 || !n71_storage_hmb_owned_ready(ctx)) return -3;
    writel(0,(u8 __iomem *)n71_nvme_mmio+0x1818);
    writel(0,(u8 __iomem *)n71_nvme_mmio+0x1814);
    writel(0,(u8 __iomem *)n71_nvme_mmio+0x1810);
    if (n71_storage_ans_hmb_read(ctx,0x1810) ||
        n71_storage_ans_hmb_read(ctx,0x1814) ||
        n71_storage_ans_hmb_read(ctx,0x1818) ||
        !n71_storage_hmb_owned_ready(ctx)) return -3;
    pr_info("n71-s3e-p0: HMB_DESCRIPTOR_OWNED rc=%d bytes=%u restored=1 controller_disabled=YES BME_OFF=YES no_NVMe_command=%s\n",rc,SZ_8M,ans_identify_once ? "NO_identify_opt_in" : "YES");
    return rc;
}
static int n71_storage_ans_hmb_observe(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    const struct n71_ans_hmb_ops o={
        .ready=n71_storage_ans_hmb_ready,.read=n71_storage_ans_hmb_read,
    };
    struct n71_ans_hmb_result r;
    unsigned int strap_before,strap_after;
    int rc;
    /* Original N71 ADT function-boot_from_host names GPIO141.
     * Read the pin only. Its direction and level are never changed here. */
    strap_before=readl((u8 __iomem *)m->pinctrl+4U*141U);
    rc=n71_ans_hmb_ro(&o,ctx,&r);
    strap_after=readl((u8 __iomem *)m->pinctrl+4U*141U);
    pr_info("n71-s3e-p0: ANS_HMB_READONLY rc=%d requested_bytes=%u configured_bytes=%u base_present=%u reads=%u stable=%u nonzero=%u aligned_4k=%u controller_disabled=YES bus_mastering_OFF=YES addresses_redacted=YES\n",
        rc,r.request,r.size,!!(r.base_lo|r.base_hi),r.reads,r.stable,r.nonzero,r.aligned);
    pr_info("n71-s3e-p0: ANS_BOOT_FROM_HOST_GPIO141 before=%08x after=%08x unchanged=%u read_only=YES\n",
        strap_before,strap_after,strap_before==strap_after);
    if (!rc && strap_before!=strap_after) rc=-EIO;
    if (!rc && ans_hmb_owned) rc=n71_storage_hmb_descriptor_owned(ctx);
    return rc;
}
static int n71_storage_nvme_mmio_observe(void *ctx)
{
    const struct n71_s3e_mmio_ops ops={
        .ready=n71_storage_endpoint_ready,.root_read=n71_storage_root_read,
        .endpoint_read=n71_storage_endpoint_read,
        .root_window=n71_storage_root_window,.endpoint_bar=n71_storage_endpoint_bar_write,
        .root_command=n71_storage_root_command,.endpoint_command=n71_storage_endpoint_command,
        .nvme_read=n71_storage_nvme_read,
        .active_readonly=ans_hmb_ro ? n71_storage_ans_hmb_observe : NULL,
    };
    struct n71_s3e_mmio_result r;
    int rc;
    if (n71_nvme_region_held || n71_nvme_mmio) return -EALREADY;
    if (!request_mem_region(S3E_BAR0_CPU_PHYS,SZ_16K,"n71-s3e-bar0-readonly"))
        return -EBUSY;
    n71_nvme_region_held=true;
    n71_nvme_mmio=ioremap(S3E_BAR0_CPU_PHYS,SZ_16K);
    if (!n71_nvme_mmio) {
        release_mem_region(S3E_BAR0_CPU_PHYS,SZ_16K);
        n71_nvme_region_held=false;return -ENOMEM;
    }
    rc=n71_s3e_nvme_mmio_ro_trial(&ops,ctx,&r);
    pr_info("n71-s3e-p0: S3E_MMIO_GUARD stage=%u root_window=%08x pref_window=%08x pref_base_hi=%08x pref_limit_hi=%08x\n",
        r.stage,r.root_window,r.pref_window,r.pref_hi_base,r.pref_hi_limit);
    pr_info("n71-s3e-p0: S3E_NVME_MMIO_READONLY rc=%d cap_hi=%08x cap_lo=%08x vs=%08x cc=%08x csts=%08x reads=%u restored=%u bus_mastering_never_enabled=%s\n",
        rc,r.cap_hi,r.cap_lo,r.vs,r.cc,r.csts,r.reads,r.restored,
        ans_identify_once ? "NO_identify_opt_in" : "YES");
    if (rc==-3) {
        pr_err("n71-s3e-p0: BAR0_MMIO_RESOURCE_QUARANTINED_KEEP_MAPPING_AND_DART_ROOTS\n");
        return rc;
    }
    iounmap(n71_nvme_mmio);n71_nvme_mmio=NULL;
    release_mem_region(S3E_BAR0_CPU_PHYS,SZ_16K);n71_nvme_region_held=false;
    return rc;
}
static int n71_storage_bar0_observe(void *ctx)
{
    const struct n71_s3e_bar_ops ops={
        .ready=n71_storage_endpoint_ready,.read=n71_storage_endpoint_read,
        .write=n71_storage_endpoint_bar_write,
    };
    struct n71_s3e_bar_result r;
    int rc;
    if ((n71_storage_root_read(ctx,4)&0xffffU)!=0) return -EPERM;
    rc=n71_s3e_bar0_size_trial(&ops,ctx,&r);
    pr_info("n71-s3e-p0: S3E_BAR0_SIZE_TRIAL rc=%d lo=%08x hi=%08x mask_lo=%08x mask_hi=%08x is64=%u bytes=%llu restored=%u decode_and_master_OFF=YES\n",
        rc,r.lo,r.hi,r.mask_lo,r.mask_hi,r.is64,r.size,r.restored);
    if (!rc && nvme_mmio_trial) {
        if (!r.is64 || r.size!=SZ_16K) return -EPROTO;
        rc=n71_storage_nvme_mmio_observe(ctx);
    }
    return rc;
}
static int n71_storage_endpoint_identify(void *ctx)
{
    const struct n71_s3e_cfg_ops o={
        .ready=n71_storage_endpoint_ready,.root_read=n71_storage_root_read,
        .root_bus_write=n71_storage_root_bus_write,
        .endpoint_read=n71_storage_endpoint_read,
        .observe=bar0_size_trial ? n71_storage_bar0_observe : NULL,
    };
    struct n71_s3e_cfg_result r;
    int rc=n71_s3e_endpoint_cfg_trial(&o,ctx,&r);
    pr_info("n71-s3e-p0: S3E_ENDPOINT_CFG_READONLY rc=%d id=%08x command_status=%08x class_rev=%08x reads=%u buses_restored=%u\n",
            rc,r.id,r.command,r.class_rev,r.reads,r.restored);
    return rc;
}
static int n71_storage_endpoint_release_trial(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    const struct n71_port_trial_ops ops={
        .read=n71_storage_local_read,.write=n71_storage_local_write,
        .perst_level=n71_storage_reset_level,.set_perst=n71_storage_set_reset,
        .dart_ready=n71_storage_full_dart_guard,.delay=n71_storage_link_tick,
        .observe=n71_storage_endpoint_identify,
    };
    unsigned int status,samples,restored;
    int rc;
    if (n71_storage_root_read(ctx,0)!=0x1003106bU ||
        (n71_storage_root_read(ctx,4)&0xffffU)!=0 ||
        (n71_storage_root_read(ctx,0x18)&0x00ffffffU)!=0 ||
        n71_storage_reset_level(ctx)!=0 || !n71_storage_full_dart_guard(ctx))
        return -EPERM;
    m->endpoint=ioremap(P0_EP_BUS2_ECAM_PHYS,0x1000);
    if (!m->endpoint) return -ENOMEM;
    rc=n71_port_local_trial(&ops,ctx,1,&status,&samples,&restored);
    if (!restored || n71_storage_reset_level(ctx)!=0) rc=-3;
    pr_info("n71-s3e-p0: S3E_BOUNDED_RELEASE_TRIAL rc=%d local_status=%08x samples=%u local80_restored=%u NAND_RESET_LOW=%u\n",
        rc,status,samples,restored,n71_storage_reset_level(ctx)==0);
    iounmap(m->endpoint);m->endpoint=NULL;
    return rc;
}

static void n71_storage_hmb_free(void)
{
    if (n71_hmb_memory.mapped)
        dma_unmap_single(n71_nvmmu_memory.dev,n71_hmb_memory.dma,SZ_8M,DMA_BIDIRECTIONAL);
    if (n71_hmb_memory.page)
        free_pages((unsigned long)n71_hmb_memory.page,get_order(SZ_8M));
    memset(&n71_hmb_memory,0,sizeof(n71_hmb_memory));
}
static int n71_storage_hmb_alloc(void *ctx,const u64 old[2])
{
    struct n71_storage_dart_context *m=ctx;
    u64 pa,old_sart_pa,old_sart_size;
    u32 v[4];
    unsigned int j;
    for (j=0;j<4;j++) v[j]=readl((u8 __iomem *)m->nvmmu+0x20+4*j);
    if (v[0]>1 || n71_hmb_memory.page) return -EPERM;
    if (v[0] && ((v[1]&0xfffffU) || (v[2]&0xfffffU) ||
        v[1]>v[2] || (v[1]&0xc0000000U)!=0x80000000U ||
        (v[2]&0xc0000000U)!=0x80000000U || v[3]>=0x10000U))
        return -EPROTO;
    n71_hmb_memory.page=(void *)__get_free_pages(GFP_KERNEL|__GFP_NOWARN|__GFP_NORETRY,get_order(SZ_8M));
    if (!n71_hmb_memory.page) return -ENOMEM;
    pa=virt_to_phys(n71_hmb_memory.page);
    if ((pa&(SZ_1M-1)) || pa>((1ULL<<36)-SZ_8M)) return -EPERM;
    /* The allocator has not zeroed this buffer. Reject inherited overlap first. */
    for (j=0;j<2;j++) {
        u64 size=j ? SZ_4K : SZ_16K;
        if (old[j] && pa<old[j]+size && old[j]<pa+SZ_8M) return -EPERM;
    }
    for (j=0;j<16;j++)
        if (m->inherited_dart_pa[j] && pa<m->inherited_dart_pa[j]+SZ_4K &&
            m->inherited_dart_pa[j]<pa+SZ_8M) return -EPERM;
    if (v[0]) {
        old_sart_pa=(u64)v[3]<<20;
        old_sart_size=(u64)v[2]-v[1]+SZ_1M;
        if (old_sart_pa>((1ULL<<36)-old_sart_size) ||
            (pa<old_sart_pa+old_sart_size && old_sart_pa<pa+SZ_8M)) return -EPERM;
    }
    if (v[0]) {
        n71_hmb_memory.inherited_pa=(u64)v[3]<<20;
        n71_hmb_memory.inherited_size=(u64)v[2]-v[1]+SZ_1M;
    }
    memset(n71_hmb_memory.page,0,SZ_8M);
    n71_hmb_memory.dma=dma_map_single(n71_nvmmu_memory.dev,n71_hmb_memory.page,SZ_8M,DMA_BIDIRECTIONAL);
    if (dma_mapping_error(n71_nvmmu_memory.dev,n71_hmb_memory.dma)) return -EIO;
    n71_hmb_memory.mapped=true;
    if (n71_hmb_memory.dma!=pa) return -EPERM;
    pr_info("n71-s3e-p0: HMB_OWNED_ALLOC bytes=%u contiguous=1 aligned_1M=1 pa36=1 direct_dma=1 inherited_overlap_rejected_before_zero=YES addresses_redacted=YES\n",SZ_8M);
    return 0;
}
static void n71_storage_nvmmu_free(void)
{
    unsigned int i;
    for (i=0;i<2;i++) {
        if (n71_nvmmu_memory.mapped[i])
            dma_unmap_single(n71_nvmmu_memory.dev,n71_nvmmu_memory.dma[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        if (n71_nvmmu_memory.page[i]) free_page((unsigned long)n71_nvmmu_memory.page[i]);
    }
    if (n71_nvmmu_memory.dev) put_device(n71_nvmmu_memory.dev);
    memset(&n71_nvmmu_memory,0,sizeof(n71_nvmmu_memory));
}
static unsigned int n71_storage_nvmmu_read(void *ctx,unsigned int off)
{
    struct n71_storage_dart_context *m=ctx;
    return readl((u8 __iomem *)m->nvmmu+off);
}
static void n71_storage_nvmmu_write(void *ctx,unsigned int off,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE((off!=4 && off!=8 && off!=0x0c && off!=0x10 && off!=0x14) ||
                     (off==4 && val!=0x10000U))) return;
    writel(val,(u8 __iomem *)m->nvmmu+off);
}
static int n71_storage_nvmmu_ready(void *ctx)
{
    return n71_storage_dart_perst(ctx) && n71_storage_full_dart_guard(ctx);
}
static void n71_storage_sart_write(void *ctx,unsigned int off,unsigned int val)
{
    struct n71_storage_dart_context *m=ctx;
    if (WARN_ON_ONCE(!n71_storage_nvmmu_ready(ctx) ||
        off<0x20 || off>0x2c || (off&3) || (off==0x20 && val>1))) return;
    writel(val,(u8 __iomem *)m->nvmmu+off);
    readl((u8 __iomem *)m->nvmmu+off);
}
static int n71_storage_nvmmu_guarded_endpoint(void *ctx)
{
    const struct n71_sart_ops ops={
        .ready=n71_storage_nvmmu_ready,.read=n71_storage_nvmmu_read,
        .write=n71_storage_sart_write,.active_hold=n71_storage_endpoint_release_trial,
    };
    struct n71_sart_result r;
    int rc;
    if (!ans_hmb_owned)
        return endpoint_id_trial ? n71_storage_endpoint_release_trial(ctx) : 0;
    if (!n71_hmb_memory.page || !n71_hmb_memory.mapped) return -EPERM;
    rc=n71_sart_hmb_owned_trial(&ops,ctx,n71_hmb_memory.dma,&r);
    pr_info("n71-s3e-p0: HMB_SART_READBACK stage=%u ctrl=%08x va_base=%08x va_end=%08x pa_match=%u addresses_redacted=YES\n",
        r.stage,r.observed[0],r.observed[1],r.observed[2],
        r.observed[3]==(n71_hmb_memory.dma>>20));
    pr_info("n71-s3e-p0: HMB_SART_OWNED rc=%d inherited_enabled=%u installed=%u restored=%u inner_rc=%d perst_low=%u BME_OFF=YES addresses_redacted=YES\n",
        rc,r.inherited_enabled,r.installed,r.restored,r.inner_rc,n71_storage_reset_level(ctx)==0);
    return rc;
}
static int n71_storage_nvmmu_owned_trial(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    const struct n71_nvmmu_ops ops={
        .read=n71_storage_nvmmu_read,.write=n71_storage_nvmmu_write,
        .ready=n71_storage_nvmmu_ready,.tick=n71_storage_dart_tick,
        .active_hold=n71_storage_nvmmu_guarded_endpoint,
    };
    struct n71_nvmmu_result result;
    u64 old[2],old_size[2]={SZ_16K,SZ_4K};
    unsigned int i,j;
    bool zero=true,free_safe;
    int rc=-EPERM;
    if (!m->nvmmu || !n71_storage_nvmmu_ready(ctx) || PAGE_SIZE<SZ_16K ||
        n71_storage_nvmmu_read(ctx,0)!=1 || n71_storage_nvmmu_read(ctx,4)!=0 ||
        n71_nvmmu_memory.dev) return rc;
    old[0]=(u64)n71_storage_nvmmu_read(ctx,8)|((u64)n71_storage_nvmmu_read(ctx,0x0c)<<32);
    old[1]=(u64)n71_storage_nvmmu_read(ctx,0x10)|((u64)n71_storage_nvmmu_read(ctx,0x14)<<32);
    if ((old[0]&127) || (old[1]&4095) || old[0]>((1ULL<<36)-SZ_16K) ||
        old[1]>((1ULL<<36)-SZ_4K)) return rc;
    m->inherited_nvmmu_pa[0]=old[0];m->inherited_nvmmu_pa[1]=old[1];
    n71_nvmmu_memory.dev=get_device(&n71_consumer->dev);
    for (i=0;i<2;i++) {
        phys_addr_t pa;
        n71_nvmmu_memory.page[i]=(void *)__get_free_page(GFP_KERNEL);
        if (!n71_nvmmu_memory.page[i]) {rc=-ENOMEM;goto alloc_fail;}
        pa=virt_to_phys(n71_nvmmu_memory.page[i]);
        if (pa>((1ULL<<36)-PAGE_SIZE)) goto alloc_fail;
        /* Reject inherited NVMMU/DART overlap before zeroing ANY bytes. */
        for (j=0;j<2;j++)
            if (old[j] && pa<old[j]+old_size[j] && old[j]<pa+PAGE_SIZE)
                goto alloc_fail;
        for (j=0;j<16;j++)
            if (m->inherited_dart_pa[j] && pa<m->inherited_dart_pa[j]+SZ_4K &&
                m->inherited_dart_pa[j]<pa+PAGE_SIZE) goto alloc_fail;
        memset(n71_nvmmu_memory.page[i],0,PAGE_SIZE);
        n71_nvmmu_memory.dma[i]=dma_map_single(n71_nvmmu_memory.dev,
            n71_nvmmu_memory.page[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
        if (dma_mapping_error(n71_nvmmu_memory.dev,n71_nvmmu_memory.dma[i])) {
            rc=-EIO;goto alloc_fail;
        }
        n71_nvmmu_memory.mapped[i]=true;
        if (n71_nvmmu_memory.dma[i]!=pa) goto alloc_fail;
        dma_sync_single_for_device(n71_nvmmu_memory.dev,n71_nvmmu_memory.dma[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
    }
    if (ans_hmb_owned) {
        rc=n71_storage_hmb_alloc(ctx,old);
        if (rc) goto alloc_fail;
    }
    dma_wmb();
    rc=n71_nvmmu_owned_tables_trial(&ops,ctx,n71_nvmmu_memory.dma[0],n71_nvmmu_memory.dma[1],&result);
    free_safe=rc!=-3 && result.restored && n71_storage_nvmmu_ready(ctx) &&
        n71_storage_nvmmu_read(ctx,4)==0;
    /* Active admin DMA is not independently quiesced; keep all backing. */
    if (!n71_dma_retire_authorized(&(struct n71_dma_retirement_boundary){
            .admin_epoch_started=ans_identify_once || READ_ONCE(n71_admin_dma_epoch_latched),
            .controller_shutdown_consistent=0,
            .independent_quiescence_proven=0})) {
        free_safe=false;
        pr_err("n71-s3e-p0: DMA_RETIREMENT_BOUNDARY stage=NVMMU release=DENIED\n");
    }
    if (free_safe) {
        for (i=0;i<2;i++) {
            dma_sync_single_for_cpu(n71_nvmmu_memory.dev,n71_nvmmu_memory.dma[i],PAGE_SIZE,DMA_BIDIRECTIONAL);
            if (memchr_inv(n71_nvmmu_memory.page[i],0,PAGE_SIZE)) zero=false;
        }
        if (ans_hmb_owned) {
            dma_sync_single_for_cpu(n71_nvmmu_memory.dev,n71_hmb_memory.dma,SZ_8M,DMA_BIDIRECTIONAL);
            bool hmb_zero=!memchr_inv(n71_hmb_memory.page,0,SZ_8M);
            if (!ans_identify_once && !hmb_zero) zero=false;
            n71_storage_hmb_free();
            pr_info("n71-s3e-p0: HMB_MEMORY_RELEASED bytes=%u free_safe=1 hmb_zero=%u device_use_permitted=%u\n",SZ_8M,hmb_zero,ans_identify_once);
        }
        n71_storage_admin_free();
        n71_storage_nvmmu_free();
    } else {
        rc=-3;
        pr_err("n71-s3e-p0: NVMMU_TABLES_QUARANTINED_KEEP_PAGES_DART_POWER_RESET\n");
    }
    pr_info("n71-s3e-p0: NVMMU_OWNED_TABLES_TRIAL rc=%d owned_polls=%u restore_polls=%u last=%08x restored=%u pages_zero=%u free_safe=%u backing_bytes=%lu addresses_redacted=YES\n",
        rc,result.owned_polls,result.restore_polls,result.last,result.restored,zero,free_safe,2UL*PAGE_SIZE);
    return !zero && !rc ? -EIO : rc;
alloc_fail:
    /* These allocations have not reached the NVMMU/endpoint trial in this
     * invocation. A previous BME/admin epoch is nevertheless monotonic:
     * never unmap any DMA backing after that epoch, even on an error path.
     * A pre-epoch allocation failure is safe to unwind normally. */
    if (READ_ONCE(n71_admin_dma_epoch_latched)) {
        n71_unreleased=true;
        pr_err("n71-s3e-p0: NVMMU_ALLOC_FAIL_AFTER_DMA_EPOCH_KEEP_ALL_BACKING quarantine=YES\n");
        return -3;
    }
    n71_storage_admin_free();
    n71_storage_hmb_free();
    n71_storage_nvmmu_free();
    return rc;
}
static int n71_storage_p0_config_observe(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    void __iomem *cfg=NULL,*local=NULL;
    u32 id,command,class_rev,buses,local80,local88;
    unsigned int j;
    int rc=-EPERM;
    if (!m->all_streams || !n71_storage_dart_perst(ctx) ||
        readl((u8 __iomem *)m->dart+0x0c)!=0x80808080U)
        return rc;
    for (j=0;j<16;j++)
        if (readl((u8 __iomem *)m->dart+0x40+4*j)!=n71_tables.word[j])
            return rc;
    /* Original N71 apcie resource0: ECAM 0x610000000 length16MiB.
     * Device0/function0/bus0 is the storage root bridge. Read only:
     * no bus numbers, command, BARs, local control or PERST writes.
     */
    cfg=ioremap(P0_ROOT_ECAM_PHYS,0x1000);
    local=ioremap(P0_PORT_PHYS,0x1000);
    if (!cfg || !local) {rc=-ENOMEM;goto out;}
    id=readl(cfg);
    command=readl((u8 __iomem *)cfg+4);
    class_rev=readl((u8 __iomem *)cfg+8);
    buses=readl((u8 __iomem *)cfg+0x18);
    local80=readl((u8 __iomem *)local+0x80);
    local88=readl((u8 __iomem *)local+0x88);
    pr_info("n71-s3e-p0: STORAGE_ROOT_CFG_RO id=%08x command_status=%08x class_rev=%08x buses=%08x local80=%08x local88=%08x NAND_RESET_LOW=YES\n",
            id,command,class_rev,buses,local80,local88);
    rc=(id & 0xffffU)==0x106bU && n71_storage_dart_perst(ctx) ? 0 : -ENODEV;
    if (!rc && endpoint_id_trial) {
        m->cfg=cfg;m->local=local;
        rc=nvmmu_owned_tables ? n71_storage_nvmmu_owned_trial(ctx) :
                              n71_storage_endpoint_release_trial(ctx);
        m->cfg=NULL;m->local=NULL;
    }
out:
    if (local) iounmap(local);
    if (cfg) iounmap(cfg);
    return rc;
}
static void n71_storage_dart_hold(void *ctx)
{
    struct n71_storage_dart_context *m=ctx;
    unsigned int command, polls;
    const struct n71_dart_trial_ops inner={
        .read=n71_storage_dart_read,.write=n71_storage_dart_write,
        .perst_low=n71_storage_dart_perst,.hold=n71_storage_dart_delay,
        .tick=n71_storage_dart_tick,
        .active_hold=observe_p0_config ? n71_storage_p0_config_observe : NULL,
    };
    if (m->all_streams)
        m->inner_rc=n71_dart_all_stream_owned_roots_trial(&inner,ctx,
                                     n71_tables.word,&command,&polls);
    else
        m->inner_rc=n71_dart_owned_roots_trial(&inner,ctx,n71_tables.word,
                                             &command,&polls);
    pr_info("n71-s3e-p0: DART0_OWNED_ROOTS streams=%u inner_rc=%d command=%08x polls=%u NAND_PERST_LOW=YES\n",
            m->all_streams ? 4 : 1,m->inner_rc,command,polls);
}
static int n71_storage_dart_owned_trial(struct device *dev,
                 void __iomem *dart, void __iomem *pinctrl, void __iomem *nvmmu)
{
    struct n71_storage_dart_context mm={
        .dart=dart,.pinctrl=pinctrl,.nvmmu=nvmmu,.inner_rc=-EINPROGRESS,
        .all_streams=dart0_all_streams,
    };
    const struct n71_dart_trial_ops outer={
        .read=n71_storage_dart_read,.write=n71_storage_dart_write,
        .perst_low=n71_storage_dart_perst,.hold=n71_storage_dart_hold,
        .command_change_mask=0x00000f00U,
    };
    unsigned int zero_ok=0,restore_ok=0,j;
    bool free_safe,pages_zero=true;
    int rc;
    if (!n71_storage_dart_perst(&mm) || readl((u8 __iomem *)dart+0x0c)!=0)
        return -EPERM;
    for (j=0;j<16;j++)
        mm.inherited_dart_pa[j]=(phys_addr_t)(readl((u8 __iomem *)dart+0x40+4*j)&0x00ffffffU)<<12;
    rc=n71_owned_alloc(dev,&n71_tables,dart,dart0_all_streams ? 16 : 4);
    if (rc) return rc;
    rc=n71_dart_disabled_ttbr_trial(&outer,&mm,&zero_ok,&restore_ok);
    free_safe=restore_ok && n71_storage_dart_perst(&mm) &&
        readl((u8 __iomem *)dart+0x0c)==0 &&
        !(readl((u8 __iomem *)dart)&BIT(3));
    /* DART roots remain pinned after any admin DMA epoch. */
    if (!n71_dma_retire_authorized(&(struct n71_dma_retirement_boundary){
            .admin_epoch_started=ans_identify_once || READ_ONCE(n71_admin_dma_epoch_latched),
            .controller_shutdown_consistent=0,
            .independent_quiescence_proven=0})) {
        free_safe=false;
        pr_err("n71-s3e-p0: DMA_RETIREMENT_BOUNDARY stage=DART release=DENIED\n");
    }
    if (free_safe) {
        for (j=0;j<n71_tables.count;j++) {
            dma_sync_single_for_cpu(n71_tables.dev,n71_tables.dma[j],
                                    PAGE_SIZE,DMA_TO_DEVICE);
            if (memchr_inv(n71_tables.page[j],0,PAGE_SIZE)) pages_zero=false;
        }
        n71_owned_free(&n71_tables);
    } else {
        n71_unreleased=true;
        pr_err("n71-s3e-p0: DART0_ROOTS_QUARANTINED_KEEP_PAGES_POWER_AND_NAND_RESET\n");
    }
    pr_info("n71-s3e-p0: DART0_ROOT_TRANSACTION rc=%d zero_pass=%u restore_pass=%u inner_rc=%d pages_zero=%u free_safe=%u NAND_RESET_LOW=YES\n",
        rc,zero_ok,restore_ok,mm.inner_rc,pages_zero,free_safe);
    return !rc && zero_ok && restore_ok && !mm.inner_rc &&
           pages_zero && free_safe ? 0 : -EIO;
}

static int __init n71_port0_init(void)
{
    struct regmap *map;
    void __iomem *root_mmio=NULL;
    void __iomem *dart0=NULL,*nvmmu0=NULL,*port0=NULL;
    void __iomem *pinctrl=NULL;
    bool mode_dirty=false, attempted=false;
    bool id3_dirty=false, id2_dirty=false, id4_dirty=false;
    u32 id3_saved=0,id2_saved=0,id4_saved=0;
    struct of_phandle_args spec={};
    struct device_node *parent,*pin_node=NULL;
    struct platform_device *pin_dev=NULL;
    u32 inside;
    int ret, rel, check;
    if (!armed) {
        pr_info("n71-s3e-p0: UNARMED inert, no PMGR access\n");
        return 0;
    }
    /* Keep observation and queue-write experiment mutually exclusive
     * and refuse before any PMGR/GPIO/NVMe access. */
    if (ans_late_dma_probe_ro && (!ans_identify_once ||
            ans_queue_retire_probe || ans_phase_trace_ro))
        return -EPERM;
    if (ans_phase_trace_ro && (!ans_identify_once || ans_queue_retire_probe))
        return -EPERM;
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
    if (sample_root || stock_nvme_mode) {
        root_mmio=ioremap(ROOT_COMMON_PHYS,0x1000);
        if (!root_mmio) { ret=-ENOMEM; goto out_put; }
    }
    if (rootstart_p0 && !stock_nvme_mode) {ret=-EPERM;goto out_put;}
    if (ans_identify_once && !ans_hmb_owned) {ret=-EPERM;goto out_put;}
    if (ans_hmb_owned && !ans_hmb_ro) {ret=-EPERM;goto out_put;}
    if (ans_hmb_ro && (!nvme_mmio_trial || !nvmmu_owned_tables)) {ret=-EPERM;goto out_put;}
    if (nvmmu_owned_tables && !endpoint_id_trial) {ret=-EPERM;goto out_put;}
    if (nvme_mmio_trial && !bar0_size_trial) {ret=-EPERM;goto out_put;}
    if (bar0_size_trial && !endpoint_id_trial) {ret=-EPERM;goto out_put;}
    if (endpoint_id_trial && !observe_p0_config) {ret=-EPERM;goto out_put;}
    if (observe_p0_config && !dart0_all_streams) {ret=-EPERM;goto out_put;}
    if (dart0_all_streams && !dart0_owned_roots) {ret=-EPERM;goto out_put;}
    if (dart0_owned_roots && !stock_late_controls) {ret=-EPERM;goto out_put;}
    if (stock_late_controls && (!assert_storage_reset || !rootstart_p0 ||
            !stock_nvme_mode || !sample_root || !sample_iommu)) {
        ret=-EPERM; goto out_put;
    }
    if (assert_storage_reset) {
        u32 pin_raw=0,pin_cached=0,wifi_raw=0,p0_root=0,p1_root=0;
        if (!stock_nvme_mode || !rootstart_p0 || !sample_iommu ||
            !sample_root || !root_mmio) {
            ret=-EPERM; goto out_put;
        }
        pin_node=of_find_node_by_path(S8000_PINCTRL_PROVIDER);
        if (!pin_node ||
            !of_device_is_compatible(pin_node,"apple,s8000-pinctrl")) {
            ret=-ENODEV; goto out_put;
        }
        pin_dev=of_find_device_by_node(pin_node);
        if (!pin_dev) {ret=-ENODEV;goto out_put;}
        n71_pinctrl_regmap=dev_get_regmap(&pin_dev->dev,NULL);
        if (!n71_pinctrl_regmap) {ret=-ENODEV;goto out_put;}
        pinctrl=ioremap(S8000_PINCTRL_PHYS,0x1000);
        if (!pinctrl) {ret=-ENOMEM;goto out_put;}
        pin_raw=readl((u8 __iomem *)pinctrl + S8000_GPIO160_OFFSET);
        wifi_raw=readl((u8 __iomem *)pinctrl + 4*161);
        p0_root=readl((u8 __iomem *)root_mmio + 0x12c);
        p1_root=readl((u8 __iomem *)root_mmio + 0x1ac);
        ret=regmap_read(n71_pinctrl_regmap,S8000_GPIO160_OFFSET,&pin_cached);
        if (ret || pin_raw!=S8000_GPIO160_ORIGINAL ||
            pin_cached!=pin_raw || wifi_raw!=S8000_GPIO161_WIFI ||
            p0_root!=0 || p1_root!=1) {
            pr_err("n71-s3e-p0: S3E_RESET_PIN160_PREFLIGHT_REJECTED raw=%08x cached=%08x wifi=%08x\n",
                pin_raw,pin_cached,wifi_raw);
            ret=-EPERM;goto out_put;
        }
        gpiod_add_lookup_table(&n71_reset_gpio_lookup);
        n71_reset_lookup_added=true;
        n71_reset_pdev=platform_device_register_simple(
            "n71-s3e-p0-reset",PLATFORM_DEVID_NONE,NULL,0);
        if (IS_ERR(n71_reset_pdev)) {
            ret=PTR_ERR(n71_reset_pdev);
            n71_reset_pdev=NULL;goto out_put;
        }
        n71_reset_pin=gpiod_get(&n71_reset_pdev->dev,"s3e-reset",GPIOD_ASIS);
        if (IS_ERR(n71_reset_pin)) {
            ret=PTR_ERR(n71_reset_pin);
            n71_reset_pin=NULL;goto out_put;
        }
        n71_reset_claimed=true;
        if (gpiod_get_direction(n71_reset_pin)!=1 ||
            readl((u8 __iomem *)pinctrl+S8000_GPIO160_OFFSET)!=
            S8000_GPIO160_ORIGINAL) {
            ret=-EPERM;goto out_put;
        }
        /* Keep NAND endpoint reset ASSERTED: output LOW. NEVER output HIGH. */
        ret=gpiod_direction_output(n71_reset_pin,0);
        if (ret) goto out_put;
        pin_raw=readl((u8 __iomem *)pinctrl+S8000_GPIO160_OFFSET);
        if (pin_raw!=S8000_GPIO160_ASSERTED_LOW ||
            gpiod_get_direction(n71_reset_pin)!=0 ||
            gpiod_get_value_cansleep(n71_reset_pin)!=0) {
            ret=-EIO; goto out_put;
        }
        pr_info("n71-s3e-p0: NAND_GPIO160_PHYSICALLY_ASSERTED_LOW register=%08x keep_ASSERTED_during_power=yes\n", pin_raw);
    }
    if (stock_nvme_mode) {
        u32 mode0,mode1,shared_status,port0_status,port1_status,perst160;
        if (!sample_iommu || !sample_root || !root_mmio) {
            ret=-EINVAL;goto out_put;
        }
        if (!pinctrl)
            pinctrl=ioremap(S8000_PINCTRL_PHYS,0x1000);
        if (!pinctrl) {ret=-ENOMEM;goto out_put;}
        perst160=readl((u8 __iomem *)pinctrl + 4*160);
        if (!assert_storage_reset) {
            iounmap(pinctrl);pinctrl=NULL;
        }
        mode0=readl((u8 __iomem *)root_mmio + 0x14);
        mode1=readl((u8 __iomem *)root_mmio + 0x24);
        shared_status=readl((u8 __iomem *)root_mmio + 0x2c);
        port0_status=readl((u8 __iomem *)root_mmio + 0x12c);
        port1_status=readl((u8 __iomem *)root_mmio + 0x1ac);
        if (perst160!=(assert_storage_reset ?
                S8000_GPIO160_ASSERTED_LOW : S8000_GPIO160_ORIGINAL) ||
            mode0!=0x00000101 ||
            mode1!=0 || shared_status!=0x00000011 ||
            port0_status!=0 || port1_status!=1) {
            pr_err("n71-s3e-p0: STOCK_NVME_MODE_PREFLIGHT_REFUSED; original reset/ports do not match\n");
            ret=-EPERM;goto out_put;
        }
        /*
         * Genuine S8000 Apple root vslot1944, implementation +0x690:
         * root+0x14=0x101, delay 100us, vslot1960 bit-inverse -> root+0x24=1
         * for port0. Only perform the missing mode1 write, while PERST160
         * is observed GPIO input LOW. No endpoint reset, no DMA possible.
         */
        udelay(100);
        mode_dirty=true;
        attempted=true;
        writel(1,(u8 __iomem *)root_mmio + 0x24);
        if (readl((u8 __iomem *)root_mmio + 0x24)!=1) {
            pr_err("n71-s3e-p0: ROOT_MODE1_WRITE_NOT_ACKNOWLEDGED\n");
            ret=-EIO;goto cleanup;
        }
        pr_info("n71-s3e-p0: STOCK_ORIGINAL_NVME_MODE_ENABLED temporary root+0x24=1 PERST160_LOW=1 no_NAND_no_DMA\n");
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
        if (rootstart_p0) {
            u32 id5_saved;
            id3_saved=readl((u8 __iomem *)root_mmio + 0x114);
            id2_saved=readl((u8 __iomem *)root_mmio + 0x100);
            id4_saved=readl((u8 __iomem *)root_mmio + 0x124);
            id5_saved=readl((u8 __iomem *)root_mmio + 0x12c);
            pr_info("n71-s3e-p0: PHYSICAL_P0_ROOT_BASELINE id2=%08x id3=%08x id4=%08x id5=%08x before_any_port_control_write\n",
                    id2_saved,id3_saved,id4_saved,id5_saved);
            if ((id3_saved | id2_saved | id4_saved | id5_saved) & BIT(0)) {
                pr_err("n71-s3e-p0: port0 root active bit unexpectedly set; refusing writes\n");
                ret=-EPERM;
            } else if (id2_saved==0xffffffffU || id3_saved==0xffffffffU ||
                       id4_saved==0xffffffffU || id5_saved==0xffffffffU) {
                pr_err("n71-s3e-p0: root control reads invalid; refusing writes\n");
                ret=-EIO;
            } else {
                /* Actual S8000 root vslot1984 ID3 and vslot1976 ID2:
                 * masked bit0 RMW, preserve all preexisting status bits.
                 * PERST160 stays LOW. Do not issue PCIe/DART/NVMe DMA.
                 */
                id3_dirty=true;
                writel(id3_saved | BIT(0),(u8 __iomem *)root_mmio + 0x114);
                if (readl((u8 __iomem *)root_mmio + 0x114)!=(id3_saved | BIT(0))) {
                    pr_err("n71-s3e-p0: port0 ID3 RMW did not acknowledge\n");
                    ret=-EIO;
                } else {
                    udelay(100);
                    id2_dirty=true;
                    writel(id2_saved | BIT(0),(u8 __iomem *)root_mmio + 0x100);
                    if (readl((u8 __iomem *)root_mmio + 0x100)!=(id2_saved | BIT(0))) {
                        pr_err("n71-s3e-p0: port0 ID2 RMW did not acknowledge\n");
                        ret=-EIO;
                    } else {
                        pr_info("n71-s3e-p0: STOCK_S8000_P0_ID3_ID2_BIT0_RMW_ACK PERST160_LOW=1 id5=%08x\n",
                           readl((u8 __iomem *)root_mmio + 0x12c));
                    }
                }
            }
        }
        if (!ret && stock_late_controls) {
            u32 active_id2, active_id4, pin_now;
            /* Original S800x ROOT vslot1992 clears selector-ID2 bit8;
             * ROOT vslot1968 with flag0 sets selector-ID4 bit0.
             * Those exact operations were already microleased on port1.
             * This research trial evaluates port0 under asserted NAND
             * reset even if opaque ID5 readiness is not yet observed;
             * it is not a claim to replay Apple's full startup method.
             * Do not issue telemetry 3/7, local0x210 acknowledgments,
             * DART/NVMMU initialization, PCI config or endpoint DMA.
             */
            pin_now=readl((u8 __iomem *)pinctrl + S8000_GPIO160_OFFSET);
            if (!n71_reset_claimed || pin_now!=S8000_GPIO160_ASSERTED_LOW ||
                gpiod_get_direction(n71_reset_pin)!=0 ||
                gpiod_get_value_cansleep(n71_reset_pin)!=0) {
                ret=-EPERM;
            } else {
                active_id2=(id2_saved | BIT(0)) & ~BIT(8);
                writel(active_id2,(u8 __iomem *)root_mmio + 0x100);
                if (readl((u8 __iomem *)root_mmio + 0x100)!=active_id2) {
                    ret=-EIO;
                } else {
                    pr_info("n71-s3e-p0: LATE_ID2_BIT8_CLEAR_ACK id2=%08x id5=%08x NAND_RESET_LOW=YES\n",
                        active_id2,readl((u8 __iomem *)root_mmio + 0x12c));
                    udelay(100);
                    active_id4=id4_saved | BIT(0);
                    id4_dirty=true;
                    writel(active_id4,(u8 __iomem *)root_mmio + 0x124);
                    if (readl((u8 __iomem *)root_mmio + 0x124)!=active_id4) {
                        ret=-EIO;
                    } else {
                        udelay(100);
                        pr_info("n71-s3e-p0: LATE_ID4_BIT0_SET_ACK id4=%08x id5=%08x NAND_RESET_LOW=YES\n",
                            active_id4,readl((u8 __iomem *)root_mmio + 0x12c));
                    }
                }
            }
        }
        msleep(DWELL_MS);
        if (sample_iommu) {
            u32 dart_id, dart_tcr, dart_fault, dart_ttbr0;
            u32 nvmmu_ctrl, nvmmu_init, p0_fifo;
            dart0=ioremap(DART0_PHYS,0x1000);
            nvmmu0=ioremap(NVMMU0_PHYS,0x1000);
            port0=ioremap(P0_PORT_PHYS,0x1000);
            if (!dart0 || !nvmmu0 || !port0) {
                pr_err("n71-s3e-p0: DART0/NVMMU0 map rejected (no register writes)\n");
                ret=-ENOMEM;
            } else {
                dart_id=readl((u8 __iomem *)dart0 + 0x00);
                dart_tcr=readl((u8 __iomem *)dart0 + 0x0c);
                dart_fault=readl((u8 __iomem *)dart0 + 0x10);
                dart_ttbr0=readl((u8 __iomem *)dart0 + 0x40);
                nvmmu_ctrl=readl((u8 __iomem *)nvmmu0 + 0x00);
                nvmmu_init=readl((u8 __iomem *)nvmmu0 + 0x04);
                p0_fifo=readl((u8 __iomem *)port0 + 0x22c);
                pr_info("n71-s3e-p0: REAL_DART0_READ_ONLY cmd=%08x packed_tcr=%08x fault=%08x ttbr0=%08x physical=0x601008000\n",
                    dart_id,dart_tcr,dart_fault,dart_ttbr0);
                pr_info("n71-s3e-p0: REAL_NVMMU0_READ_ONLY ctrl=%08x init=%08x p0_fifo=%08x physical=0x601004000 and 0x601000000 no_DART_NVMMU_writes\n",
                    nvmmu_ctrl,nvmmu_init,p0_fifo);
                if (dart_id==0xffffffffU || dart_tcr==0xffffffffU ||
                    nvmmu_ctrl==0xffffffffU || p0_fifo==0xffffffffU)
                    ret=-EIO;
            }
            if (!ret && dart0_owned_roots) {
                ret=n71_storage_dart_owned_trial(&n71_consumer->dev,dart0,pinctrl,nvmmu0);
            }
            if (port0) { iounmap(port0); port0=NULL; }
            if (nvmmu0) { iounmap(nvmmu0); nvmmu0=NULL; }
            if (dart0) { iounmap(dart0); dart0=NULL; }
        }
        if (root_mmio) {
            u32 p0_link=readl((u8 __iomem *)root_mmio+0x12c);
            u32 p1_link=readl((u8 __iomem *)root_mmio+0x1ac);
            u32 shared=readl((u8 __iomem *)root_mmio+0x2c);
            pr_info("n71-s3e-p0: PHYSICAL_ROOT_DURING_P0_POWER p0_id5=%08x p0_bit0=%u p1_id5=%08x p1_bit0=%u shared=%08x no_pcie_reset_no_dma\n",
                p0_link,p0_link&1U,p1_link,p1_link&1U,shared);
        }
        if (n71_unreleased) goto cleanup;
        if (rootstart_p0) {
            if (id4_dirty) {
                writel(id4_saved,(u8 __iomem *)root_mmio + 0x124);
                if (readl((u8 __iomem *)root_mmio + 0x124)!=id4_saved)
                    ret=-EUCLEAN;
                else id4_dirty=false;
                pr_info("n71-s3e-p0: LATE_ID4_RESTORE_CHECK restored=%u\n", !id4_dirty);
            }
            if (id2_dirty) {
                writel(id2_saved,(u8 __iomem *)root_mmio + 0x100);
                if (readl((u8 __iomem *)root_mmio + 0x100)!=id2_saved)
                    ret=-EUCLEAN;
                else id2_dirty=false;
            }
            if (id3_dirty) {
                writel(id3_saved,(u8 __iomem *)root_mmio + 0x114);
                if (readl((u8 __iomem *)root_mmio + 0x114)!=id3_saved)
                    ret=-EUCLEAN;
                else id3_dirty=false;
            }
            if (id2_dirty || id3_dirty || id4_dirty) {
                n71_unreleased=true;
                pr_err("n71-s3e-p0: ROOT_PORT_CONTROL_ROLLBACK_FAILED, quarantine\n");
            } else {
                pr_info("n71-s3e-p0: ROOT_PORT0_ID2_ID3_RESTORED_TO_ORIGINAL_BASELINE_before_PMGR_release\n");
            }
        }
    }
    if (n71_unreleased) goto cleanup;
    rel=pm_runtime_put_sync_suspend(&n71_consumer->dev);
    if (rel<0) {
        n71_unreleased=true;
        pr_err("n71-s3e-p0: POWER_RELEASE_ERROR rc=%d, consumer must remain pinned\n",rel);
        ret=rel;
        goto cleanup;
    }
    check=n71_snapshot(map,false);
    if (check) {
        ret=check;
        pr_err("n71-s3e-p0: POSTFAIL rc=%d, verify p0 physically off before NVMe mode rollback\n",ret);
        if (regmap_read(map,PORT0_OFF,&inside) ||
            ACTUAL(inside)!=0 || TARGET(inside)!=0)
            n71_unreleased=true;
        goto cleanup;
    }
    if (!ret)
        pr_info("n71-s3e-p0: PHYSICAL_POWER_ON_OFF_PASS p0_actual=0 wifi_p1_preserved=yes p2_p3_preserved=yes\n");

cleanup:
    if (mode_dirty && !n71_unreleased) {
        u32 mode_val=0,domain_state=0;
        if (regmap_read(map,PORT0_OFF,&domain_state) ||
            ACTUAL(domain_state)!=0 || TARGET(domain_state)!=0) {
            n71_unreleased=true;
            pr_err("n71-s3e-p0: ROOT_NVME_MODE_RESTORE_REFUSED_WHILE_POWER_ACTIVE\n");
        } else {
            writel(0,(u8 __iomem *)root_mmio + 0x24);
            mode_val=readl((u8 __iomem *)root_mmio + 0x24);
            if (mode_val!=0) {
                n71_unreleased=true;
                pr_err("n71-s3e-p0: ROOT_NVME_MODE_RESTORE_READBACK_FAILED val=%08x\n",mode_val);
            } else {
                pr_info("n71-s3e-p0: ORIGINAL_NVME_MODE_ROOT24_RESTORED_TO_ZERO, p0_PMGR=OFF\n");
                mode_dirty=false;
            }
        }
    }
    if (n71_unreleased) {
        /* A safety failure retains the device association (no unsafe unload). */
        __module_get(THIS_MODULE);
        n71_pin_ref_held=true;
        pr_err("n71-s3e-p0: QUARANTINED module pinned; inspect power state before next boot\n");
    } else {
        n71_safe_detach();
    }
out_put:
    if (assert_storage_reset && n71_reset_claimed) {
        u32 after=0,cached=0,pmgr=0,wifi=0;
        int pin_ret, reg_ret;
        /* NEVER let the GPIO go to input while PCIe port0 is powered.
         * The original iOS pin mode is recovered only with genpd OFF.
         */
        pin_ret=regmap_read(map,PORT0_OFF,&pmgr);
        if (n71_unreleased || pin_ret ||
            ACTUAL(pmgr)!=0 || TARGET(pmgr)!=0) {
            n71_unreleased=true;
            pr_err("n71-s3e-p0: GPIO160_RESET_RETAINED_LOW_AS_P0_NOT_OFF\n");
        } else {
            pin_ret=gpiod_direction_input(n71_reset_pin);
            if (!pin_ret)
                pin_ret=regmap_update_bits(n71_pinctrl_regmap,
                        S8000_GPIO160_OFFSET,S8000_GPIO_MUTABLE_MASK,
                        S8000_GPIO160_ORIGINAL & S8000_GPIO_MUTABLE_MASK);
            if (pinctrl) {
                after=readl((u8 __iomem *)pinctrl+S8000_GPIO160_OFFSET);
                wifi=readl((u8 __iomem *)pinctrl+4*161);
            }
            reg_ret=regmap_read(n71_pinctrl_regmap,
                       S8000_GPIO160_OFFSET,&cached);
            if (pin_ret || reg_ret || after!=S8000_GPIO160_ORIGINAL ||
                cached!=S8000_GPIO160_ORIGINAL ||
                wifi!=S8000_GPIO161_WIFI ||
                gpiod_get_direction(n71_reset_pin)!=1) {
                n71_unreleased=true;
                pr_err("n71-s3e-p0: GPIO160_EXACT_RESTORE_FAILED raw=%08x cached=%08x wifi=%08x\n",
                    after,cached,wifi);
            } else {
                pr_info("n71-s3e-p0: GPIO160_ORIGINAL_INPUT_RESTORED_VERIFIED reg=%08x p0_OFF=YES\n",
                    after);
            }
        }
    }
    if (assert_storage_reset && n71_unreleased && !n71_pin_ref_held) {
        __module_get(THIS_MODULE);
        n71_pin_ref_held=true;
        pr_err("n71-s3e-p0: QUARANTINE_GPIO160_PIN_HOLD_AND_MODULE_REF; DO_NOT_UNLOAD\n");
    }
    if (!n71_unreleased) {
        if (n71_reset_pin) {
            gpiod_put(n71_reset_pin); n71_reset_pin=NULL;
        }
        if (n71_reset_pdev) {
            platform_device_unregister(n71_reset_pdev);n71_reset_pdev=NULL;
        }
        if (n71_reset_lookup_added) {
            gpiod_remove_lookup_table(&n71_reset_gpio_lookup);
            n71_reset_lookup_added=false;
        }
    }
    if (pin_dev) put_device(&pin_dev->dev);
    if (pin_node) of_node_put(pin_node);
    if (pinctrl) iounmap(pinctrl);
    if (port0) iounmap(port0);
    if (nvmmu0) iounmap(nvmmu0);
    if (dart0) iounmap(dart0);
    if (root_mmio) iounmap(root_mmio);
    of_node_put(n71_p0);n71_p0=NULL;
    /* Keep module resident if pin/quarantine must survive error. */
    if (n71_unreleased)
        return 0;
    /*
     * BusyBox may retry a negative init_module through finit_module,
     * invoking the physical one-shot twice. Once ALL temporary hardware
     * state was demonstrably restored, report a diagnostic error in dmesg
     * but keep the inert module resident for a supervised rmmod.
     */
    if (attempted && ret && !mode_dirty && !id3_dirty &&
        !id2_dirty && !id4_dirty && !n71_consumer) {
        pr_err("n71-s3e-p0: DIAGNOSTIC_REJECTED_AFTER_SAFE_ROLLBACK rc=%d; do not retry\n",ret);
        return 0;
    }
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
MODULE_DESCRIPTION("Bounded S8000 port0 controls, Linux-owned DART0 roots and optional S3E config identification");
