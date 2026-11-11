"""Synthetic N71 Wi-Fi config regression tests, no private kernel configs."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"tools/n71_wifi_kernel_baseline_gate.py"
sp=importlib.util.spec_from_file_location("n71_wifi_kernel_gate",P)
g=importlib.util.module_from_spec(sp)
sp.loader.exec_module(g)

def example():
    original={**g.REQUIRED_BASE,
              "CONFIG_WIRELESS":"n","CONFIG_WLAN":"n",
              "CONFIG_MODULE_UNLOAD":"n",
              "CONFIG_GPIO_APPLE_PMIC":"m",
              "CONFIG_FB":"y",
              "CONFIG_USB_LIBCOMPOSITE":"y"}
    candidate={**original,**g.REQUIRED_NEW}
    return original,candidate

class TestN71WiFiConfigCompatibility(unittest.TestCase):
    def test_preserved_known_good_touch_display_usb(self):
        before,after=example()
        r=g.verify(before,after)
        self.assertGreaterEqual(r["preserved_enabled_symbols"],11)

    def test_reject_touch_removal(self):
        a,b=example()
        b["CONFIG_TOUCHSCREEN_APPLE_Z2"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_usb_gadget_removal(self):
        a,b=example()
        b["CONFIG_USB_CONFIGFS_NCM"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_drm_removal(self):
        a,b=example()
        b["CONFIG_DRM_SIMPLEDRM"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_dart_removal(self):
        a,b=example()
        b["CONFIG_APPLE_DART"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_wrong_radio_bus(self):
        a,b=example()
        b["CONFIG_BRCMFMAC_PCIE"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_sdio_radio(self):
        a,b=example()
        b["CONFIG_BRCMFMAC_SDIO"]="y"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_disabled_firmware_loader(self):
        a,b=example()
        b["CONFIG_BRCMFMAC"]="n"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_research_host_guard_activation(self):
        a,b=example()
        b["CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD"]="y"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_unrelated_pci_driver(self):
        a,b=example()
        a["CONFIG_SOME_OTHER_PCIE_HOST"]="n"
        b["CONFIG_SOME_OTHER_PCIE_HOST"]="y"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_reject_module_unload_semantics_changed(self):
        a,b=example()
        b["CONFIG_MODULE_UNLOAD"]="y"
        with self.assertRaises(g.UnqualifiedConfig):g.verify(a,b)

    def test_parse_disabled_flags(self):
        x=g.parse_kconfig(
            b'CONFIG_TOUCHSCREEN_APPLE_Z2=y\n# CONFIG_WIRELESS is not set\n')
        self.assertEqual(x["CONFIG_WIRELESS"],"n")
        self.assertEqual(x["CONFIG_TOUCHSCREEN_APPLE_Z2"],"y")

    def test_reject_duplicate_symbols(self):
        with self.assertRaises(g.UnqualifiedConfig):
            g.parse_kconfig(b"CONFIG_DRM=y\nCONFIG_DRM=n\n")

    def test_cli_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"fake"
            p.write_bytes(b"not a valid config")
            r=subprocess.run([sys.executable,str(P),str(p),str(p)],
                             capture_output=True,text=True,timeout=8)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("FAIL_CLOSED",r.stderr)

    def test_no_device_or_filesystem_write(self):
        s=P.read_text()
        for prohibited in ("write_bytes(", "open('/dev/", "subprocess.run(",
                           "mmap(", "ioremap(", "readl(", "writel("):
            self.assertNotIn(prohibited,s)

if __name__=="__main__":
    unittest.main()
