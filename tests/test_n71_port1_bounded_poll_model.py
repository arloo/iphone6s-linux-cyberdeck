"""Synthetic-only C execution of the N71/S8000 port-1 bounded-poll model.

No Apple binary or physical hardware data is used. The C source is tested
with a callback that creates fake status values; the actual ARM64 object is
compiled only, never run on an iPhone.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"examples/n71-pcie-port1/port1_bounded_poll_model.c"
HARNESS=r"""
#include <stdint.h>
#include <stdio.h>
#include <errno.h>

struct synthetic_state {
    unsigned calls, nonzero_on, fail_on, unexpected_port;
};

static int synthetic_status(void *ptr, uint32_t port, uint32_t *status)
{
    struct synthetic_state *s = ptr;
    ++s->calls;
    if (port != 1U) ++s->unexpected_port;
    if (s->fail_on != 0U && s->calls == s->fail_on) return -1;
    *status = (s->nonzero_on != 0U && s->calls >= s->nonzero_on) ? 7U : 0U;
    return 0;
}
#define CHECK(expr, msg) do { \
    if (!(expr)) {fprintf(stderr,"FAIL: %s\n",msg); return 2;} \
} while(0)

int main(void)
{
    unsigned cases=0, n=0, status=0;
    struct synthetic_state st={0};
    int r=0;
    st.nonzero_on=1;
    r=n71_port1_bounded_status_query(synthetic_status,&st,1,5,&n,&status);
    CHECK(r==0 && n==1 && status==7 && st.calls==1,"first response");
    ++cases;

    st=(struct synthetic_state){.nonzero_on=3};
    r=n71_port1_bounded_status_query(synthetic_status,&st,1,5,&n,&status);
    CHECK(r==0 && n==3 && st.calls==3 && status==7,"third response");
    ++cases;

    st=(struct synthetic_state){.nonzero_on=99};
    r=n71_port1_bounded_status_query(synthetic_status,&st,1,4,&n,&status);
    CHECK(r==-ETIMEDOUT && n==4 && st.calls==4 && status==0,"timeout");
    ++cases;

    st=(struct synthetic_state){.fail_on=2};
    r=n71_port1_bounded_status_query(synthetic_status,&st,1,4,&n,&status);
    CHECK(r==-EIO && n==2 && st.calls==2,"callback failure");
    ++cases;

    st=(struct synthetic_state){.nonzero_on=1};
    r=n71_port1_bounded_status_query(synthetic_status,&st,0,3,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"storage port0 blocked");
    ++cases;

    r=n71_port1_bounded_status_query(synthetic_status,&st,2,3,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"baseband port2 blocked");
    ++cases;

    r=n71_port1_bounded_status_query(synthetic_status,&st,3,3,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"unknown port3 blocked");
    ++cases;

    r=n71_port1_bounded_status_query(synthetic_status,&st,1,0,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"zero retries blocked");
    ++cases;

    r=n71_port1_bounded_status_query(synthetic_status,&st,1,4097,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"excessive retries blocked");
    ++cases;

    r=n71_port1_bounded_status_query(0,&st,1,1,&n,&status);
    CHECK(r==-EINVAL && st.calls==0,"null callback blocked");
    ++cases;

    r=n71_port1_bounded_status_query(synthetic_status,&st,1,1,0,&status);
    CHECK(r==-EINVAL && st.calls==0,"null attempt output blocked");
    ++cases;

    st=(struct synthetic_state){.nonzero_on=0};
    r=n71_port1_bounded_status_query(synthetic_status,&st,1,4096,&n,&status);
    CHECK(r==-ETIMEDOUT && n==4096 && st.calls==4096 &&
          st.unexpected_port==0,"maximum bounded retries");
    ++cases;

    printf("N71_PORT1_FAKE_STATUS_POLL_C_HARNESS_PASS CASES=%u\n",cases);
    return 0;
}
"""

class TestN71Port1BoundedPolling(unittest.TestCase):
    def test_actual_c_model_compiles_and_executes_12_cases(self):
        if not shutil.which("gcc"):
            self.skipTest("Native C compiler not installed")
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            driver=p/"port1_model.c"
            driver.write_text(SOURCE.read_text()+"\n"+HARNESS)
            compiled=subprocess.run([
                "gcc","-std=c11","-O2","-Wall","-Wextra","-Werror",
                "-o",str(p/"port1_test"),str(driver)],
                text=True,capture_output=True,timeout=15)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            executed=subprocess.run([str(p/"port1_test")],
                                    text=True,capture_output=True,timeout=10)
            self.assertEqual(executed.returncode,0,executed.stderr)
            self.assertIn("CASES=12",executed.stdout)

    def test_arm64_cross_compiler_emits_relocatable_elf(self):
        if not shutil.which("aarch64-linux-gnu-gcc"):
            self.skipTest("AArch64 compiler not installed")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"model.o"
            result=subprocess.run(
                ["aarch64-linux-gnu-gcc","-std=c11","-Wall","-Wextra",
                 "-Werror","-c",str(SOURCE),"-o",str(path)],
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            b=path.read_bytes()
            self.assertTrue(b.startswith(b"\x7fELF\x02\x01"))
            self.assertEqual(int.from_bytes(b[18:20],"little"),183)

    def test_port1_only_compile_time_policy(self):
        text=SOURCE.read_text()
        self.assertIn("#define N71_WLAN_PORT_INDEX 1U",text)
        self.assertIn("port != N71_WLAN_PORT_INDEX",text)

    def test_retry_bound_is_finite(self):
        text=SOURCE.read_text()
        self.assertIn("N71_MAX_OFFLINE_POLL_ATTEMPTS 4096U",text)
        self.assertIn("max_attempts == 0U",text)
        self.assertIn("max_attempts > N71_MAX_OFFLINE_POLL_ATTEMPTS",text)

    def test_returns_distinct_failures(self):
        text=SOURCE.read_text()
        for expected in ("return -EINVAL","return -EIO","return -ETIMEDOUT"):
            self.assertIn(expected,text)

    def test_no_proprietary_original_kernel_included(self):
        text=SOURCE.read_text()
        for forbidden in ("AppleS800xPCIe.__text", "kernelcache.release.n71",
                          "#include \"Apple", "/home/arlo"):
            self.assertNotIn(forbidden,text)

    def test_no_pcie_driver_hardware_access(self):
        text=SOURCE.read_text()
        for forbidden in ("ioremap(", "readl(", "writel(", "pci_enable",
                          "dma_map", "regmap", "gpiod_", "reset_control_",
                          "clk_prepare", "request_irq", "/dev/mem"):
            self.assertNotIn(forbidden,text)

    def test_no_false_link_training_or_wifi_claim(self):
        text=SOURCE.read_text()
        self.assertIn("DOES NOT claim",text)
        self.assertIn("nonzero",text)
        self.assertIn("Never register",text)

if __name__=="__main__":
    unittest.main()
