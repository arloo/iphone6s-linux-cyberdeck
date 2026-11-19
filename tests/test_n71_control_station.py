"""Offline contract tests for read-only LAN Cyberdeck Control Station."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("n71_control_station",ROOT/"tools/n71_control_station.py")
station=importlib.util.module_from_spec(spec)
spec.loader.exec_module(station)

class ControlStationTests(unittest.TestCase):
    def test_safe_defaults_and_no_public_host_specific_ip(self):
        s=(ROOT/"tools/n71_control_station.py").read_text()
        self.assertNotIn("192.168.1.",s)
        self.assertIn('os.environ.get("N71_HOST_IP", "127.0.0.1")',s)
        self.assertIn('os.environ.get("N71_MINT_IP", "")',s)
        self.assertIn("ALLOWED",s)
        self.assertNotIn("subprocess.run(self.path",s)
        self.assertNotIn("subprocess.Popen(self.path",s)
        self.assertIn("return self.answer(405",s)

    def test_access_list_denies_unapproved_client(self):
        obj=station.Dashboard.__new__(station.Dashboard)
        obj.client_address=("192.0.2.123",4000)
        obj.path="/api/status"
        results=[]
        obj.answer=lambda code,ctype,payload: results.append((code,payload))
        obj.do_GET()
        self.assertEqual(results,[(403,b"Forbidden")])

    def test_debian_handoff_never_exposes_public_source_secrets(self):
        source=(ROOT/"tools/n71_control_station.py").read_text()
        self.assertNotIn("3XiSMxz6oUo8uIyXDFp1GpLqy",source)
        self.assertNotIn("su -c '/bin/bash",source)
        self.assertIn("DEBIAN_HANDOFF",source)

    def test_usb_page_only_renders_owner_local_command(self):
        obj=station.Dashboard.__new__(station.Dashboard)
        obj.client_address=("127.0.0.1",4000)
        obj.path="/usb"
        results=[]
        obj.answer=lambda code,ctype,payload: results.append((code,ctype,payload))
        obj.do_GET()
        self.assertEqual(results[0][0],200)
        text=results[0][2].decode()
        self.assertIn("Copia comando",text)
        self.assertIn("--write",text)
        self.assertIn("DEBIAN13_7_INSTALLER_USB_SUCCESS",text)
        self.assertNotIn("fetch(",text)
        self.assertNotIn("WebSocket",text)

    def test_unknown_or_mutating_route_refused(self):
        obj=station.Dashboard.__new__(station.Dashboard)
        obj.client_address=("127.0.0.1",4000)
        results=[]
        obj.answer=lambda code,ctype,payload: results.append((code,payload))
        obj.path="/private/secret"
        obj.do_GET()
        obj.path="/api/status"
        obj.do_POST()
        obj.do_PUT()
        obj.do_DELETE()
        self.assertEqual([item[0] for item in results],[404,405,405,405])

    def test_public_payload_no_shell_or_client_secrets(self):
        self.assertNotIn("WebSocket",station.PAGE)
        for forbidden in ("/bin/bash", "exec(", "document.cookie", "eval(",
                          "github_token", "private_key", "SerialNumber:"):
            self.assertNotIn(forbidden,station.PAGE)

    def test_no_apple_usb_does_not_claim_charging(self):
        with patch.object(station,"run",return_value=""):
            x=station.device_state()
        self.assertEqual(x["state"],"ESTERNO / ASSENTE")
        self.assertIn("Non rilevabile",x["battery"])

    def test_linux_pinned_live_metrics_displayed_without_secrets(self):
        values={"capacity":"97","temp_tenths":"321","current_uA":"-215000",
                "wlan":"1","ui":"running","charge_supervisor":"inactive"}
        with patch.object(station,"run",return_value="Bus 001 ID 05ac:4142 HoolockLinux"):
            with patch.object(station,"linux_live_status",return_value=values):
                x=station.device_state()
        self.assertEqual(x["state"],"LINUX A9")
        self.assertEqual(x["battery"],"97% · 32.1 °C · -215 mA")
        self.assertEqual(x["runtime"],"Wi-Fi attivo · UI attiva")
        self.assertNotIn("wifi_ip",x)

    def test_linux_ssh_failure_does_not_invent_battery(self):
        with patch.object(station,"run",return_value="Bus 001 ID 05ac:4142 HoolockLinux"):
            with patch.object(station,"linux_live_status",side_effect=RuntimeError("pin mismatch")):
                x=station.device_state()
        self.assertTrue(x["linux_usb"])
        self.assertEqual(x["battery"],"Non rilevabile via USB")
        self.assertNotIn("runtime",x)

    def test_linux_out_of_range_metrics_fail_display(self):
        values={"capacity":"101","temp_tenths":"320","current_uA":"-200000",
                "wlan":"1","ui":"running","charge_supervisor":"running"}
        with patch.object(station,"run",return_value="Bus 001 ID 05ac:4142 HoolockLinux"):
            with patch.object(station,"linux_live_status",return_value=values):
                x=station.device_state()
        self.assertEqual(x["battery"],"Non rilevabile via USB")

    def test_ios_battery_reports_only_valid_paired_percentage(self):
        with patch.object(station,"run",side_effect=[
            "Bus 001 Device 008: ID 05ac:12a8 Apple iPhone",
            "BatteryCurrentCapacity: 100\nBatteryIsCharging: true\nExternalConnected: true"
        ]):
            x=station.device_state()
        self.assertEqual(x["state"],"iOS")
        self.assertEqual(x["battery"],"100% · in carica")

    def test_ios_battery_malformed_is_unknown(self):
        with patch.object(station,"run",side_effect=[
            "Bus 001 Device 008: ID 05ac:12a8 Apple iPhone",
            "BatteryCurrentCapacity: 101\nBatteryIsCharging: true"
        ]):
            x=station.device_state()
        self.assertEqual(x["battery"],"Non rilevabile via USB")

    def test_unknown_apple_mode_does_not_invent_linux(self):
        with patch.object(station,"run",return_value="Bus 001 Device 005: ID 05ac:12a8 Apple Inc"):
            x=station.device_state()
        self.assertEqual(x["state"],"iOS")
        self.assertFalse(x["linux_usb"])

if __name__=="__main__":
    unittest.main()
