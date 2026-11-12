#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sanitized physical N71 RAM-Linux port1 *descriptor-only* safety gate.

No writes to the iPhone, its sysfs, NAND, registers, PCIe or DART.
Uses exclusively the owner-approved USB gadget shell (172.16.42.1:23).
This intentionally FAILS if a real driver, PCIe endpoint or IOMMU group
appears, because that would exceed the scope of this descriptor-only test.

This is NOT proof of a native BCM4350 WLAN link, DHCP, or DART requester SID.
"""
from __future__ import annotations

import re
import socket
import struct
import subprocess
import sys
import time

USB_GADGET="05ac:4142"
USB_SHELL="172.16.42.1"
PORT=23
BEGIN=b"__N71_PORT1_DESCRIPTOR_BEGIN__\r\n"
END=b"__N71_PORT1_DESCRIPTOR_END__\r\n"
EXPECTED_REGS=(
    (0x602000000,0x4000),
    (0x602004000,0x4000),
    (0x602008000,0x4000),
)
SCRIPT=(
    "echo __N71_PORT1_DESCRIPTOR_BEGIN__",
    "D=/sys/firmware/devicetree/base/soc/pcie-port1-preflight@602000000",
    'test -d "$D" && echo N71_PORT1_META_OF_NODE=YES || echo N71_PORT1_META_OF_NODE=NO',
    'printf "N71_PORT1_META_COMPAT="; tr "\\000" " " < "$D/compatible"; echo',
    'printf "N71_PORT1_META_STATUS="; tr "\\000" " " < "$D/status"; echo',
    'printf "N71_PORT1_META_REG_NAMES="; tr "\\000" " " < "$D/reg-names"; echo',
    'printf "N71_PORT1_META_REG_HEX="; od -An -tx1 "$D/reg" | tr -d " \\n"; echo',
    'test -e "$D/research,hardware-activation-blocked" && echo N71_PORT1_META_HW_BLOCK_FLAG=YES || echo N71_PORT1_META_HW_BLOCK_FLAG=NO',
    'P=/sys/bus/platform/devices/602000000.pcie-port1-preflight',
    'test -d "$P" && echo N71_PORT1_META_PLATFORM_DEVICE=YES || echo N71_PORT1_META_PLATFORM_DEVICE=NO',
    'test -L "$P/driver" && echo N71_PORT1_META_DRIVER_BOUND=YES || echo N71_PORT1_META_DRIVER_BOUND=NO',
    'echo N71_PORT1_META_PLATFORM_MATCHES=$(find /sys/bus/platform/devices -mindepth 1 -maxdepth 1 -name "*pcie-port1*" | wc -l)',
    'echo N71_PORT1_META_PCI_DEVICES=$(find /sys/bus/pci/devices -mindepth 1 -maxdepth 1 | wc -l)',
    'echo N71_PORT1_META_IOMMU_GROUPS=$(find /sys/kernel/iommu_groups -mindepth 1 -maxdepth 1 | wc -l)',
    'echo N71_PORT1_META_WLAN_NETIF=$(find /sys/class/net -mindepth 1 -maxdepth 1 -name "wl*" | wc -l)',
    'grep -q "COMPLETE:PROTOCOL_READY" /run/n71_z2_autostart.log && echo N71_PORT1_META_TOUCH_PROTOCOL_READY=YES || echo N71_PORT1_META_TOUCH_PROTOCOL_READY=NO',
    "echo __N71_PORT1_DESCRIPTOR_END__",
)
FIELD=re.compile(r"^N71_PORT1_META_([A-Z_]+)=(.*)$")
FIELDS={
 "OF_NODE","COMPAT","STATUS","REG_NAMES","REG_HEX","HW_BLOCK_FLAG",
 "PLATFORM_DEVICE","DRIVER_BOUND","PLATFORM_MATCHES","PCI_DEVICES",
 "IOMMU_GROUPS","WLAN_NETIF","TOUCH_PROTOCOL_READY"
}

class DescriptorNotProven(Exception):
    pass

def validate_readonly_console(response:bytes)->dict[str,str]:
    if len(response)>65536:
        raise DescriptorNotProven("USB console output exceeds privacy limit")
    begin=response.find(BEGIN)
    finish=response.rfind(END)
    if begin<0 or finish<begin+len(BEGIN):
        raise DescriptorNotProven("USB console proof markers absent")
    text=response[begin+len(BEGIN):finish].decode("utf-8","replace")
    text=re.sub(r"\x1b\[[0-9;]*m","",text)
    metrics={}
    for line in text.splitlines():
        line=line.strip()
        while line.startswith("~ #"):
            line=line[3:].strip()
        match=FIELD.fullmatch(line)
        if match is None or match.group(1) not in FIELDS:continue
        key,val=match.group(1),match.group(2).strip()
        if len(val)>256 or key in metrics:
            raise DescriptorNotProven("Unexpected or repeated field")
        metrics[key]=val
    if set(metrics)!=FIELDS:
        raise DescriptorNotProven("Required fixed fields missing: "+",".join(sorted(FIELDS-set(metrics))))
    expected={
        "OF_NODE":"YES",
        "COMPAT":"apple,s8000-pcie-research-blocked",
        "STATUS":"okay",
        "REG_NAMES":"port1-reg-a port1-reg-b dart1-reg",
        "HW_BLOCK_FLAG":"YES",
        "PLATFORM_DEVICE":"YES",
        "DRIVER_BOUND":"NO",
        "PLATFORM_MATCHES":"1",
        "PCI_DEVICES":"0",
        "IOMMU_GROUPS":"0",
        "WLAN_NETIF":"0",
        "TOUCH_PROTOCOL_READY":"YES",
    }
    for key,val in expected.items():
        if metrics.get(key)!=val:
            raise DescriptorNotProven("Descriptor-only metadata safety invariant mismatch")
    code=metrics["REG_HEX"]
    if re.fullmatch(r"[0-9a-f]{96}",code) is None:
        raise DescriptorNotProven("Unexpected port1 register bytes")
    vals=struct.unpack(">QQQQQQ",bytes.fromhex(code))
    regs=tuple((vals[i],vals[i+1]) for i in (0,2,4))
    if regs!=EXPECTED_REGS:
        raise DescriptorNotProven("Port1 and DART1 resource boundaries not proven")
    return metrics

def read_from_live_usb():
    p=subprocess.run(["lsusb","-d",USB_GADGET],capture_output=True,
                     text=True,timeout=5)
    if p.returncode or USB_GADGET not in p.stdout:
        raise DescriptorNotProven("Actual owner phone not in RAM Linux USB mode")
    try:
        with socket.create_connection((USB_SHELL,PORT),timeout=5) as sock:
            sock.settimeout(.65)
            time.sleep(.22)
            try:sock.recv(4096)
            except socket.timeout:pass
            sock.sendall(b"stty -echo\n")
            time.sleep(.2)
            try:sock.recv(4096)
            except socket.timeout:pass
            for command in SCRIPT:
                sock.sendall(command.encode()+b"\n")
                time.sleep(.045)
            data=bytearray()
            deadline=time.monotonic()+12
            while time.monotonic()<deadline and len(data)<65536:
                try:piece=sock.recv(4096)
                except socket.timeout:continue
                if not piece:break
                data+=piece
                if END in data:break
            return validate_readonly_console(bytes(data))
    except (OSError,TimeoutError) as exc:
        raise DescriptorNotProven("Owner-local Linux USB-only shell unreachable") from exc

def main():
    try:
        data=read_from_live_usb()
    except (DescriptorNotProven,subprocess.SubprocessError):
        print("N71_N71_S8000_PORT1_DESCRIPTOR_ONLY_PHYSICAL_NOT_PROVEN",
              file=sys.stderr)
        return 2
    print("N71_S8000_PORT1_DESCRIPTOR_ONLY_LIVE_PHYSICAL_PASS")
    print("N71_PORT1_APPLE_COMPATIBLE="+data["COMPAT"])
    print("N71_PORT1_DEVICE_TREE_OF_NODE_AND_PLATFORM_DEVICE=YES")
    print("N71_PORT1_THREE_EXACT_MMIO_WINDOW_DESCRIPTORS=YES")
    print("N71_PORT1_HARDWARE_ACTIVATION_BLOCKED_FLAG=YES")
    print("N71_PORT1_NO_DRIVER_BOUND=YES")
    print("N71_PORT1_NO_PCI_DEVICES_NO_IOMMU_GROUPS_NO_WLAN=YES")
    print("N71_Z2_TOUCH_INITIALIZATION_PROTOCOL_READY=YES")
    print("PCIE_DMA_DART_MMIO_RF_ACTIONS_EXECUTED_BY_THIS_PROBE=NO")
    print("NATIVE_WIFI_ASSOCIATION_AND_DHCP_PROVEN=NO")
    print("HARDWARE_BCM4350_REQUESTER_TO_DART_SID_PROVEN=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
