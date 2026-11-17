#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe real local command output from a LAN terminal. HTTP is read-only."""
import argparse
import datetime
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ANSI = re.compile(r"\x1b(?:\][^\x07]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])")
SECRET = re.compile(r"(?i)(authorization\s*:\s*bearer\s+|(?:api[_-]?key|access[_-]?token|password)\s*[=:]\s*)([^\s,;]+)")

def clean(value):
    value = ANSI.sub("", value)
    value = "".join(c for c in value if c.isprintable() or c in "\n\r\t")
    return SECRET.sub(r"\1[REDACTED]", value)

def timestamp():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def private_dir(path):
    path = Path(path).expanduser().resolve()
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.chmod(0o700)
    return path

def append(state, value):
    fd = os.open(state / "activity.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(clean(value))

def run_job(state, argv):
    if not argv:
        raise ValueError("A local command is required")
    append(state, f"\n[{timestamp()}] $ {shlex.join(argv)}\n")
    with subprocess.Popen(argv, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1) as process:
        for line in process.stdout:
            safe = clean(line)
            append(state, safe)
            sys.stdout.write(safe)
            sys.stdout.flush()
        code = process.wait()
    append(state, f"[{timestamp()}] exit={code}\n")
    return code

class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, address, state, token, network):
        self.state, self.token = state, token
        self.network = ipaddress.ip_network(network)
        self.stop_event = threading.Event()
        self.viewers = threading.BoundedSemaphore(8)
        super().__init__(address, ConsoleHandler)

class ConsoleHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_POST(self):
        self.send_error(405, "Read-only monitor")
    do_PUT = do_DELETE = do_PATCH = do_POST
    def do_GET(self):
        peer = ipaddress.ip_address(self.client_address[0])
        expected = "/view/" + self.server.token
        if peer not in self.server.network:
            self.send_error(403)
            return
        if not hmac.compare_digest(urlsplit(self.path).path, expected):
            self.send_error(404)
            return
        if not self.server.viewers.acquire(blocking=False):
            self.send_error(503)
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(b"CYBERDECK / DELL - REAL COMMAND OUTPUT - READ ONLY\n")
            self.wfile.flush()
            logfile = self.server.state / "activity.log"
            offset = max(0, logfile.stat().st_size - 131072) if logfile.exists() else 0
            heartbeat = time.monotonic()
            while not self.server.stop_event.is_set():
                if logfile.exists():
                    if logfile.stat().st_size < offset:
                        offset = 0
                    with logfile.open("rb") as stream:
                        stream.seek(offset)
                        data = stream.read(32768)
                        offset = stream.tell()
                    if data:
                        self.wfile.write(data)
                        self.wfile.flush()
                        heartbeat = time.monotonic()
                        continue
                if time.monotonic() - heartbeat >= 20:
                    self.wfile.write(f"\n[{timestamp()}] Monitor connesso; in attesa di nuovo output.\n".encode())
                    self.wfile.flush()
                    heartbeat = time.monotonic()
                self.server.stop_event.wait(0.25)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.server.viewers.release()

def serve(state, bind, port, network):
    address = ipaddress.ip_address(bind)
    allowed = ipaddress.ip_network(network)
    if not address.is_private or address.is_unspecified or address not in allowed or not allowed.is_private:
        raise ValueError("An explicit private LAN interface and subnet are required")
    tokenfile = state / "view_token"
    if tokenfile.exists():
        token = tokenfile.read_text().strip()
    else:
        token = secrets.token_hex(24)
        fd = os.open(tokenfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(token + "\n")
    if not re.fullmatch(r"[0-9a-f]{48}", token):
        raise ValueError("Invalid view token file")
    server = ConsoleServer((bind, port), state, token, network)
    config = {"pid": os.getpid(), "url": f"http://{bind}:{server.server_port}/view/{token}",
              "network": network}
    fd = os.open(state / "connection.json", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(config, stream)
    print("LOCAL_READONLY_MONITOR_READY", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.stop_event.set()
        server.server_close()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--bind")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--network")
    ap.add_argument("mode", choices=("serve", "run", "note"))
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    state = private_dir(a.state_dir)
    argv = a.argv[1:] if a.argv[:1] == ["--"] else a.argv
    if a.mode == "serve":
        if not a.bind or not a.network:
            ap.error("serve requires --bind and --network")
        serve(state, a.bind, a.port, a.network)
        return 0
    if a.mode == "run":
        return run_job(state, argv)
    append(state, f"\n[{timestamp()}] NOTE: {' '.join(argv)}\n")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
