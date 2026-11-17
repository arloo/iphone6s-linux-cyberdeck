// SPDX-License-Identifier: GPL-2.0
/*
 * N71 S8000 storage port0: owner-supervised, one-shot 25ms PMGR power lease.
 *
 * When fully armed: assert S3E NAND GPIO160 reset as OUTPUT LOW,
 * temporarily enable the stock S8000 NVMe mode and port0-only PCIe
 * root bits, request genpd "pcie_link0" ON for 25 ms, then synchronously
 * restore every root register and PMGR domain BEFORE returning GPIO160
 * to its exact original INPUT LOW configuration. Never deassert PERST.
 * No DART/NVMMU writes, NVMe commands, filesystem/NAND, iOS partition,
 * or DMA writes. No PCI endpoint rescan or PCIe configuration access.
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
#define P0_PORT_BANK1_PHYS 0x601004000ULL
#define P1_PORT_PHYS 0x602000000ULL
#define P1_PORT_BANK1_PHYS 0x602004000ULL
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
static bool sample_local_banks;
module_param(sample_local_banks, bool, 0400);
MODULE_PARM_DESC(sample_local_banks, "read only 8 original Apple per-port tuning offsets across both physical banks for storage0 and WLAN1");
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

static int __init n71_port0_init(void)
{
    struct regmap *map;
    void __iomem *root_mmio=NULL;
    void __iomem *dart0=NULL,*nvmmu0=NULL,*port0=NULL;
    void __iomem *pinctrl=NULL;
    bool mode_dirty=false, attempted=false;
    bool id3_dirty=false, id2_dirty=false;
    u32 id3_saved=0,id2_saved=0;
    struct of_phandle_args spec={};
    struct device_node *parent,*pin_node=NULL;
    struct platform_device *pin_dev=NULL;
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
    if (sample_root || stock_nvme_mode) {
        root_mmio=ioremap(ROOT_COMMON_PHYS,0x1000);
        if (!root_mmio) { ret=-ENOMEM; goto out_put; }
    }
    if (sample_local_banks && (!assert_storage_reset || !stock_nvme_mode ||
                                !rootstart_p0 || !sample_iommu || !sample_root)) {
        ret=-EPERM;goto out_put;
    }
    if (rootstart_p0 && !stock_nvme_mode) {ret=-EPERM;goto out_put;}
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
        p0_root=readl((u8 __iomem *)root_mmio + 0x16c);
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
        port0_status=readl((u8 __iomem *)root_mmio + 0x16c);
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
            u32 id4_saved, id5_saved;
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
            if (port0) { iounmap(port0); port0=NULL; }
            if (nvmmu0) { iounmap(nvmmu0); nvmmu0=NULL; }
            if (dart0) { iounmap(dart0); dart0=NULL; }
        }
        if (sample_local_banks) {
            /* Four genuine PCIe port-resource physical windows from the
             * original N71 Apple apcie reg[] array. All offsets occur in
             * original per-port 24-byte RMW tunable records; read-only.
             * Port0 remains under actively asserted PERST160 OUTPUT LOW.
             */
            const u32 off[]={
                0x90U,0x130U,0x134U,0x138U,0x13cU,0x140U,0x98U,0x154U
            };
            void __iomem *bank[4]={};
            const phys_addr_t phys[4]={
                P0_PORT_PHYS,P0_PORT_BANK1_PHYS,
                P1_PORT_PHYS,P1_PORT_BANK1_PHYS
            };
            unsigned int valid[4]={};
            u32 val;
            unsigned int k,j;
            bool mapped=true;
            for (k=0;k<ARRAY_SIZE(bank);++k) {
                bank[k]=ioremap(phys[k],0x1000);
                if (!bank[k]) mapped=false;
            }
            if (!mapped) {
                pr_err("n71-s3e-p0: LOCAL_BANK_READONLY_MAPPING_REJECTED\n");
                ret=-ENOMEM;
            } else {
                for (j=0;j<ARRAY_SIZE(off);++j) {
                    u32 samples[4];
                    for (k=0;k<ARRAY_SIZE(bank);++k) {
                        val=readl((u8 __iomem *)bank[k]+off[j]);
                        samples[k]=val;
                        if (val!=0xffffffffU) ++valid[k];
                    }
                    pr_info("n71-s3e-p0: LOCAL_BANK_COMPARE_RO offset=%04x p0bank0=%08x p0bank1=%08x p1bank0=%08x p1bank1=%08x\n",
                            off[j],samples[0],samples[1],
                            samples[2],samples[3]);
                }
                pr_info("n71-s3e-p0: LOCAL_BANK_COMPARE_TOTAL valid_p0bank0=%u valid_p0bank1=%u valid_p1bank0=%u valid_p1bank1=%u per_bank=%zu reset160_asserted=YES\n",
                        valid[0],valid[1],valid[2],valid[3],
                        ARRAY_SIZE(off));
            }
            for (k=0;k<ARRAY_SIZE(bank);++k)
                if (bank[k]) iounmap(bank[k]);
        }
        if (root_mmio) {
            u32 p0_link=readl((u8 __iomem *)root_mmio+0x16c);
            u32 p1_link=readl((u8 __iomem *)root_mmio+0x1ac);
            u32 shared=readl((u8 __iomem *)root_mmio+0x2c);
            pr_info("n71-s3e-p0: PHYSICAL_ROOT_DURING_P0_POWER p0_id5=%08x p0_bit0=%u p1_id5=%08x p1_bit0=%u shared=%08x no_pcie_reset_no_dma\n",
                p0_link,p0_link&1U,p1_link,p1_link&1U,shared);
        }
        if (rootstart_p0) {
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
            if (id2_dirty || id3_dirty) {
                n71_unreleased=true;
                pr_err("n71-s3e-p0: ROOT_PORT_CONTROL_ROLLBACK_FAILED, quarantine\n");
            } else {
                pr_info("n71-s3e-p0: ROOT_PORT0_ID2_ID3_RESTORED_TO_ORIGINAL_BASELINE_before_PMGR_release\n");
            }
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
        !id2_dirty && !n71_consumer) {
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
MODULE_DESCRIPTION("S8000 NAND reset asserted with bounded port0 power and four original per-port MMIO windows read only");
