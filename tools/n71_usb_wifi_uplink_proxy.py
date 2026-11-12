#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N71 Dell Wi-Fi -> iPhone 6s RAM-Linux USB-only user-space HTTPS uplink.

This is NOT iPhone native WLAN: device packet transport remains 05ac:4142
USB NCM. Only the owner-controlled phone 172.16.42.1 can use this service,
which listens exclusively on the Dell USB-interface address 172.16.42.2.

HTTP proxy GET/HEAD to allowlisted public hosts are fetched by Dell as
HTTPS. HTTPS CONNECT is accepted only for port 443 and allowlisted hosts.
No arbitrary LAN targets, no local/private/loopback IPs, no file access,
no cookies or Authorization forwarding, no POST and no credential storage.
Can run without root; doesn't configure firewall, DNS or OS routing.
"""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import select
import socket
import ssl
import sys
from urllib.parse import urlsplit,urlunsplit
import urllib.error
import urllib.request

BIND="172.16.42.2"
CLIENT="172.16.42.1"
PORT=18080
ALLOWED_HOSTS=frozenset((
    "example.com",
    "www.example.com",
    "deb.debian.org",
    "security.debian.org",
    "github.com",
    "raw.githubusercontent.com",
    "pypi.org",
    "files.pythonhosted.org",
    "www.kernel.org",
    "www.gnu.org",
))
MAX_HTTP_REPLY=1<<20
MAX_CONNECT_BYTES=50<<20

class StrictProxyError(ValueError):pass

def approved_host(host:str)->bool:
    return (bool(host) and host in ALLOWED_HOSTS and
            host.isascii() and host==host.lower())

def public_ips(host:str,port:int):
    if not approved_host(host) or port not in (80,443):
        raise StrictProxyError("host not approved")
    ips=[]
    for ai in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM):
        addr=ai[4][0]
        if not ipaddress.ip_address(addr).is_global:
            raise StrictProxyError("upstream is not public")
        ips.append(ai)
    if not ips:raise StrictProxyError("missing upstream")
    return ips

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class USBProxy(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    server_version="N71-USB-only-HTTPS-uplink/0.1"
    sys_version=""
    timeout=12

    def log_message(self,format,*args):
        # Never log client URL, cookies, SSID, MAC, destination or query.
        return

    def reply(self,code,body=b""):
        self.send_response(code)
        self.send_header("Content-Type","text/plain; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Connection","close")
        self.end_headers()
        if self.command!="HEAD":
            self.wfile.write(body)
        self.close_connection=True

    def allowed_client(self):
        if self.client_address[0]!=CLIENT:
            self.reply(403,b"PHONE_ONLY\n")
            return False
        return True

    def _proxy_http(self):
        if not self.allowed_client():return
        if self.path=="/__n71_usb_uplink_health__":
            self.reply(200,b"N71_USB_UPLINK_READY_PHONE_USB_ONLY\n")
            return
        try:
            parsed=urlsplit(self.path)
            if parsed.scheme not in ("http","https") or parsed.username or parsed.password:
                raise StrictProxyError("bad proxy URL")
            if parsed.hostname is None or not approved_host(parsed.hostname):
                raise StrictProxyError("destination is not approved")
            allowed_port=80 if parsed.scheme=="http" else 443
            if parsed.port not in (None,allowed_port) or parsed.fragment:
                raise StrictProxyError("unexpected destination port")
            public_ips(parsed.hostname,443)
            target=urlunsplit(("https",parsed.hostname,
                              parsed.path or "/",parsed.query,""))
            req=urllib.request.Request(target,
                headers={"User-Agent":"N71-USB-uplink-verify/0.1"},
                method=self.command)
            # No source-request headers, cookie or auth are forwarded.
            opener=urllib.request.build_opener(NoRedirect)
            with opener.open(req,timeout=12) as response:
                data=response.read(MAX_HTTP_REPLY+1) if self.command=="GET" else b""
                if len(data)>MAX_HTTP_REPLY:
                    raise StrictProxyError("upstream response exceeds 1 MiB")
                self.send_response(response.status)
                self.send_header("Content-Length",str(len(data) if self.command=="GET" else 0))
                self.send_header("Content-Type",response.headers.get("Content-Type","application/octet-stream"))
                self.send_header("X-N71-Uplink","dell-wifi-over-usb")
                self.send_header("Cache-Control","no-store")
                self.send_header("Connection","close")
                self.end_headers()
                if self.command=="GET":self.wfile.write(data)
                self.close_connection=True
        except (OSError,ValueError,urllib.error.URLError,ssl.SSLError):
            self.reply(502,b"N71_UPLINK_FAILED_NO_FALLBACK\n")

    def do_GET(self):
        self._proxy_http()
    def do_HEAD(self):
        self._proxy_http()

    def do_CONNECT(self):
        if not self.allowed_client():return
        # Strict CONNECT host:443 -> public DNS answer, no private egress.
        sock=None
        try:
            host,sep,port=self.path.partition(":")
            if not sep or port!="443" or not approved_host(host):
                raise StrictProxyError("CONNECT blocked")
            candidates=public_ips(host,443)
            for ai in candidates:
                try:
                    sock=socket.socket(ai[0],ai[1],ai[2])
                    sock.settimeout(7)
                    sock.connect(ai[4])
                    break
                except OSError:
                    if sock:sock.close()
                    sock=None
            if sock is None:raise StrictProxyError("Public upstream unavailable")
            self.send_response(200,"Connection Established")
            self.send_header("Connection","close")
            self.end_headers()
            self.wfile.flush()
            # Raw TLS tunnel; server sees no HTTPS content. Cap bytes.
            self.connection.settimeout(None)
            sock.settimeout(None)
            count=0
            while count<MAX_CONNECT_BYTES:
                ready,_,_=select.select([self.connection,sock],[],[],20)
                if not ready:break
                for source in ready:
                    data=source.recv(16384)
                    if not data:return
                    target=sock if source is self.connection else self.connection
                    target.sendall(data)
                    count+=len(data)
            self.close_connection=True
        except (OSError,ValueError):
            if sock is None:
                self.reply(403,b"N71_TLS_TARGET_DENIED\n")
        finally:
            if sock:sock.close()
            self.close_connection=True

    def do_POST(self):
        if self.allowed_client():self.reply(405,b"READ_ONLY_PROXY\n")

class ThreadedUSBServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port",type=int,default=PORT)
    a=ap.parse_args()
    if not 1024<=a.port<65536:
        print("N71_USB_UPLINK_BAD_UNPRIVILEGED_PORT",file=sys.stderr)
        return 2
    try:
        with ThreadedUSBServer((BIND,a.port),USBProxy) as server:
            print("N71_USB_ONLY_DELL_WIFI_UPLINK_BOUND=YES",flush=True)
            print("N71_UPLINK_ONBOARD_BCM4350_WIFI_AVAILABLE=NO",flush=True)
            server.serve_forever(poll_interval=.5)
    except OSError:
        print("N71_USB_UPLINK_CANNOT_BIND_TO_APPROVED_USB_ADDRESS",
              file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
