"""Offline security-policy tests for the phone-USB-only Dell Wi-Fi uplink proxy.

The tests use mocked DNS; they do not bind sockets, access the network,
start a proxy or write iPhone storage.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

TOOL=Path(__file__).resolve().parents[1]/"tools/n71_usb_wifi_uplink_proxy.py"
spec=importlib.util.spec_from_file_location("n71_usb_wifi_uplink",TOOL)
assert spec and spec.loader
M=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=M
spec.loader.exec_module(M)

def addr(ip:str,port:int=443):
    fam=socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(fam,socket.SOCK_STREAM,6,"",(ip,port))]

class TestPhoneUSBWifiUplinkPolicy(unittest.TestCase):
    def test_bind_only_on_existing_dell_usb_interface(self):
        self.assertEqual(M.BIND,"172.16.42.2")
        self.assertEqual(M.CLIENT,"172.16.42.1")

    def test_no_root_needed(self):
        self.assertGreaterEqual(M.PORT,1024)

    def test_known_public_test_domain_allowed(self):
        self.assertTrue(M.approved_host("example.com"))

    def test_small_fixed_public_allowlist(self):
        self.assertLessEqual(len(M.ALLOWED_HOSTS),12)
        for host in M.ALLOWED_HOSTS:
            self.assertTrue(M.approved_host(host))

    def test_reject_arbitrary_public_domain(self):
        self.assertFalse(M.approved_host("untrusted-source.example"))

    def test_reject_unapproved_subdomain(self):
        self.assertFalse(M.approved_host("foo.example.com"))

    def test_reject_case_confusable_host(self):
        self.assertFalse(M.approved_host("Example.com"))

    def test_reject_localhost(self):
        self.assertFalse(M.approved_host("localhost"))

    def test_reject_numeric_router_ip(self):
        self.assertFalse(M.approved_host("192.168.1.1"))

    def test_reject_cloud_metadata(self):
        self.assertFalse(M.approved_host("169.254.169.254"))

    def test_reject_dns_local_qualified(self):
        self.assertFalse(M.approved_host("host.local"))

    def test_public_dns_ipv4_accepted(self):
        with patch.object(M.socket,"getaddrinfo",return_value=addr("8.8.8.8")):
            self.assertEqual(len(M.public_ips("example.com",443)),1)

    def test_public_dns_ipv6_accepted(self):
        with patch.object(M.socket,"getaddrinfo",return_value=addr("2606:4700:4700::1111")):
            self.assertEqual(len(M.public_ips("example.com",443)),1)

    def test_dns_rebinding_with_mixed_public_private_rejected(self):
        mix=addr("8.8.8.8")+addr("192.168.1.1")
        with patch.object(M.socket,"getaddrinfo",return_value=mix):
            with self.assertRaises(M.StrictProxyError):
                M.public_ips("example.com",443)

    def test_private_network_resolution_rejected(self):
        for ip in ("127.0.0.1","192.168.1.1","10.0.0.12",
                   "169.254.169.254","172.16.42.1","::1",
                   "fe80::1","fc00::1","0.0.0.0"):
            with self.subTest(ip=ip):
                with patch.object(M.socket,"getaddrinfo",return_value=addr(ip)):
                    with self.assertRaises(M.StrictProxyError):
                        M.public_ips("example.com",443)

    def test_bad_upstream_port_rejected(self):
        with self.assertRaises(M.StrictProxyError):
            M.public_ips("example.com",22)

    def test_unknown_domain_rejected_before_dns(self):
        with patch.object(M.socket,"getaddrinfo") as resolver:
            with self.assertRaises(M.StrictProxyError):
                M.public_ips("not-allowed.example",443)
            resolver.assert_not_called()

    def test_no_dns_results_rejected(self):
        with patch.object(M.socket,"getaddrinfo",return_value=[]):
            with self.assertRaises(M.StrictProxyError):
                M.public_ips("example.com",443)

    def test_public_host_identity_and_local_server_no_authorization(self):
        probe=object.__new__(M.USBProxy)
        probe.client_address=("172.16.42.2",10000)
        record=[]
        probe.reply=lambda status,body:record.append((status,body))
        self.assertFalse(probe.allowed_client())
        self.assertEqual(record,[(403,b"PHONE_ONLY\n")])
        probe.client_address=(M.CLIENT,10000)
        self.assertTrue(probe.allowed_client())

    def test_unsupported_post_is_explicitly_rejected(self):
        p=object.__new__(M.USBProxy)
        p.client_address=(M.CLIENT,10000)
        record=[]
        p.reply=lambda status,body:record.append((status,body))
        p.do_POST()
        self.assertEqual(record,[(405,b"READ_ONLY_PROXY\n")])

    def test_server_never_forwards_inbound_headers_or_credentials(self):
        source=TOOL.read_text()
        self.assertIn('"User-Agent":"N71-USB-uplink-verify/0.1"',source)
        self.assertIn('or parsed.username or parsed.password:',source)
        self.assertNotIn("self.headers.items()",source)
        self.assertNotIn('self.headers["Authorization"]',source)
        self.assertNotIn("logging.basicConfig",source)

    def test_tls_only_for_public_upstream_request(self):
        source=TOOL.read_text()
        self.assertIn('target=urlunsplit(("https",parsed.hostname,',source)
        self.assertIn("NoRedirect",source)
        self.assertIn('allowed_port=80 if parsed.scheme=="http" else 443',source)
        self.assertIn('public_ips(parsed.hostname,443)',source)

    def test_connect_only_443_for_approved_host(self):
        source=TOOL.read_text()
        self.assertIn('port!="443" or not approved_host(host)',source)
        self.assertIn("MAX_CONNECT_BYTES",source)

    def test_no_kernel_or_iphone_modification(self):
        source=TOOL.read_text()
        for forbidden in ("sudo ","iptables","nft add","sysctl -w","modprobe",
                          "insmod","devmem","writel","systemctl","dd if=",
                          "flash_erase","/dev/disk","wifi_scan"):
            self.assertNotIn(forbidden,source)

if __name__=="__main__":
    unittest.main()
