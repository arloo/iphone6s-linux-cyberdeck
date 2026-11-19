"""Read-only CC phase trace analyzer rejects missing or malformed hardware samples."""
import importlib.util
from pathlib import Path
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("n71_cc_phase_trace",root/"tools/n71_s3e_cc_phase_trace.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def log(values,high=1):
    return "\n".join(
        f"[ 10.{i:06d}] n71-s3e-p0: ADMIN_CC_INTMS_RO phase={phase} edge={edge} "
        f"intms_bit0={value} perst_high={high} no_dma_release=YES"
        for i,((phase,edge),value) in enumerate(zip(mod.ORDER,values))
    )

class PhaseTraceParseTests(unittest.TestCase):
    def test_detect_first_cleared_after_shutdown(self):
        status,detail,missing=mod.interpret(log([1,1,1,1,0,0]))
        self.assertEqual(status,"MASK_CLEARED")
        self.assertIn("shutdown_after",detail)
        self.assertEqual(missing,[])

    def test_mask_retained(self):
        self.assertEqual(mod.interpret(log([1]*6))[0],"MASK_RETAINED")

    def test_missing_and_duplicate_refuse(self):
        self.assertEqual(mod.interpret(log([1]*5))[0],"INCOMPLETE")
        dup=log([1]*6)+"\n"+log([1]*6).splitlines()[0]
        self.assertEqual(mod.interpret(dup)[0],"DUPLICATE")

    def test_unexpected_perst_refuses(self):
        self.assertEqual(mod.interpret(log([1]*6,high=0))[0],"PERST_UNEXPECTED")

    def test_postcore_phase_transition_localized_to_short_window(self):
        extra=("[ 303.537120] n71-s3e-p0: ADMIN_POST_CORE_RO "
               "intms_bit0=0 reset_low=0 hmb_descriptor_zero=1 "
               "queues_owned=1 master_off=1 no_dma_release=YES")
        result,detail=mod.classify_postcore(log([1]*6)+"\n"+extra)
        self.assertEqual(result,"AFTER_DISABLE_BEFORE_POSTCORE_MASK_FELL")
        self.assertIn("postcore=0",detail)
        self.assertIn("reset_low=0",detail)

    def test_postcore_missing_or_duplicate_cannot_prove_transition(self):
        self.assertEqual(mod.classify_postcore(log([1]*6))[0],"NO_POSTCORE_SAMPLE")
        extra=("ADMIN_POST_CORE_RO intms_bit0=0 reset_low=0 "
               "hmb_descriptor_zero=1 queues_owned=1 master_off=1 no_dma_release=YES")
        self.assertEqual(mod.classify_postcore(log([1]*6)+"\n"+extra+"\n"+extra)[0],
                         "AMBIGUOUS_POSTCORE_SAMPLE")

    def test_postcore_malformed_and_phase_incomplete_fail_closed(self):
        extra=("ADMIN_POST_CORE_RO intms_bit0=0 reset_low=0 "
               "hmb_descriptor_zero=1 queues_owned=1 master_off=1 no_dma_release=YES")
        self.assertEqual(mod.classify_postcore(log([1]*5)+"\n"+extra)[0],
                         "UNQUALIFIED_PHASE_SEQUENCE")
        self.assertEqual(mod.classify_postcore(log([1]*6)+"\n"+
                                            extra.replace("intms_bit0=0","intms_bit0=9"))[0],
                         "MALFORMED_POSTCORE_SAMPLE")

    def test_malformed_log_refuses(self):
        self.assertEqual(mod.interpret(log([1]*6).replace("intms_bit0=1","intms_bit0=9"))[0],
                         "MALFORMED")

if __name__=="__main__":
    unittest.main()
