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

    def test_malformed_log_refuses(self):
        self.assertEqual(mod.interpret(log([1]*6).replace("intms_bit0=1","intms_bit0=9"))[0],
                         "MALFORMED")

if __name__=="__main__":
    unittest.main()
