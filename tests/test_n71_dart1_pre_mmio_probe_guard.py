"""Compile and execute the exact public N71/S8000 DART1 pre-MMIO guard C.

The C harness uses fake device/resource objects and fully mocked OF
functions. It never communicates with the Apple device, reads MMIO or
enables any hardware. The two public patches compose in order.
"""
from __future__ import annotations
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH12=ROOT/"experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch"
PATCH13=ROOT/"experimental/patches/0013-n71-s8000-dart1-pre-mmio-wlan-probe-guard.patch"
GUARD_NAME="apple_n71_s8000_wlan_dart1_blocked"

def actual_guard_function()->str:
    patch=PATCH13.read_text()
    assert patch.startswith("--- a/drivers/iommu/apple-dart.c\n")
    added="\n".join(line[1:] for line in patch.splitlines()
                    if line.startswith("+") and not line.startswith("+++"))
    first=added.index("static bool "+GUARD_NAME+"(")
    end=added.index("\n}\n",first)+3
    source=added[first:end]
    if not source.endswith("}\n"):source+="\n"
    return source

MOCK_HEADER=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct resource { uint64_t start, end; };
struct platform_device { struct resource res; bool present; };
#define IORESOURCE_MEM 0
static bool n71, s8000;
static unsigned resource_query_count;
static bool of_machine_is_compatible(const char *name) {
    if (strcmp(name,"apple,n71")==0) return n71;
    if (strcmp(name,"apple,s8000")==0) return s8000;
    return false;
}
static struct resource *platform_get_resource(struct platform_device *pdev,
                                              unsigned type, unsigned idx) {
    resource_query_count++;
    if (type!=IORESOURCE_MEM || idx!=0 || !pdev->present) return NULL;
    return &pdev->res;
}
'''
MOCK_MAIN=r'''
static unsigned checked;
static void verify(unsigned a, unsigned b, unsigned present,
                   uint64_t start, uint64_t end, bool expected) {
    struct platform_device device={{start,end},present!=0};
    n71=a!=0;
    s8000=b!=0;
    resource_query_count=0;
    bool got=apple_n71_s8000_wlan_dart1_blocked(&device);
    unsigned expected_queries = n71 && s8000 ? 1U:0U;
    if (got!=expected || resource_query_count!=expected_queries) {
        fprintf(stderr,"DART_GUARD_MODEL_REJECTED case=%u\n",checked);
        exit(2);
    }
    checked++;
}
int main(void) {
    const uint64_t a=UINT64_C(0x602008000);
    const uint64_t b=UINT64_C(0x60200bfff);
    verify(1,1,1,a,b, true);
    verify(1,1,1,a,a,true);
    verify(1,1,1,b,b,true);
    verify(1,1,1,a-1,a-1,false);
    verify(1,1,1,b+1,b+1,false);
    verify(1,1,1,a-1,a,true);
    verify(1,1,1,b,b+1,true);
    verify(1,1,1,a-0x100000,b+0x100000,true);
    verify(1,1,1,UINT64_C(0x601000000),
                    UINT64_C(0x60100bfff),false); // port 0 storage
    verify(1,1,1,UINT64_C(0x603000000),
                    UINT64_C(0x60300bfff),false); // port 2 modem
    verify(1,1,1,UINT64_C(0x600000000),
                    UINT64_C(0x600007fff),false); // shared root
    verify(1,1,1,UINT64_C(0x604000000),
                    UINT64_C(0x604007fff),false); // other port
    verify(1,1,0,a,b,false); // absent resource is not a mapping
    verify(1,1,1,b,a,true); // malformed resource fails closed
    verify(1,1,1,UINT64_MAX,0,true); // malformed extreme
    verify(0,1,1,a,b,false); // other N71 lineage board
    verify(1,0,1,a,b,false); // other A9 SoC (S8003)
    verify(0,0,1,a,b,false);
    uint64_t seed=UINT64_C(0x7c0f29a681d5e4b3);
    for (unsigned i=0; i<50000; i++) {
        seed ^= seed<<13; seed ^= seed>>7; seed ^= seed<<17;
        uint64_t start=a-0x10000U+(seed&0x1ffffU);
        seed ^= seed<<13; seed ^= seed>>7; seed ^= seed<<17;
        uint64_t length=seed & 0xffffU;
        uint64_t end = start+length;
        bool expected = start<=b && end>=a;
        verify(1,1,1,start,end,expected);
    }
    printf("N71_DART1_ACTUAL_C_PRE_MMIO_GUARD_PASS SYNTHETIC_VECTORS=%u\n",checked);
    return 0;
}
'''

class TestN71Dart1PreMMIO(unittest.TestCase):
    def test_actual_patch_has_correct_paths(self):
        self.assertIn("+++ b/drivers/iommu/apple-dart.c",PATCH13.read_text())

    def test_patch_is_a_separate_followup_after_lane12(self):
        self.assertIn("apple_dart_s5l8960x_write_tcr",PATCH12.read_text())
        self.assertNotIn(GUARD_NAME,PATCH12.read_text())
        self.assertIn(GUARD_NAME,PATCH13.read_text())

    def test_original_n71_and_s8000_both_required(self):
        s=actual_guard_function()
        self.assertIn('of_machine_is_compatible("apple,n71")',s)
        self.assertIn('of_machine_is_compatible("apple,s8000")',s)

    def test_exact_dart1_aperture_protected(self):
        s=actual_guard_function()
        self.assertIn("0x602008000ULL",s)
        self.assertIn("0x60200bfffULL",s)
        self.assertLess(s.index("0x60200bfffULL"),s.index("0x602008000ULL"))

    def test_guard_rejects_malformed_resource(self):
        self.assertIn("res->end < res->start",actual_guard_function())

    def test_guard_rejects_entire_overlapping_region(self):
        s=actual_guard_function()
        self.assertIn("res->start <=",s)
        self.assertIn("res->end >=",s)

    def test_guard_uses_descriptor_metadata_only(self):
        s=actual_guard_function()
        self.assertIn("platform_get_resource(pdev, IORESOURCE_MEM, 0)",s)
        for forbid in ("ioremap","readl(","writel(","clk_prepare",
                       "reset_control","request_irq","dma_map",
                       "iommu","pci_host_probe","gpiod_"):
            with self.subTest(forbid=forbid):
                self.assertNotIn(forbid,s)

    def test_probe_refuses_before_mapping_or_reset(self):
        patch=PATCH13.read_text()
        check=patch.index("+\tif ("+GUARD_NAME+"(pdev))")
        deny=patch.index("+\t\treturn -EOPNOTSUPP;",check)
        kernel_alloc=patch.index(" \tdart = devm_kzalloc",check)
        self.assertLess(check,deny)
        self.assertLess(deny,kernel_alloc)
        self.assertIn("BEFORE any register map",patch)
        self.assertIn("probe blocked until DMA isolation is verified",patch)

    def test_fifty_thousand_actual_compiled_C_resource_vectors(self):
        gcc=shutil.which("gcc")
        self.assertIsNotNone(gcc)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            c=p/"model.c";exe=p/"model"
            c.write_text(MOCK_HEADER+"\n"+actual_guard_function()+"\n"+MOCK_MAIN)
            subprocess.run(
                [gcc,"-O2","-Wall","-Wextra","-Werror","-std=c11",
                 str(c),"-o",str(exe)],
                check=True,capture_output=True,text=True,timeout=25)
            ran=subprocess.run([str(exe)],check=True,
                 capture_output=True,text=True,timeout=15)
            self.assertIn("PRE_MMIO_GUARD_PASS",ran.stdout)
            self.assertIn("SYNTHETIC_VECTORS=50018",ran.stdout)

    def test_public_patch_avoids_private_data(self):
        s=PATCH13.read_text()
        self.assertIsNone(re.search(r"/home/[A-Za-z0-9._-]+/",s))
        self.assertNotIn("wifi_passphrase",s)
        self.assertNotIn("ECID",s)

    def test_workflow_never_claims_dma_operational(self):
        s=PATCH13.read_text()
        self.assertIn("requires verified requester/SID",s)
        self.assertIn("until DMA isolation is verified",s)

if __name__=="__main__":
    unittest.main()
