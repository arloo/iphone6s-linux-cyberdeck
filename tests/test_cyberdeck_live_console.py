# SPDX-License-Identifier: MIT
"""HTTP viewers must have no command-input path; output must be genuine."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("cyberdeck_live_console",ROOT/"tools/cyberdeck_live_console.py")
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class LiveConsoleTests(unittest.TestCase):
    def test_http_auth_readonly_and_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=M.private_dir(tmp);token="a"*48
            server=M.ConsoleServer(("127.0.0.1",0),state,token,"127.0.0.0/8")
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base="http://127.0.0.1:"+str(server.server_port)
            try:
                for path,method,status in [("/view/wrong","GET",404),("/view/"+token,"POST",405),("/exec","GET",404)]:
                    with self.subTest(path=path,method=method),self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(urllib.request.Request(base+path,method=method),timeout=3)
                    self.assertEqual(caught.exception.code,status)
                    caught.exception.close()
                with urllib.request.urlopen(base+"/view/"+token,timeout=3) as response:
                    self.assertIn(b"READ ONLY",response.readline())
                    M.append(state,"ACTUAL_STREAM_EVENT\n")
                    self.assertEqual(response.readline(),b"ACTUAL_STREAM_EVENT\n")
            finally:
                server.stop_event.set();server.shutdown();server.server_close();thread.join(2)
    def test_real_child_output_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=M.private_dir(tmp)
            self.assertEqual(M.run_job(state,[sys.executable,"-c","print('ACTUAL_CHILD_OUTPUT');raise SystemExit(7)"]),7)
            text=(state/"activity.log").read_text()
            self.assertIn("ACTUAL_CHILD_OUTPUT\n",text)
            self.assertIn("exit=7",text)
    def test_terminal_controls_and_named_secrets_filtered(self):
        self.assertEqual(M.clean("\x1b[31mhello\x1b[0m"),"hello")
        self.assertEqual(M.clean("Authorization: Bearer local-demo-value"),"Authorization: Bearer [REDACTED]")
        self.assertEqual(M.clean("api_key=local-demo-value"),"api_key=[REDACTED]")
if __name__=="__main__":unittest.main()
