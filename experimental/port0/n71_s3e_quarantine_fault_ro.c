// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/mfd/syscon.h>
#include <linux/regmap.h>
static bool armed;
module_param(armed,bool,0400);
static int __init ro_init(void)
{
    struct device_node *node;
    struct regmap *map;
    void __iomem *pin,*dart,*nvmmu;
    u32 p0,p1,root,pin160,err,addr;
    if (!armed) return 0;
    if (!of_machine_is_compatible("apple,n71") ||
        !of_machine_is_compatible("apple,s8000")) return -EPERM;
    node=of_find_node_by_path("/soc/power-management@20e000000");
    map=syscon_node_to_regmap(node);of_node_put(node);
    if (IS_ERR(map)) return PTR_ERR(map);
    if (regmap_read(map,0x80320,&p0) || regmap_read(map,0x80328,&p1) ||
        regmap_read(map,0x80310,&root)) return -EIO;
    if ((p0&255)!=255 || (p1&255)!=255 || (root&255)!=255) return -EPERM;
    pin=ioremap(0x20f100000ULL,4096);
    if (!pin) return -ENOMEM;
    pin160=readl((u8 __iomem *)pin+160*4);iounmap(pin);
    if (pin160!=0x72202) return -EPERM;
    dart=ioremap(0x601008000ULL,4096);
    nvmmu=ioremap(0x601004000ULL,4096);
    if (!dart || !nvmmu) {if(dart)iounmap(dart);if(nvmmu)iounmap(nvmmu);return -ENOMEM;}
    err=readl((u8 __iomem *)dart+0x10);
    addr=readl((u8 __iomem *)dart+0x1c);
    pr_info("n71-s3e-fault-ro: SNAPSHOT error=%08x stream=%u code=%02x iova=%08x cmd=%08x packed_tcr=%08x NVMMU_ctrl=%08x NVMMU_invalidate=%08x SART_ctrl=%08x PERST_LOW=YES power_held=YES no_writes=YES\n",
        err,(err>>24)&3,err&255,addr,readl(dart),readl((u8 __iomem *)dart+0x0c),
        readl(nvmmu),readl((u8 __iomem *)nvmmu+4),readl((u8 __iomem *)nvmmu+0x20));
    iounmap(nvmmu);iounmap(dart);
    return 0;
}
static void __exit ro_exit(void) {}
module_init(ro_init);
module_exit(ro_exit);
MODULE_LICENSE("GPL");

MODULE_DESCRIPTION("Read-only S8000 DART0 fault snapshot while owner guard holds port0 on and NAND PERST low");
