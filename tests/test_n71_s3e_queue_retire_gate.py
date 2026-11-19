# SPDX-License-Identifier: MIT
"""Fail-closed, opt-in queue-register-only retirement model."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
C=r"""
#include <assert.h>
#include <stdio.h>
#include "n71_s3e_queue_retire_gate.h"
int main(void) {
    struct n71_queue_retire_observation g={
        .shutdown_attempted=1,.shutdown_rc=0,.shutdown_csts=9,
        .disable_rc=0,.disable_csts=0,.master_off=1,
        .cc=0,.csts=0,.root_command=2,.endpoint_command=2,
        .reset_low=1,.prepared=1,.regs_saved=1,.dart_mapped=1,
        .hmb_owned=1,.hmb_lo=0,.hmb_hi=0,.hmb_size=0,
        .intms=1,.aqa=0x000f000f,.asq_lo=0x80010000,
        .asq_hi=0,.acq_lo=0x80011000,.acq_hi=0
    };
    assert(!n71_queue_retire_gate(NULL));
    assert(n71_queue_retire_gate(&g));
    #define ASSERT_BAD(field,value) do { unsigned int before=g.field;g.field=(value);assert(!n71_queue_retire_gate(&g));g.field=before; } while(0)
    ASSERT_BAD(shutdown_attempted,0);
    ASSERT_BAD(shutdown_rc,1);
    ASSERT_BAD(shutdown_csts,1);
    ASSERT_BAD(disable_rc,1);
    ASSERT_BAD(disable_csts,1);
    ASSERT_BAD(master_off,0);
    ASSERT_BAD(cc,1);
    ASSERT_BAD(csts,1);
    ASSERT_BAD(root_command,6);
    ASSERT_BAD(endpoint_command,6);
    ASSERT_BAD(reset_low,0);
    ASSERT_BAD(prepared,0);
    ASSERT_BAD(regs_saved,0);
    ASSERT_BAD(dart_mapped,0);
    ASSERT_BAD(hmb_owned,0);
    ASSERT_BAD(hmb_lo,0xbc000000);
    ASSERT_BAD(hmb_hi,1);
    ASSERT_BAD(hmb_size,8388608);
    ASSERT_BAD(intms,0);
    ASSERT_BAD(aqa,0);
    ASSERT_BAD(asq_lo,0);
    ASSERT_BAD(asq_hi,1);
    ASSERT_BAD(acq_lo,0);
    ASSERT_BAD(acq_hi,1);
    assert(n71_queue_retire_gate(&g));
    puts("QUEUE_REGISTER_PROBE_FAIL_CLOSED_GATES_PASS");
    return 0;
}
"""

class QueueGateTests(unittest.TestCase):
    def test_compiled_fail_closed_gate_all_fields(self):
        with tempfile.TemporaryDirectory() as td:
            src=pathlib.Path(td)/"model.c"
            src.write_text(C)
            binary=pathlib.Path(td)/"model"
            r=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
                              "-I",str(ROOT/"experimental/port0"),str(src),
                              "-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("QUEUE_REGISTER_PROBE_FAIL_CLOSED_GATES_PASS",r.stdout)

    def test_refusal_diagnostics_preserve_exact_gate_and_private_addresses(self):
        source=(ROOT/"experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        start=source.index("if (!n71_queue_retire_gate(&v))")
        end=source.index("/* CC=0, CSTS=0", start)
        refusal=source[start:end]
        self.assertIn("ADMIN_QUEUE_RETIRE_GATES", refusal)
        for gate in ("shn=%u", "disable=%u", "master_off=%u", "controller_zero=%u",
                     "command_words_2=%u", "reset_low=%u", "prepared=%u",
                     "regs_saved=%u", "dart_mapped=%u", "hmb_owned=%u",
                     "hmb_zero=%u", "intms_bit0=%u", "queue_owned=%u"):
            with self.subTest(gate=gate):
                self.assertIn(gate, refusal)
        self.assertIn("action=REFUSE_KEEP_QUARANTINE", refusal)
        self.assertIn("return;", refusal)
        for forbidden in ("n71_admin_write(", "writel(", "writew(", "free_page(",
                          "dma_unmap_single(", "pr_info(\"physical", "iova_base_low=%08x"):
            self.assertNotIn(forbidden, refusal)

    def test_prephase_refusal_identifies_all_guards_without_unqualified_hmb_read(self):
        source=(ROOT/"experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        start=source.index("static void n71_admin_queue_register_retire_probe(")
        end=source.index("v.shutdown_attempted=",start)
        phase=source[start:end]
        self.assertIn("if (!ans_queue_retire_probe) return;",phase)
        self.assertIn("phase_ok=ans_identify_once && r->shutdown_attempted &&",phase)
        self.assertIn("if (phase_ok)\n        hmb_owned=n71_storage_hmb_owned_ready(ctx);",phase)
        self.assertIn("if (!phase_ok || !hmb_owned)",phase)
        self.assertIn("ADMIN_QUEUE_RETIRE_PHASE_GATES",phase)
        for gate in ("identify_armed=%u","shutdown_attempted=%u",
                     "shutdown_ok=%u","disable_ok=%u","inner_ok=%u",
                     "master_off=%u","hmb_checked=%u","hmb_owned=%u"):
            with self.subTest(gate=gate):
                self.assertIn(gate,phase)
        self.assertIn("action=REFUSE_KEEP_QUARANTINE",phase)
        self.assertIn("phase_gate=0 DMA_QUARANTINE=YES",phase)
        for forbidden in ("n71_admin_write(", "writel(", "writew(",
                          "free_page(", "dma_unmap_single(", "iova_base_low="):
            self.assertNotIn(forbidden,phase)

    def test_opt_in_and_no_release_path(self):
        owner=(ROOT/"experimental/port0/n71_s3e_p0_asserted_reset_rootstart.c").read_text()
        source=(ROOT/"experimental/port0/n71_s3e_admin_identify_once.h").read_text()
        self.assertIn("static bool ans_queue_retire_probe;",owner)
        self.assertIn("module_param(ans_queue_retire_probe, bool, 0400);",owner)
        start=source.index("static void n71_admin_queue_register_retire_probe(")
        end=source.index("static int n71_storage_admin_identify_once(",start)
        trial=source[start:end]
        self.assertIn("if (!ans_queue_retire_probe) return;",trial)
        self.assertIn("n71_queue_retire_gate(&v)",trial)
        self.assertIn("n71_admin_write(i,0);",trial)
        for forbidden in ("dma_unmap_single(", "free_page(", "n71_admin_dart_map(",
                          "n71_admin_unprepare(", "n71_storage_admin_free(",
                          "writel(", "writew(", "gpio_direction_output("):
            self.assertNotIn(forbidden,trial)
        marker=source.index("if (ans_queue_retire_probe) {",end)
        self.assertIn("rc=-3;",source[marker:marker+180])
        self.assertIn("if (rc==-3) return -3;",source[marker:])

if __name__=="__main__":
    unittest.main()
