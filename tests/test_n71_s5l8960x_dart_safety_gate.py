"""Synthetic fail-closed DART1 reset-probe guard, no private Apple data."""
from pathlib import Path
import importlib.util
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/n71_s5l8960x_dart_safety_gate.py"
SPEC=importlib.util.spec_from_file_location("n71_dart_safety",SCRIPT)
gate=importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)

PATCH=ROOT/"experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch"

def patched_functions()->str:
    rows=PATCH.read_text().splitlines(keepends=True)
    lines=[]
    for row in rows:
        if row.startswith(("---","+++","@@")):
            continue
        if row and row[0] in ("+"," "):
            lines.append(row[1:])
    text="".join(lines)
    a=text.index("static u32 apple_dart_s5l8960x_read_tcr")
    b=text.index("\nstatic u32 apple_dart_t8020_read_tcr",a)
    return text[a:b]

def synthetic_source()->str:
    return r'''
#define DART_S5L8960X_TCR_BITS_PER_STREAM 8
struct apple_dart_hw apple_dart_hw_s5l8960x = {
  .max_sid_count = 4,
};
.compatible = "apple,s5l8960x-dart",
static int apple_dart_status(struct apple_dart *dart) {
 dart->supports_bypass = 0;
 return 0;
}
'''+patched_functions()+r'''
static int apple_dart_hw_reset(struct apple_dart *dart) {
 bitmap_set(stream_map.sidmap, 0, dart->num_streams);
 apple_dart_hw_disable_dma(&stream_map);
 apple_dart_hw_clear_all_ttbrs(&stream_map);
 return 0;
}
static int apple_dart_probe(struct platform_device *dev) {
 return apple_dart_hw_reset(dart);
}
static void apple_dart_remove(struct platform_device *dev) {
 apple_dart_hw_reset(dart);
}
static __maybe_unused int apple_dart_resume(struct device *dev) {
 return apple_dart_hw_reset(dart);
}
'''

class TestN71S5L8960XDARTSafety(unittest.TestCase):
    def pass_source(self,source):
        return gate.classify(source)

    def reject(self,source):
        with self.assertRaises(gate.UnqualifiedDART):
            self.pass_source(source)

    def test_valid_synthetic_patch_source_classifies_blocked(self):
        out=self.pass_source(synthetic_source())
        self.assertTrue(out["packed_tcr_rmw_patched"])
        self.assertTrue(out["whole_dart_reset_on_probe"])
        self.assertTrue(out["whole_dart_reset_on_resume"])
        self.assertTrue(out["whole_dart_reset_on_remove"])
        self.assertFalse(out["safe_to_activate_dart1"])

    def test_original_bit_mask_corruption_rejected(self):
        src=synthetic_source().replace(
            "tcr = (tcr & ~mask) | ((val << shift) & mask);",
            "tcr &= 0xff << (sid * 8);")
        self.reject(src)

    def test_missing_shared_register_spinlock_rejected(self):
        self.reject(synthetic_source().replace(
            "spin_lock_irqsave(&dart->lock, flags);","/* omitted */"))

    def test_lock_after_mmio_read_rejected(self):
        src=synthetic_source()
        src=src.replace(
          "spin_lock_irqsave(&dart->lock, flags);\n\ttcr = readl",
          "tcr = readl(dart->regs + dart->hw->tcr);\n"
          "\tspin_lock_irqsave(&dart->lock, flags);\n\ttcr = readl")
        self.reject(src)

    def test_invalid_sid_bounds_rejected(self):
        self.reject(synthetic_source().replace(
           "if (WARN_ON(sid >= 4 || val > 0xff))",
           "if (WARN_ON(sid >= 5 || val > 0xff))"))

    def test_abnormal_stream_count_rejected(self):
        self.reject(synthetic_source().replace(".max_sid_count = 4",
                                               ".max_sid_count = 32"))

    def test_unknown_iommu_compatible_rejected(self):
        self.reject(synthetic_source().replace(
          "apple,s5l8960x-dart","apple,not-known-dart"))

    def test_missing_reset_dma_disable_rejected(self):
        self.reject(synthetic_source().replace(
          "apple_dart_hw_disable_dma(&stream_map);","/* removed */"))

    def test_missing_reset_ttbr_clear_rejected(self):
        self.reject(synthetic_source().replace(
          "apple_dart_hw_clear_all_ttbrs(&stream_map);","/* removed */"))

    def test_mismatched_resume_semantics_rejected(self):
        self.reject(synthetic_source().replace(
          "static __maybe_unused int apple_dart_resume(struct device *dev) {\n return apple_dart_hw_reset(dart);",
          "static __maybe_unused int apple_dart_resume(struct device *dev) {\n return 0;"))

    def test_no_bypass_metadata_fails(self):
        self.reject(synthetic_source().replace(
          "dart->supports_bypass = 0;","dart->supports_bypass = 1;"))

    def test_valid_synthetic_arm64_relocatable_header(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fake.o"
            data=bytearray(64)
            data[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",data,16,1)
            struct.pack_into("<H",data,18,183)
            p.write_bytes(data)
            self.assertTrue(gate.is_aarch64_rel_object(p))

    def test_wrong_architecture_object_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fake.o"
            data=bytearray(64)
            data[:6]=b"\x7fELF\x02\x01"
            struct.pack_into("<H",data,16,1)
            struct.pack_into("<H",data,18,62)
            p.write_bytes(data)
            self.assertFalse(gate.is_aarch64_rel_object(p))

    def test_no_hardware_or_write_apis(self):
        text=SCRIPT.read_text()
        for disallowed in ("write_bytes(", "mmap(", "ioremap(",
                           "subprocess.run(", "insmod ","modprobe ",
                           "socket.", "/dev/mem", "git push"):
            self.assertNotIn(disallowed,text)
        # Source-pattern checks mention readl/writel as strings; they are
        # not function calls performed by this Python tool.
        self.assertNotIn("\n    writel(",text)
        self.assertNotIn("\n    readl(",text)

    def test_explicit_no_hardware_bringup_claim(self):
        text=SCRIPT.read_text()
        for required in ("DART_WHOLE_INSTANCE_RESET_ON_PROBE_REMOVE_RESUME=YES",
                         "ACTUAL_SID_IOVA_DMA_FAULT_ISOLATION_PROVEN=NO",
                         "DART1_PHYSICAL_BRINGUP_AUTHORIZED=NO"):
            self.assertIn(required,text)

if __name__=="__main__":
    unittest.main()
