"""No-device synthetic tests for N71 USB-RAM Linux read-only field collector."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"tools/n71_usb_wlan_fieldtest_collect.py"
SP=importlib.util.spec_from_file_location("n71_collector_unit",SOURCE)
assert SP and SP.loader
G=importlib.util.module_from_spec(SP);SP.loader.exec_module(G)

SAFE=b"""device-shell-private-junk\nN71_WLAN_FIELDTEST_BOARD_N71_S8000_PASS\r\nN71_WLAN_FIELDTEST_ACCESS_MODE_SYSFS_PROCFS_METADATA_ONLY\nN71_WLAN_FIELDTEST_PCIE_CORE_PRESENT=YES\nN71_WLAN_FIELDTEST_PCI_DEVICES_COUNT=0\nN71_WLAN_FIELDTEST_IOMMU_GROUPS_COUNT=0\nN71_WLAN_FIELDTEST_N71_DART1_PLATFORM_NODES_MATCHED=0\nN71_WLAN_FIELDTEST_WLAN_INTERFACES_COUNT=0\nN71_WLAN_FIELDTEST_NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS=YES\nN71_WLAN_FIELDTEST_TEST_FINISHED\n__N71_READONLY_DIAGNOSTIC_DONE__\n"""

class TestN71USBFieldCollector(unittest.TestCase):
    def test_only_allowlisted_linux_metadata_fields_kept(self):
        r=G.parse_private_console(SAFE)
        self.assertEqual(r["PCI_DEVICES_COUNT"],"0")
        self.assertEqual(r["BOARD_N71_S8000_PASS"],"OBSERVED")
        self.assertNotIn("device-shell-private-junk",str(r))

    def test_invalid_missing_board_rejected(self):
        with self.assertRaises(G.FieldtestUnavailable):
            G.parse_private_console(SAFE.replace(
                b"N71_WLAN_FIELDTEST_BOARD_N71_S8000_PASS",b"NOT_AN_N71_BOARD"))

    def test_invalid_missing_passive_mode_rejected(self):
        with self.assertRaises(G.FieldtestUnavailable):
            G.parse_private_console(SAFE.replace(
               b"N71_WLAN_FIELDTEST_NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS=YES",
               b"N71_WLAN_FIELDTEST_NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS=NO"))

    def test_invalid_missing_finish_rejected(self):
        with self.assertRaises(G.FieldtestUnavailable):
            G.parse_private_console(SAFE.replace(
                b"N71_WLAN_FIELDTEST_TEST_FINISHED",b"NOT_FINISHED"))

    def test_no_private_network_text_or_mac_is_returned(self):
        secret=b"SYNTHETIC_SECRET_LABEL=NOTREALTEST\nMAC=00:ab:cd:ef:10:11\n"
        data=G.parse_private_console(SAFE+secret)
        self.assertNotIn("SUPERPRIVATE",str(data))
        self.assertNotIn("00:ab:cd:ef",str(data))

    def test_only_bound_usb_interface_allowed(self):
        with self.assertRaises(G.FieldtestUnavailable):
            G.request_private_log("192.0.2.1",23)
        with self.assertRaises(G.FieldtestUnavailable):
            G.request_private_log("172.16.42.1",22)

    def test_malformed_device_field_not_forwarded(self):
        response=SAFE.replace(
            b"N71_WLAN_FIELDTEST_PCI_DEVICES_COUNT=0",
            b"N71_WLAN_FIELDTEST_PCI_DEVICES_COUNT=MY_MAC_SECRET")
        self.assertNotIn("PCI_DEVICES_COUNT",G.parse_private_console(response))

    def test_current_os_without_linux_usb_does_not_call_shell(self):
        with patch.object(G,"exact_usb_linux_gadget_present",return_value=False),\
             patch.object(G,"request_private_log") as req:
            self.assertEqual(G.main([]),2)
            req.assert_not_called()

    def test_generated_diagnostic_never_infers_wifi_from_usb(self):
        src=SOURCE.read_text()
        self.assertIn("USB_GADGET_CONNECTION_IS_NOT_NATIVE_WIFI=YES",src)
        self.assertIn("DIRECT_WLAN_ASSOCIATION_AND_DHCP_PROVEN=NO",src)
        self.assertIn("PHYSICAL_DART1_DMA_REQUESTER_SID_PROVEN=NO",src)

if __name__=="__main__":unittest.main()
