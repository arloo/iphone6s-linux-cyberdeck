#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect strictly sanitized N71 read-only WLAN baseline from RAM-Linux USB.

Only after owner physically entered DFU and booted the approved private,
RAM-only m1n1 Linux candidate. Connects to local USB tether shell
172.16.42.1:23, NOT Wi-Fi. Does not invoke a bootloader, radio or MMIO
command; reads one /run log on the phone. Prints ONLY allowlisted metrics.
"""
from __future__ import annotations
import argparse,re,socket,subprocess,sys,time

DEFAULT_USB_LINUX_SHELL="172.16.42.1"
LINUX_USB_ID="05ac:4142"
DONE=b"__N71_READONLY_DIAGNOSTIC_DONE__"

ALLOWED={
    "BOARD_N71_S8000_PASS",
    "ACCESS_MODE_SYSFS_PROCFS_METADATA_ONLY",
    "PCIE_CORE_PRESENT",
    "PCI_DEVICES_COUNT",
    "IOMMU_GROUPS_COUNT",
    "N71_PCIE_PORT1_PLATFORM_NODES_MATCHED",
    "N71_DART1_PLATFORM_NODES_MATCHED",
    "WLAN_INTERFACES_COUNT",
    "WLAN_NETWORK_ASSOCIATION_NOT_TESTED",
    "WLAN_NATIVE_NOT_ENUMERATED_OR_NOT_NAMED",
    "NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS",
    "TEST_FINISHED",
}
FIELD=re.compile(r"^N71_WLAN_FIELDTEST_([A-Z0-9_]+)(?:=([A-Z0-9]+))?$")

class FieldtestUnavailable(Exception):
    pass

def parse_private_console(raw:bytes):
    # No arbitrary console or device output is returned to caller.
    try: text=raw.decode("utf-8","replace")
    except Exception as exc:
        raise FieldtestUnavailable("Malformed Linux shell response") from exc
    data={}
    for line in text.replace("\r","\n").split("\n"):
        match=FIELD.fullmatch(line.strip())
        if match and match.group(1) in ALLOWED:
            key,value=match.group(1),match.group(2)
            if value is not None and not (
                    value.isdecimal() or value in ("YES","NO")):
                continue
            data[key]=value if value is not None else "OBSERVED"
    if not {"BOARD_N71_S8000_PASS","TEST_FINISHED",
            "NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS"} <= data.keys():
        raise FieldtestUnavailable("N71 Linux read-only fieldtest not verified")
    if data["NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS"]!="YES":
        raise FieldtestUnavailable("Phone did not certify passive mode")
    if data.get("ACCESS_MODE_SYSFS_PROCFS_METADATA_ONLY")!="OBSERVED":
        raise FieldtestUnavailable("Linux passive metadata mode not verified")
    return data

def exact_usb_linux_gadget_present():
    result=subprocess.run(["lsusb","-d",LINUX_USB_ID],
                          capture_output=True,text=True,timeout=5)
    return result.returncode==0 and LINUX_USB_ID in result.stdout

def request_private_log(host=DEFAULT_USB_LINUX_SHELL,port=23):
    if host!=DEFAULT_USB_LINUX_SHELL or port!=23:
        raise FieldtestUnavailable("Only verified local USB gadget shell allowed")
    try:
        with socket.create_connection((host,port),timeout=4) as s:
            s.settimeout(1.0)
            time.sleep(.15)
            try:s.recv(8192)
            except socket.timeout:pass
            s.sendall(
                b"cat /run/n71_wlan_readonly_fieldtest.log; "
                b"echo __N71_READONLY_DIAGNOSTIC_DONE__\n")
            data=bytearray()
            deadline=time.monotonic()+7
            while time.monotonic()<deadline and len(data)<65536:
                try:chunk=s.recv(8192)
                except socket.timeout:continue
                if not chunk:break
                data+=chunk
                if DONE in data:break
            if DONE not in data:
                raise FieldtestUnavailable("Bounded read-only console capture incomplete")
            return parse_private_console(bytes(data))
    except (OSError,TimeoutError) as exc:
        raise FieldtestUnavailable("Linux USB shell not reachable") from exc

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    try:
        if not exact_usb_linux_gadget_present():
            raise FieldtestUnavailable("Phone not in RAM-only Linux USB mode")
        data=request_private_log()
    except FieldtestUnavailable:
        print("N71_WLAN_LINUX_RAM_ONLY_READONLY_FIELDTEST_NOT_YET_AVAILABLE",
              file=sys.stderr)
        return 2
    print("N71_WLAN_LINUX_RAM_ONLY_READONLY_FIELDTEST_PHYSICAL_PASS")
    for key in sorted(data):
        print("N71_FIELDTEST_"+key+"="+data[key])
    print("USB_GADGET_CONNECTION_IS_NOT_NATIVE_WIFI=YES")
    print("DIRECT_WLAN_ASSOCIATION_AND_DHCP_PROVEN=NO")
    print("PHYSICAL_DART1_DMA_REQUESTER_SID_PROVEN=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
