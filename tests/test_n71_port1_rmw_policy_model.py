"""Actual native-C emulation of synthetic N71 S8000 port1 register RMW policy.

Tests stand-alone C bit transitions with 65,536 generated vectors,
and rejects any write to shared/global or other PCIe ports. All data
is synthetic; none originate from Apple kernelcache or physical MMIO.
"""
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"examples/n71-pcie-port1/port1_rmw_policy_model.c"

HARNESS=r"""
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
struct model_case {
    uint32_t slot, offset, mask;
    int inverted;
};
static const struct model_case examples[] = {
    {1968U,0x1A4U,1U,1},
    {1984U,0x194U,1U,0},
    {1992U,0x180U,1U<<8,0},
    {2000U,0x180U,1U<<20,0}
};
static uint32_t seed=0x91a5d39bU;
static uint32_t next(void) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}
#define REQUIRE(expr, why) do { \
 if (!(expr)) {fprintf(stderr,"FAIL: %s\n",why);return 7;} \
} while(0)
int main(void)
{
    unsigned i;
    uint32_t vectors=0;
    struct n71_synthetic_write x={0};
    for (i=0;i<65536U;i++) {
        const struct model_case *t = &examples[i%4U];
        uint32_t previous=next();
        uint32_t value=next()&1U;
        uint32_t wanted_bit=t->inverted?(value^1U):value;
        uint32_t expected=(previous&~t->mask) |
                          (wanted_bit ? t->mask : 0U);
        int r=n71_port1_calculate_synthetic_rmw(
            1U,t->slot,value,previous,&x);
        REQUIRE(r==0,"four original synthetic operations must be accepted");
        REQUIRE(x.register_relative_offset==t->offset,
                "incorrect relative port1 offset");
        REQUIRE(x.permitted_bit_mask==t->mask,"wrong target bit");
        REQUIRE(x.new_value==expected,"different from independent bit oracle");
        REQUIRE(((x.new_value^previous)&~t->mask)==0U,
                "neighboring synthetic bits clobbered");
        REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                    1U,x.register_relative_offset,x.permitted_bit_mask)==1,
                "known port1 operation blocked");
        ++vectors;
    }
    REQUIRE(vectors==65536U,"lost vectors");

    for (i=0;i<4U;i++) {
        uint32_t port=(i==0)?0U:(i==1)?2U:(i==2)?3U:5U;
        x=(struct n71_synthetic_write){111U,222U,333U};
        REQUIRE(n71_port1_calculate_synthetic_rmw(
                    port,1968U,1U,0U,&x)==-EINVAL,
                "cross-port write must be denied");
        REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                    port,0x1A4U,1U)==0,
                "cross-port write whitelist denied");
    }
    REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                1U,0x2CU,1U<<4)==0,
            "shared global status register must NEVER be writable");
    REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                1U,0x180U,1U)==0,
            "wrong per-port mask denied");
    REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                1U,0x180U,0xFFFFFFFFU)==0,
            "multi-bit mask denied");
    REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                1U,0x1ACU,1U)==0,
            "status-register write denied");
    REQUIRE(n71_port1_is_allowed_synthetic_register_write(
                1U,0U,1U)==0,
            "unknown target denied");

    x=(struct n71_synthetic_write){111U,222U,333U};
    REQUIRE(n71_port1_calculate_synthetic_rmw(
                1U,1888U,1U,1U,&x)==-EOPNOTSUPP,
            "unknown vtable operation denied");
    REQUIRE(x.register_relative_offset==0U &&
            x.permitted_bit_mask==0U && x.new_value==0U,
            "unsupported operation must clear output");
    REQUIRE(n71_port1_calculate_synthetic_rmw(
                1U,1968U,2U,1U,&x)==-EINVAL,
            "nonboolean value denied");
    REQUIRE(n71_port1_calculate_synthetic_rmw(
                1U,1968U,1U,1U,0)==-EINVAL,
            "null output denied");
    puts("N71_A9_PORT1_RMW_SYNTHETIC_C_VECTOR_PASS=65536");
    puts("SHARED_GLOBAL_MMIO_WRITES_ALLOWED=NO");
    puts("STORAGE_MODEM_OTHER_PORT_WRITES_ALLOWED=NO");
    return 0;
}
"""

class TestN71A9Port1RMWModel(unittest.TestCase):
    def test_actual_native_c_compiles_and_65536_vectors_pass(self):
        if not shutil.which("gcc"):
            self.skipTest("GNU C compiler unavailable")
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            src=root/"synthetic.c"
            src.write_text(C.read_text()+"\n"+HARNESS)
            elf=root/"rmw-simulation"
            cp=subprocess.run(["gcc","-std=c11","-O2","-Wall","-Wextra",
                               "-Werror","-o",str(elf),str(src)],
                              capture_output=True,text=True,timeout=20)
            self.assertEqual(cp.returncode,0,cp.stderr)
            out=subprocess.run([str(elf)],capture_output=True,
                               text=True,timeout=15)
            self.assertEqual(out.returncode,0,out.stderr)
            self.assertIn("PASS=65536",out.stdout)
            self.assertIn("SHARED_GLOBAL_MMIO_WRITES_ALLOWED=NO",out.stdout)

    def test_real_cross_compiler_aarch64_binary_object(self):
        if not shutil.which("aarch64-linux-gnu-gcc"):
            self.skipTest("ARM64 cross compiler unavailable")
        with tempfile.TemporaryDirectory() as td:
            obj=Path(td)/"rmw.o"
            cp=subprocess.run(["aarch64-linux-gnu-gcc","-std=c11",
                               "-Wall","-Wextra","-Werror","-c",
                               str(C),"-o",str(obj)],
                              capture_output=True,text=True,timeout=20)
            self.assertEqual(cp.returncode,0,cp.stderr)
            raw=obj.read_bytes()
            self.assertEqual(raw[:6],b"\x7fELF\x02\x01")
            self.assertEqual(int.from_bytes(raw[16:18],"little"),1)
            self.assertEqual(int.from_bytes(raw[18:20],"little"),183)

    def test_port1_only_and_explicit_global_write_ban(self):
        text=C.read_text()
        self.assertIn("port != N71_PORT1_INDEX",text)
        self.assertIn("N71_SHARED_ID1_OFFSET 0x02CU",text)
        self.assertIn("shared ID1 offset 0x2C",text)

    def test_unknown_controller_virtual_slot_fails_closed(self):
        self.assertIn("return -EOPNOTSUPP;",C.read_text())

    def test_boolean_input_strict(self):
        self.assertIn("boolean_value > 1U",C.read_text())

    def test_no_direct_device_hardware_apis(self):
        contents=C.read_text()
        for bad in ("writel(", "ioremap(", "readl(","regmap_","pci_enable",
                    "dma_map", "ioread", "clk_prepare", "gpiod_",
                    "request_irq(", "/dev/mem", "socket."):
            self.assertNotIn(bad,contents)

    def test_does_not_implement_a_real_driver(self):
        text=C.read_text()
        self.assertIn("NOT a device driver",text)
        self.assertIn("runtime physical provider resource",text)

    def test_wlan_bit_change_model_preserves_masked_output(self):
        text=C.read_text()
        self.assertIn("(previous_value & ~mask) | wanted",text)
        self.assertIn("boolean_value ^ 1U",text)

if __name__=="__main__":
    unittest.main()
