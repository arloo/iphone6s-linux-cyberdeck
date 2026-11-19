"""NVMe reset semantics are observable but never authorize DMA cleanup."""
from pathlib import Path
import subprocess
import tempfile
import unittest
root=Path(__file__).resolve().parents[1]

C=r"""
#include <assert.h>
#include <stdio.h>
#include "n71_s3e_post_reset_protocol.h"
int main(void) {
 struct n71_post_reset_protocol_observation p={
    .shutdown_attempted=1,.shutdown_rc=0,.shutdown_csts=9,
    .disable_rc=0,.disable_csts=0,.master_off=1,
    .cc=0,.csts=0,.root_command=2,.endpoint_command=2,
    .intms=0,.perst_high=1,.hmb_descriptor_zero=1,.queues_owned=1,
    .prepared=1,.dart_mapped=1,.hmb_owned=1
 };
 assert(!n71_post_reset_protocol_consistent(NULL));
 assert(n71_post_reset_protocol_consistent(&p));
 #define BAD(field,v) do { unsigned int saved=p.field;p.field=(v);assert(!n71_post_reset_protocol_consistent(&p));p.field=saved;} while(0)
 BAD(shutdown_attempted,0);
 BAD(shutdown_rc,1);
 BAD(shutdown_csts,1);
 BAD(disable_rc,1);
 BAD(disable_csts,1);
 BAD(master_off,0);
 BAD(cc,1);BAD(csts,1);
 BAD(root_command,6);BAD(endpoint_command,6);
 BAD(intms,1);
 BAD(perst_high,0);
 BAD(hmb_descriptor_zero,0);
 BAD(queues_owned,0);
 BAD(prepared,0);BAD(dart_mapped,0);BAD(hmb_owned,0);
 assert(n71_post_reset_protocol_consistent(&p));
 puts("POST_RESET_PROTOCOL_CONSISTENCY_ONLY_NO_DMA_AUTHORITY_PASS");
 return 0;
}
"""

class PostResetProtocolTests(unittest.TestCase):
    def test_compiled_consistency_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/"check.c"
            binary=Path(t)/"check"
            source.write_text(C)
            build=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
                 "-I",str(root/"experimental/port0"),str(source),"-o",str(binary)],
                 capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("NO_DMA_AUTHORITY_PASS",run.stdout)

    def test_integration_only_produces_readonly_predicate_log(self):
        owner=(root/"experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        self.assertIn('#include "n71_s3e_post_reset_protocol.h"',owner)
        start=owner.index("const struct n71_post_reset_protocol_observation p=")
        end=owner.index("ADMIN_POST_STOP_DMA_SNAPSHOT",start)
        excerpt=owner[start:end]
        self.assertIn("if (ans_phase_trace_ro)",owner[start-55:start])
        self.assertIn("ADMIN_POST_RESET_PROTOCOL_RO consistent=%u",excerpt)
        self.assertIn("DMA_QUARANTINE=YES",excerpt)
        self.assertIn("queue_write_authorized=NO",excerpt)
        self.assertIn("n71_post_reset_protocol_consistent(&p)",excerpt)
        for forbidden in ("n71_admin_write(", "writew(", "writel(",
                          "dma_unmap_single(", "free_page(", "gpiod_set_value("):
            self.assertNotIn(forbidden,excerpt)

    def test_semantic_gate_never_replaces_retire_gate_or_quarantine(self):
        header=(root/"experimental/port0/n71_s3e_post_reset_protocol.h").read_text()
        self.assertIn("does NOT establish",header)
        for forbidden in ("writel(","writew(","dma_unmap_single(","free_page(",
                          "n71_admin_write(","gpiod_set_value("):
            self.assertNotIn(forbidden,header)
        owner=(root/"experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        self.assertIn("if (ans_queue_retire_probe) {",owner)
        self.assertIn("rc=-3; /* pin every owned DMA resource until full phone restart */",owner)
        self.assertIn("if (rc==-3) return -3;",owner)
        self.assertIn("n71_queue_retire_gate(&v)",owner)

if __name__ == "__main__":
    unittest.main()
