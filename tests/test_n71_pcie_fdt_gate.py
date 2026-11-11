"""Offline compiled-FDT fail-closed tests for N71/S8000 port-1 PCIe research.

All inputs are synthetic and no test accesses a phone, MMIO or firmware.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=(ROOT/"examples/n71-pcie-port1/port1-disabled.dts").read_text()
TOOL=ROOT/"tools/n71_pcie_fdt_gate.py"


class TestN71PcieFdtGate(unittest.TestCase):
    def setUp(self):
        if not shutil.which("dtc"):
            self.skipTest("Host dtc not installed")
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)

    def validate(self,dts,valid=False):
        dtsp=self.path/"candidate.dts"
        dtbp=self.path/"candidate.dtb"
        dtsp.write_text(dts)
        compiled=subprocess.run(
            ["dtc","-q","-I","dts","-O","dtb","-o",str(dtbp),str(dtsp)],
            capture_output=True,text=True,timeout=8,
        )
        self.assertEqual(compiled.returncode,0,compiled.stderr)
        verdict=subprocess.run(
            ["python3",str(TOOL),str(dtbp)],
            capture_output=True,text=True,timeout=8,
        )
        self.assertEqual(verdict.returncode,0 if valid else 1,
                         verdict.stdout+verdict.stderr)
        return verdict.stdout

    def replace(self,old,new):
        self.assertIn(old,BASE)
        return BASE.replace(old,new,1)

    def test_only_disabled_nonbootable_scaffold_accepted(self):
        result=self.validate(BASE,valid=True)
        self.assertIn("OFFLINE_STRUCTURE_PASS",result)
        self.assertIn("HARDWARE_PROBE_BLOCKED",result)

    def test_s8003_fab_is_not_this_hardware(self):
        self.validate(self.replace('"apple,n71"','"apple,n71m"'))

    def test_pcie_host_would_trigger_unsafe_global_setup(self):
        self.validate(self.replace(
            '"apple,s8000-pcie-unimplemented";\n            status = "disabled";',
            '"apple,s8000-pcie-unimplemented";\n            status = "okay";',
        ))

    def test_port0_storage_must_be_disabled(self):
        self.validate(self.replace(
            'port@0 {\n                reg = <0x0000>;\n                status = "disabled";',
            'port@0 {\n                reg = <0x0000>;\n                status = "okay";',
        ))

    def test_port2_baseband_must_be_disabled(self):
        self.validate(self.replace(
            'port@1000 {\n                reg = <0x1000>;\n                status = "disabled";',
            'port@1000 {\n                reg = <0x1000>;\n                status = "okay";',
        ))

    def test_wifi_port1_still_cannot_be_live_probed(self):
        self.validate(self.replace(
            'port@800 {\n                reg = <0x0800>;\n                status = "disabled";',
            'port@800 {\n                reg = <0x0800>;\n                status = "okay";',
        ))

    def test_unknown_port3_must_be_disabled(self):
        self.validate(self.replace(
            'port@1800 {\n                reg = <0x1800>;\n                status = "disabled";',
            'port@1800 {\n                reg = <0x1800>;\n                status = "okay";',
        ))

    def test_dart_must_remain_disabled(self):
        self.validate(self.replace(
            '"apple,s8000-dart-unimplemented";\n            status = "disabled";',
            '"apple,s8000-dart-unimplemented";\n            status = "okay";',
        ))

    def test_fake_newer_host_compatible_rejected(self):
        self.validate(self.replace('"apple,s8000-pcie-unimplemented"',
                                   '"apple,pcie"'))

    def test_wrong_a9_dart_rejected(self):
        self.validate(self.replace('"apple,s8000-dart-unimplemented"',
                                   '"apple,t8103-dart"'))

    def test_missing_port2_rejected(self):
        self.validate(self.replace(
            '''            port@1000 {
                reg = <0x1000>;
                status = "disabled";
            };

''', ""))

    def test_duplicate_port_rejected(self):
        # The two node names differ, so dtc compiles the DTB. The guard
        # must still reject identical numeric port indices.
        self.validate(self.replace(
            'port@1800 {\n                reg = <0x1800>;',
            'port@1800 {\n                reg = <0x1000>;',
        ))

    def test_malformed_port_reg_alignment_rejected(self):
        self.validate(self.replace(
            'port@800 {\n                reg = <0x0800>;',
            'port@801 {\n                reg = <0x0801>;',
        ))

    def test_malicious_host_mmio_resource_rejected(self):
        self.validate(self.replace(
            '''            compatible = "apple,s8000-pcie-unimplemented";
            status = "disabled";''',
            '''            compatible = "apple,s8000-pcie-unimplemented";
            status = "disabled";
            reg = <0 0x60000000 0 0x1000>;''',
        ))

    def test_dart_dma_resource_rejected(self):
        self.validate(self.replace(
            '''            compatible = "apple,s8000-dart-unimplemented";
            status = "disabled";''',
            '''            compatible = "apple,s8000-dart-unimplemented";
            status = "disabled";
            iommus = <0 0>;''',
        ))

    def test_unexpected_pcie_endpoint_rejected(self):
        self.validate(self.replace(
            '''        dart-apcie1 {
''',
            '''        pcie-other {
            compatible = "apple,pcie";
            status = "okay";
        };
        dart-apcie1 {
''',
        ))

    def test_bad_port_child_properties_rejected(self):
        self.validate(self.replace(
            '''            port@800 {
                reg = <0x0800>;
                status = "disabled";''',
            '''            port@800 {
                reg = <0x0800>;
                status = "disabled";
                interrupts = <77>;''',
        ))

    def test_broken_fdt_magic_rejected(self):
        f=self.path/"invalid.dtb"
        f.write_bytes(b"BAD" + b"\0"*44)
        r=subprocess.run(["python3",str(TOOL),str(f)],capture_output=True,text=True)
        self.assertEqual(r.returncode,1)
        self.assertIn("FAIL_CLOSED",r.stdout)

    def test_truncated_fdt_rejected(self):
        dts=self.path/"candidate.dts"
        f=self.path/"candidate.dtb"
        dts.write_text(BASE)
        subprocess.run(["dtc","-q","-I","dts","-O","dtb","-o",str(f),str(dts)],
                       check=True,capture_output=True)
        b=f.read_bytes()
        f.write_bytes(b[:len(b)//2])
        r=subprocess.run(["python3",str(TOOL),str(f)],capture_output=True,text=True)
        self.assertEqual(r.returncode,1)
        self.assertIn("FAIL_CLOSED",r.stdout)


if __name__=="__main__":
    unittest.main()
