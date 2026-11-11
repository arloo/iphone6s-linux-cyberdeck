"""Offline fail-closed checks for the native N71 Wi-Fi acceptance script."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/n71_native_wifi_acceptance.sh"
class TestN71WifiGate(unittest.TestCase):
    def call(self,*args):
        return subprocess.run(["sh",str(SCRIPT),*args],
                              capture_output=True,text=True,timeout=8)
    def test_syntax(self):
        r=subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_missing_args_fails(self):
        r=self.call()
        self.assertNotEqual(r.returncode,0)
        self.assertIn("usage_iface",r.stdout)
    def test_usb_and_nonradio_rejected(self):
        for iface in ("usb0","enx1234","eth0","lo","sit0","tun0","tap0"):
            with self.subTest(iface=iface):
                r=self.call(iface,"test","192.0.2.1","192.0.2.2")
                self.assertNotEqual(r.returncode,0)
                self.assertIn("not_native_wifi",r.stdout)
    def test_shell_injection_rejected(self):
        r=self.call("wlan0;id","test","192.0.2.1","192.0.2.2")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("not_native_wifi",r.stdout)
    def test_absent_wlan_fails(self):
        r=self.call("wlan-does-not-exist","test","192.0.2.1","192.0.2.2")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("wlan_interface_absent",r.stdout)
    def test_wifi_phy_and_exact_association_required(self):
        t=SCRIPT.read_text()
        for token in ("/sys/class/net/$IFACE/phy80211",
                      "/sys/class/ieee80211", 'iw dev "$IFACE" link',
                      '"$actual_ssid" = "$SSID"',
                      'dev $IFACE', 'ping -I "$IFACE"'):
            with self.subTest(token=token):
                self.assertIn(token,t)
    def test_no_credentials_or_network_changes(self):
        t=SCRIPT.read_text()
        for bad in ("wpa_passphrase","password=","psk=",
                    "route add","ip link set","nmcli connect",
                    "rfkill unblock","sudo "):
            self.assertNotIn(bad,t)
if __name__=="__main__":
    unittest.main()
