"""Offline regression tests for the USB-only N71 AI companion bridge."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / "experimental/ai/n71_ai_usb_bridge.py"
spec = importlib.util.spec_from_file_location("n71_ai_bridge", SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class DummyResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class BridgeTests(unittest.TestCase):
    def test_response_text_parsing(self):
        obj = {"output":[{"type":"reasoning","summary":[]},
                         {"type":"message","content":[{"type":"output_text","text":"Ciao, Cyberdeck!"}]}]}
        self.assertEqual(bridge.collect_reply(obj), "Ciao, Cyberdeck!")
        with self.assertRaises(ValueError):
            bridge.collect_reply({"output":[]})

    def test_no_key_ever_placed_in_model_input_or_phone(self):
        observed={}
        def fake_urlopen(req,timeout):
            observed["url"]=req.full_url
            observed["body"]=json.loads(req.data)
            observed["authorization"]=req.get_header("Authorization")
            return DummyResponse(json.dumps({"output":[{"type":"message","content":[
                {"type":"output_text","text":"OK"}]}]}).encode())
        result=bridge.query_openai("LOCAL_SECRET","gpt-4.1-mini","What is wlan0?",
                                   [("user","Hi"),("assistant","Hello")],fake_urlopen)
        self.assertEqual(result,"OK")
        self.assertEqual(observed["url"],"https://api.openai.com/v1/responses")
        self.assertEqual(observed["authorization"],"Bearer LOCAL_SECRET")
        self.assertFalse(observed["body"]["store"])
        self.assertEqual(len(observed["body"]["input"]),3)
        self.assertNotIn("LOCAL_SECRET", json.dumps(observed["body"]))

    def test_no_openai_key_fails_closed(self):
        state=bridge.Conversation("","TEST_TOKEN")
        code,msg=state.reply("Ciao")
        self.assertEqual(code,503)
        self.assertIn("non configurata",msg)

    def test_reset_has_no_persistent_log(self):
        state=bridge.Conversation("","TEST_TOKEN")
        state.history=[("user","private"),("assistant","reply")]
        code,msg=state.reply("/reset")
        self.assertEqual(code,200)
        self.assertEqual(state.history,[])
        self.assertIn("azzerata",msg)

    def test_token_file_security(self):
        with tempfile.TemporaryDirectory() as tmp:
            token=Path(tmp)/"token"
            token.write_text("a"*60)
            token.chmod(0o600)
            self.assertEqual(bridge.load_token(token),"a"*60)
            token.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,"unsafe"):
                bridge.load_token(token)

    def test_phone_client_never_uses_api_key_or_cloud_domain(self):
        client=(HERE/"experimental/ai/n71-ai-phone.sh").read_text()
        self.assertIn("172.16.42.2:18962",client)
        self.assertIn("--post-file",client)
        self.assertIn("ai-bridge-token",client)
        self.assertNotIn("api.openai.com",client)
        self.assertNotIn("sk-",client)

    def test_bridge_confined_to_usb_and_openai_memory_only(self):
        code=SOURCE.read_text()
        self.assertIn('HOST, PORT, PEER = "172.16.42.2", 18962, "172.16.42.1"',code)
        self.assertIn('"store": False',code)
        self.assertIn("compare_digest",code)
        self.assertIn("self.last_active > 1200",code)


if __name__=="__main__":
    unittest.main()
