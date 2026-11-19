"""S3E trace parsing must never claim DMA safety from queue-only evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "n71_s3e_gate_diagnostic", ROOT / "tools/n71_s3e_gate_diagnostic.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TraceParserTests(unittest.TestCase):
    def test_register_gate_names_and_failed_predicates(self):
        line = "n71-s3e-p0: ADMIN_QUEUE_RETIRE_GATES " + " ".join(
            f"{key}={0 if key in ('intms_bit0', 'hmb_zero') else 1}"
            for key in module.REGISTER_KEYS
        ) + " action=REFUSE_KEEP_QUARANTINE\n"
        log = line + "n71-s3e-p0: ADMIN_QUEUE_RETIRE_PROBE refused=1 exact_gate=0 DMA_QUARANTINE=YES"
        self.assertEqual(module.decode(log), ("REGISTER_REFUSED", ["hmb_zero", "intms_bit0"]))

    def test_phase_short_circuit_hmb_is_not_measured(self):
        line = "ADMIN_QUEUE_RETIRE_PHASE_GATES " + " ".join(
            f"{key}={0 if key in ('inner_ok', 'hmb_checked', 'hmb_owned') else 1}"
            for key in module.PHASE_KEYS
        )
        result = module.decode(line + "\nADMIN_QUEUE_RETIRE_PROBE refused=1 phase_gate=0")
        self.assertEqual(result, ("PHASE_REFUSED", ["inner_ok", "hmb_checked"]))

    def test_unqualified_or_missing_values_fail_closed(self):
        self.assertEqual(module.decode("ADMIN_QUEUE_RETIRE_PROBE refused=1 exact_gate=0"),
                         ("REGISTER_REFUSED_UNCLASSIFIED", []))
        malformed = "ADMIN_QUEUE_RETIRE_GATES " + " ".join(f"{key}=1" for key in module.REGISTER_KEYS)
        malformed = malformed.replace("intms_bit0=1", "intms_bit0=2")
        self.assertEqual(module.decode(malformed+"\nADMIN_QUEUE_RETIRE_PROBE refused=1 exact_gate=0"),
                         ("REGISTER_REFUSED_UNCLASSIFIED", []))
        self.assertEqual(module.decode("some unrelated kernel output"), ("NOT_OBSERVED", []))

    def test_queue_register_zero_does_not_imply_dma_retired(self):
        self.assertEqual(module.decode("ADMIN_QUEUE_RETIRE_PROBE armed=1 queue_regs_zero=1"),
                         ("QUEUE_REGS_ZERO_ONLY", []))

    def test_does_not_open_symlinked_private_log(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "trace"
            src.write_text("dummy")
            alias = Path(td) / "alias"
            alias.symlink_to(src)
            with self.assertRaises(ValueError):
                module.read_private_log(alias)


if __name__ == "__main__":
    unittest.main()
