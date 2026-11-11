"""Offline mock of guarded early-boot N71 Z2 setup.

The mock does NOT send real SPI commands. It simulates sysfs state gates.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1] / "scripts/n71_z2_autostart.sh"

class TestN71Autostart(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.sysfs=self.dir/"spi0.0"
        self.sysfs.mkdir()
        self.board=self.dir/"compatible"
        self.board.write_bytes(b"apple,n71\x00apple,s8000\x00")
        self.marker=self.dir/"run/attempted"
        self.marker.parent.mkdir()
        self.state_path=self.sysfs/"runtime_state"
        self.state_path.write_text("unused; served by mock cat\n")
        self.controls=("runtime_wake","runtime_d9","runtime_d9_fetch",
                       "runtime_type1_setup","runtime_af")
        for name in self.controls:
            (self.sysfs/name).write_text("")
        self.bin=self.dir/"fakebin"
        self.bin.mkdir()
        stub=self.bin/"cat"
        stub.write_text("""#!/bin/sh
if [ "$1" = "$N71_TEST_STATE_PATH" ]; then
    n=$(/bin/cat "$N71_TEST_COUNTER")
    n=$((n + 1))
    echo "$n" > "$N71_TEST_COUNTER"
    /bin/sed -n "$n""p" "$N71_TEST_STATES"
else
    exec /bin/cat "$@"
fi
""")
        stub.chmod(0o755)
        self.counter=self.dir/"counter"
        self.counter.write_text("0")
        self.states=self.dir/"states"
        state={
            "booted":1,"wake_attempted":0,"wake_rc":-11,
            "d9_attempts":0,"d9_rc":-11,"d9_reply":"0x00",
            "d9_status":0,"d9_size":0,"d9_checksum_ok":0,
            "d9_fetch_attempted":0,"d9_fetch_mode":0,
            "d9_fetch_rc":-11,"d9_fetch_first":"0x00",
            "d9_fetch_checksum_ok":0,"d9_geometry_plausible":0,
            "type1_attempted":0,"type1_rc":-11,
            "af_attempted":0,"af_rc":-11,"af_reply":"0x00",
            "af_checksum_ok":0
        }
        self.simulated=[dict(state)]
        for updates in (
            {"wake_attempted":1,"wake_rc":0},
            {"d9_attempts":1,"d9_rc":0,"d9_reply":"0xe1","d9_checksum_ok":1},
            {"d9_attempts":2,"d9_reply":"0xe3","d9_status":0,
             "d9_size":16,"d9_checksum_ok":1},
            {"d9_fetch_attempted":1,"d9_fetch_mode":1,"d9_fetch_rc":0,
             "d9_fetch_first":"0xe7","d9_fetch_checksum_ok":1,
             "d9_geometry_plausible":1},
            {"type1_attempted":1,"type1_rc":0},
            {"af_attempted":1,"af_rc":0,"af_reply":"0xe1",
             "af_checksum_ok":1}
        ):
            state.update(updates)
            self.simulated.append(dict(state))
        self.env=os.environ.copy()
        self.env.update({
            "PATH":str(self.bin)+":"+os.environ.get("PATH","/usr/bin:/bin"),
            "N71_TEST_STATE_PATH":str(self.state_path),
            "N71_TEST_COUNTER":str(self.counter),
            "N71_TEST_STATES":str(self.states),
        })
        self.fixture_script=self.dir/"init.sh"
        text=SRC.read_text()
        for a,b in (
            ("Z2_DIR=/sys/bus/spi/devices/spi0.0","Z2_DIR="+str(self.sysfs)),
            ("BOARD_FILE=/proc/device-tree/compatible","BOARD_FILE="+str(self.board)),
            ("MARKER=/run/n71_z2_auto_attempted","MARKER="+str(self.marker)),
        ):
            assert a in text
            text=text.replace(a,b,1)
        self.fixture_script.write_text(text)

    def run_mock(self):
        self.states.write_text(
            "".join(" ".join(f"{k}={v}" for k,v in state.items())+"\n"
                    for state in self.simulated)
        )
        return subprocess.run(["/bin/sh",str(self.fixture_script)],
                              env=self.env,capture_output=True,text=True,
                              timeout=5,check=False)

    def test_successful_mock_protocol_with_exact_gates(self):
        p=self.run_mock()
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn("COMPLETE:PROTOCOL_READY",p.stdout)
        self.assertEqual(self.counter.read_text().strip(),"7")
        self.assertTrue(self.marker.exists())
        for control in self.controls:
            self.assertEqual((self.sysfs/control).read_text(),"1")

    def test_unexpected_d9_size_fails_before_long_report(self):
        self.simulated[3]["d9_size"]=32
        p=self.run_mock()
        self.assertNotEqual(p.returncode,0)
        self.assertIn("FAIL:unexpected_protocol_state",p.stdout)
        self.assertEqual((self.sysfs/"runtime_d9_fetch").read_text(),"")
        self.assertEqual((self.sysfs/"runtime_af").read_text(),"")

    def test_incorrect_panel_geometry_fails_before_type1(self):
        self.simulated[4]["d9_geometry_plausible"]=0
        p=self.run_mock()
        self.assertNotEqual(p.returncode,0)
        self.assertEqual((self.sysfs/"runtime_type1_setup").read_text(),"")
        self.assertEqual((self.sysfs/"runtime_af").read_text(),"")

    def test_non_n71_board_never_sends_spi(self):
        self.board.write_bytes(b"apple,n71m\x00apple,s8003\x00")
        p=self.run_mock()
        self.assertEqual(p.returncode,0)
        self.assertIn("SKIP:not_N71",p.stdout)
        self.assertFalse(self.marker.exists())
        self.assertEqual((self.sysfs/"runtime_wake").read_text(),"")

    def test_attempt_marker_fails_closed(self):
        self.marker.write_text("")
        p=self.run_mock()
        self.assertNotEqual(p.returncode,0)
        self.assertIn("FAIL:already_attempted",p.stdout)
        self.assertEqual((self.sysfs/"runtime_wake").read_text(),"")

if __name__=="__main__":
    unittest.main()
