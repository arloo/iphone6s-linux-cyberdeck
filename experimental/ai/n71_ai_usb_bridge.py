#!/usr/bin/env python3
"""Owner-only Cyberdeck AI text bridge over USB NCM. No secret on phone.

No persistent prompts/responses; OpenAI Responses store=False.
"""
import json
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT, PEER = "172.16.42.2", 18962, "172.16.42.1"
TOKEN_PATH = Path.home() / ".config/cyberdeck/ai-bridge-token"
MODEL = os.environ.get("OPENAI_CHAT_MODEL") or os.environ.get("OPENAI_BRIEF_MODEL", "gpt-4.1-mini")
INSTRUCTIONS = (
    "Sei DECK.AI, assistente del Cyberdeck ARM64. Rispondi in italiano, "
    "chiaro e pratico. Aiuta con Linux, reti e sicurezza in ambienti autorizzati. "
    "Non inventare risultati di tool o accesso ai dati privati, e non esegui comandi. "
    "Non hai accesso diretto a Gmail, Calendar o WhatsApp."
)

def load_token(path=TOKEN_PATH):
    info = path.stat(follow_symlinks=False)
    if path.is_symlink() or not path.is_file() or info.st_uid != os.getuid() or (info.st_mode & 0o077):
        raise RuntimeError("AI bridge token file has unsafe permissions")
    token = path.read_text(encoding="ascii").strip()
    if not 40 <= len(token) <= 200:
        raise RuntimeError("Invalid AI bridge token length")
    return token

def collect_reply(result):
    parts = []
    for item in result.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message": continue
        for block in item.get("content", []):
            if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    value = "\n".join(parts).strip()
    if not value: raise ValueError("Model did not return text")
    return value[:5000]

def query_openai(key, model, question, history, open_url=urllib.request.urlopen):
    input_messages = [{"role": role, "content": txt} for role,txt in history]
    input_messages.append({"role": "user", "content": question})
    body = json.dumps({"model": model, "instructions": INSTRUCTIONS,
                       "input": input_messages, "store": False,
                       "max_output_tokens": 450}, ensure_ascii=False).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses",
        data=body, headers={"Authorization": "Bearer " + key,
                            "Content-Type": "application/json"}, method="POST")
    with open_url(req, timeout=40) as resp:
        return collect_reply(json.load(resp))

class Conversation:
    def __init__(self, key, token, model=MODEL):
        self.key, self.token, self.model = key, token, model
        self.lock = threading.Lock()
        self.history = []
        self.last_active = 0.0
        self.last_request = 0.0

    def reply(self, question):
        with self.lock:
            now = time.monotonic()
            if now-self.last_request < 2:
                return 429, "Attendi un momento prima della prossima domanda."
            self.last_request = now
            if now-self.last_active > 1200:
                self.history.clear()
            self.last_active = now
            if question == "/reset":
                self.history.clear()
                return 200, "Conversazione temporanea azzerata."
            if not self.key:
                return 503, "API OpenAI non configurata sul Dell."
            try:
                answer = query_openai(self.key, self.model, question, self.history)
            except urllib.error.HTTPError as exc:
                return 502, "OpenAI HTTP " + str(exc.code) + ": verificare quota e modello."
            except (OSError, ValueError, TimeoutError):
                return 502, "AI non disponibile: verificare la connessione del Dell."
            self.history.extend([("user", question), ("assistant", answer)])
            self.history = self.history[-8:]
            return 200, answer

def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(45)

        def send_text(self, code, msg):
            data = (msg.rstrip() + "\n").encode("utf-8", "replace")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.client_address[0] != PEER or self.path != "/v1/chat":
                return self.send_text(403, "Accesso negato.")
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + state.token):
                return self.send_text(401, "Autorizzazione richiesta.")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2048:
                    return self.send_text(413, "Domanda troppo lunga o vuota.")
                question = self.rfile.read(size).decode("utf-8", errors="strict").strip()
            except (ValueError, UnicodeError):
                return self.send_text(400, "Testo non valido.")
            if not question or any(ord(ch)<32 and ch not in "\t\n" for ch in question):
                return self.send_text(400, "Testo non valido.")
            code,answer = state.reply(question)
            self.send_text(code,answer)

        def log_message(self,*args): pass
    return Handler

def main():
    state = Conversation(os.environ.get("OPENAI_API_KEY", ""), load_token())
    server = ThreadingHTTPServer((HOST, PORT), make_handler(state))
    print("N71_AI_BRIDGE_READY usb_only=true key_configured=" + str(bool(state.key)).lower(), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__ == "__main__":
    main()
