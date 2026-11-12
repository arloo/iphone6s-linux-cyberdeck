#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only physical N71/S8000 metadata-guard execution proof over Linux USB.

A physically successful port1 metadata guard is deliberately NOT a PCIe link,
DART DMA proof, native Wi-Fi interface, or wireless network connection.
Never prints raw kernel logs, console data, MAC, serial or device identifiers.
No kernel module load/unload, reboot or on-device write is performed here.
"""
from __future__ import annotations
import re
import socket
import subprocess
import sys
import time

BEGIN=b"__N71_PORT1_GUARD_AUDIT_START__\r\n"
END=b"__N71_PORT1_GUARD_AUDIT_END__\r\n"
COMMANDS=(
    "echo __N71_PORT1_GUARD_AUDIT_START__",
    'test -d /sys/module/pcie_apple_s8000_guard && echo N71_GUARD_AUDIT_MODULE_SYS=YES || echo N71_GUARD_AUDIT_MODULE_SYS=NO',
    'grep -q "^pcie_apple_s8000_guard " /proc/modules && echo N71_GUARD_AUDIT_MODULE_PROC=YES || echo N71_GUARD_AUDIT_MODULE_PROC=NO',
    'test -L /sys/bus/platform/devices/602000000.pcie-port1-preflight/driver && echo N71_GUARD_AUDIT_DRIVER_BOUND=YES || echo N71_GUARD_AUDIT_DRIVER_BOUND=NO',
    'dmesg | grep -Fq "N71 S8000 port1/DART1 descriptor preflight passed; hardware BLOCKED" && echo N71_GUARD_AUDIT_REFUSAL_DMESG=YES || echo N71_GUARD_AUDIT_REFUSAL_DMESG=NO',
    'test -f /sys/firmware/devicetree/base/soc/pcie-port1-preflight@602000000/research,hardware-activation-blocked && echo N71_GUARD_AUDIT_HW_BLOCK_FLAG=YES || echo N71_GUARD_AUDIT_HW_BLOCK_FLAG=NO',
    'echo N71_GUARD_AUDIT_PCI_COUNT=$(find /sys/bus/pci/devices -mindepth 1 -maxdepth 1 | wc -l)',
    'echo N71_GUARD_AUDIT_IOMMU_COUNT=$(find /sys/kernel/iommu_groups -mindepth 1 -maxdepth 1 | wc -l)',
    'echo N71_GUARD_AUDIT_WLAN_COUNT=$(find /sys/class/net -mindepth 1 -maxdepth 1 -name "wl*" | wc -l)',
    'grep -q "COMPLETE:PROTOCOL_READY" /run/n71_z2_autostart.log && echo N71_GUARD_AUDIT_TOUCH_READY=YES || echo N71_GUARD_AUDIT_TOUCH_READY=NO',
    'test -d /sys/class/net/usb0 && echo N71_GUARD_AUDIT_USB_NET=YES || echo N71_GUARD_AUDIT_USB_NET=NO',
    "echo __N71_PORT1_GUARD_AUDIT_END__",
)
EXPECTED={
    "MODULE_SYS":"YES",
    "MODULE_PROC":"YES",
    "DRIVER_BOUND":"NO",
    "REFUSAL_DMESG":"YES",
    "HW_BLOCK_FLAG":"YES",
    "PCI_COUNT":"0",
    "IOMMU_COUNT":"0",
    "WLAN_COUNT":"0",
    "TOUCH_READY":"YES",
    "USB_NET":"YES",
}
PATTERN=re.compile(r"^N71_GUARD_AUDIT_([A-Z_]+)=(YES|NO|[0-9]+)$")
class PhysicalProofUnavailable(ValueError):pass

def validate_console(data:bytes)->None:
    if len(data)>65536:raise PhysicalProofUnavailable("Excessive terminal data")
    a=data.find(BEGIN)
    b=data.rfind(END)
    if a<0 or b<a+len(BEGIN):
        raise PhysicalProofUnavailable("Incomplete bounded physical telemetry")
    txt=re.sub(r"\x1b\[[0-9;]*m","",data[a+len(BEGIN):b].decode("utf8","replace"))
    found={}
    for raw in txt.splitlines():
        ln=raw.strip()
        while ln.startswith("~ #"):
            ln=ln[3:].strip()
        hit=PATTERN.fullmatch(ln)
        if hit:
            key,value=hit.groups()
            if key in found:raise PhysicalProofUnavailable("Repeated result")
            found[key]=value
    if found!=EXPECTED:raise PhysicalProofUnavailable("On-device guard or safety metric differs")

def collect_live() -> None:
    usb=subprocess.run(["lsusb","-d","05ac:4142"],check=False,
                       capture_output=True,text=True,timeout=5)
    if usb.returncode or "05ac:4142" not in usb.stdout:
        raise PhysicalProofUnavailable("N71 Linux USB gadget not present")
    with socket.create_connection(("172.16.42.1",23),timeout=5) as sock:
        sock.settimeout(.65)
        time.sleep(.18)
        try:sock.recv(4096)
        except socket.timeout:pass
        sock.sendall(b"stty -echo\n")
        time.sleep(.16)
        try:sock.recv(4096)
        except socket.timeout:pass
        for c in COMMANDS:
            sock.sendall(c.encode()+b"\n")
            time.sleep(.05)
        buf=bytearray()
        deadline=time.monotonic()+12
        while time.monotonic()<deadline and len(buf)<65536:
            try:p=sock.recv(4096)
            except socket.timeout:continue
            if not p:break
            buf+=p
            if END in buf:break
    validate_console(bytes(buf))

def main():
    try:collect_live()
    except (PhysicalProofUnavailable,OSError,TimeoutError,subprocess.SubprocessError):
        print("N71_PORT1_GUARD_PHYSICAL_PROBE_READONLY_NOT_PROVEN",file=sys.stderr)
        return 2
    print("N71_S8000_PORT1_GUARD_LOADED_AND_PROBED_PHYSICAL_PASS")
    print("N71_MODULE_KERNEL_LOADED_AND_PROBE_LOG_CONFIRMED=YES")
    print("N71_PLATFORM_DRIVER_NOT_BOUND_HARDWARE_STILL_BLOCKED=YES")
    print("N71_PCI_ENDPOINTS_IOMMU_GROUPS_NATIVE_WLAN_ALL_ZERO=YES")
    print("N71_USB_GADGET_AND_TOUCH_PROTOCOL_READY=YES")
    print("N71_PHYSICAL_PCIE_LINK_DART_DMA_REQUESTER_SID_NATIVE_WIFI_PROVEN=NO")
    print("N71_MODULE_UNLOAD_NOT_ATTEMPTED=YES")
    return 0
if __name__=="__main__":raise SystemExit(main())
