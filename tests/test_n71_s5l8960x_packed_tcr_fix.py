"""Real C emulation + deterministic vectors for the S5L8960x packed TCR patch.

No Apple device data. Exercises the actual C function body reconstructed
from this project's public unified source patch, NOT a stand-in Python fix.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch"

def patched_function_pair()->str:
    diff=PATCH.read_text()
    assert diff.startswith("--- a/drivers/iommu/apple-dart.c\n")
    body=[]
    for line in diff.splitlines(keepends=True):
        if line.startswith(("---","+++","@@","\\")):
            continue
        if line and line[0] in ("+"," "):
            body.append(line[1:])
    text="".join(body)
    m=re.search(
        r"(static u32 apple_dart_s5l8960x_read_tcr\(.*?"
        r"(?=\nstatic u32 apple_dart_t8020_read_tcr))",text,re.S)
    if not m:
        raise AssertionError("Both original C functions missing from patched hunk")
    return m.group(1)

HEADER=r"""
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
typedef uint32_t u32;
typedef struct apple_dart_hw { unsigned int tcr; } hw_t;
typedef struct apple_dart {
    volatile unsigned char *regs;
    hw_t *hw;
    int lock;
} dart_t;
#define DART_S5L8960X_TCR_BITS_PER_STREAM 8
static int warning_count;
static int acquire_count, release_count;
#define WARN_ON(expr) ((expr) ? (++warning_count,1) : 0)
#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags)=0; ++acquire_count; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); ++release_count; } while (0)
static inline u32 readl(volatile void *p) { return *(volatile u32 *)p; }
static inline void writel(u32 val, volatile void *p) { *(volatile u32 *)p = val; }
"""
MAIN=r"""
int main(void) {
    u32 word=0, initial=0, sid=0, val=0, expected=0;
    hw_t hw={0};
    dart_t dart={(volatile unsigned char *)&word,&hw,0};
    unsigned long state=0x123456789abcdefULL;
    unsigned long count=0;
    for (unsigned it=0; it<2500;it++) {
        state ^= state << 7;
        state ^= state >> 9;
        state ^= state << 8;
        initial = (u32)state;
        for (sid=0;sid<4;sid++) {
            for (unsigned j=0;j<5;j++) {
                val=(u32)((state >> (j*9))&0xff);
                if (j==4) val=0xff;
                word=initial;
                apple_dart_s5l8960x_write_tcr(&dart,sid,val);
                expected=(initial & ~(0xffu << (8u*sid))) |
                          ((val & 0xffu) << (8u*sid));
                if(word != expected) {
                    fprintf(stderr,"BAD_LANE sid=%u it=%u\n",sid,it);
                    return 2;
                }
                if(apple_dart_s5l8960x_read_tcr(&dart,sid)!=val)
                    return 3;
                count++;
            }
        }
    }
    word=0x12345678;
    int before=warning_count;
    apple_dart_s5l8960x_write_tcr(&dart,4,0x33);
    if (word!=0x12345678 || warning_count!=before+1) return 4;
    before=warning_count;
    apple_dart_s5l8960x_write_tcr(&dart,2,0x100);
    if (word!=0x12345678 || warning_count!=before+1) return 5;
    before=warning_count;
    if (apple_dart_s5l8960x_read_tcr(&dart,4)!=0 ||
        warning_count!=before+1) return 6;
    if(acquire_count!=(int)count || release_count!=acquire_count) return 7;
    printf("S5L8960X_TCR_ACTUAL_PATCH_C_HARNESS_PASS VECTORS=%lu\n",count);
    return 0;
}
"""

class TestS5L8960XPackedTCR(unittest.TestCase):
    def test_patch_has_correct_api_boundaries(self):
        s=patched_function_pair()
        self.assertIn("static u32 apple_dart_s5l8960x_read_tcr",s)
        self.assertIn("static void apple_dart_s5l8960x_write_tcr",s)

    def test_patch_preserves_three_other_stream_lanes(self):
        s=patched_function_pair()
        self.assertIn("tcr = (tcr & ~mask) | ((val << shift) & mask);",s)
        self.assertNotIn("tcr &= 0xff <<",s)

    def test_patch_bounds_check_precedes_shift(self):
        s=patched_function_pair()
        assert "if (WARN_ON(sid >= 4 || val > 0xff))" in s
        self.assertLess(s.index("if (WARN_ON(sid >= 4 || val > 0xff))"),
                        s.index("shift = sid"))

    def test_patch_serializes_shared_register_rmw(self):
        s=patched_function_pair().split(
            "static void apple_dart_s5l8960x_write_tcr",1)[1]
        self.assertLess(s.index("spin_lock_irqsave"),s.index("tcr = readl"))
        self.assertLess(s.index("writel(tcr"),s.index("spin_unlock_irqrestore"))
        self.assertEqual(s.count("spin_lock_irqsave"),1)
        self.assertEqual(s.count("spin_unlock_irqrestore"),1)

    def test_patch_stops_on_invalid_read_sid(self):
        s=patched_function_pair()
        self.assertIn("if (WARN_ON(sid >= 4))\n\t\treturn 0;",s)

    def test_actual_c_functions_50000_vectors(self):
        if shutil.which("gcc") is None:
            self.skipTest("native gcc unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"packed_tcr.c"
            executable=root/"packed_tcr-test"
            source.write_text(HEADER+"\n"+patched_function_pair()+"\n"+MAIN)
            built=subprocess.run(
                ["gcc","-std=gnu11","-O2","-Wall","-Wextra","-Werror",
                 "-o",str(executable),str(source)],
                text=True,capture_output=True,timeout=25)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            ran=subprocess.run([str(executable)],
                               text=True,capture_output=True,timeout=15)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertIn("VECTORS=50000",ran.stdout)

    def test_old_shift_logic_corrupts_streams(self):
        word=0xA1B2C3D4
        sid=2
        val=0x55
        original=((word & (0xff << (sid*8))) | val)&0xffffffff
        expected=((word & ~(0xff << (sid*8))) | (val << (sid*8)))&0xffffffff
        self.assertNotEqual(original,expected)
        self.assertEqual(expected,0xA155C3D4)

    def test_experimental_dart_patch_excluded_from_known_good_boot_series(self):
        self.assertIn("experimental/patches/",str(PATCH))
        self.assertFalse((ROOT/"patches"/PATCH.name).exists())
        script=(ROOT/"scripts/check_kernel_rfc.sh").read_text()
        self.assertIn("00{01..11}-*.patch",script)
        self.assertNotIn("0012-",script)

    def test_patch_contains_no_direct_hardware_enumeration(self):
        s=PATCH.read_text()
        for forbidden in ("insmod","wlan0","/dev/mem","ioremap(",
                          "pci_enable_device(","readl_relaxed("):
            self.assertNotIn(forbidden,s)

if __name__=="__main__":
    unittest.main()
