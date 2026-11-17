"""Offline safety and UI navigation contracts for KALI/TODAY/AI."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
KALI=ROOT/"experimental/kali/n71-kali-phone.sh"
UI=ROOT/"examples/cyberdeck-shell/cyberdeck-shell.c"
DOC=ROOT/"docs/N71_THREE_PILLARS_KALI_TODAY_AI_2026_11_17.md"

class ThreePillars(unittest.TestCase):
    def run_kali(self,*args):
        return subprocess.run(["sh",str(KALI),*args],capture_output=True,text=True,timeout=5)

    def test_kali_help_discloses_limits(self):
        result=self.run_kali("help")
        self.assertEqual(result.returncode,0)
        self.assertIn("full Kali",result.stdout)
        self.assertIn("authorized",result.stdout)
        self.assertIn("NOT ready",result.stdout)

    def test_kali_rejects_invalid_host_without_network(self):
        for value in ["", "../invalid", ";id", "foo bar"]:
            result=self.run_kali("ping",value)
            self.assertEqual(result.returncode,3)

    def test_kali_rejects_invalid_port_without_network(self):
        for value in ["0","65536","-1","not-a-port"]:
            result=self.run_kali("port","127.0.0.1",value)
            self.assertEqual(result.returncode,3)

    def test_kali_rejects_unbounded_passive_capture(self):
        for value in ["0","51","999","words"]:
            result=self.run_kali("capture",value)
            self.assertEqual(result.returncode,3)

    def test_six_tabs_and_ai_touch_keyboard(self):
        code=UI.read_text()
        self.assertIn('{"HOME","TERM","SYS","KALI","TODAY","AI"}',code)
        self.assertIn("for(int i=0;i<6;i++)button(",code)
        self.assertIn('key_send("/usr/bin/n71-ai --chat',code)
        self.assertIn("else if(page==5)",code)
        self.assertIn('"/reset',code)
        self.assertIn('"/exit',code)
        self.assertIn("keyboard_draw();",code)

    def test_kali_buttons_run_actual_phone_commands(self):
        code=UI.read_text()
        self.assertIn('key_send("n71-kali help',code)
        self.assertIn('key_send("n71-kali network',code)
        self.assertNotIn('KALI ARM64 PACKAGES: PLANNED',code)

    def test_no_false_persistent_install_or_usb_c_claim(self):
        doc=DOC.read_text()
        self.assertIn("**not yet been boot-tested",doc)
        self.assertIn("Lightning",doc)
        self.assertIn("not yet a Kali distribution",doc)
        self.assertIn("Never",doc)

if __name__=="__main__":
    unittest.main()
