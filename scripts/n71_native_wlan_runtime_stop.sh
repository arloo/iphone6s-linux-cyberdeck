#!/bin/sh
# SPDX-License-Identifier: MIT
# Run on the phone as root. Unbind before rmmod: the active IOMMU pins its owner.
set -eu
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx apple,n71
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx apple,s8000
for file in /tmp/n71-wpa-live.pid /tmp/n71-dhcp-live.pid; do
 test -f "$file" || continue
 pid=$(cat "$file")
 case "$pid" in ''|*[!0-9]*) exit 1;; esac
 test -r "/proc/$pid/cmdline" || continue
 cmd=$(tr '\000' ' ' < "/proc/$pid/cmdline")
 case "$cmd" in /tmp/n71-wpa_supplicant\ *|*n71-udhcpc-script.sh*) kill "$pid";; *) exit 1;; esac
done
for device in /sys/bus/platform/drivers/n71-s8000-perst-held/*; do
 test -L "$device" && test -f "$device/modalias" || continue
 name=$(basename "$device")
 case "$name" in *n71-port1-perst-held*) printf '%s\n' "$name" > /sys/bus/platform/drivers/n71-s8000-perst-held/unbind;; esac
done
rmmod pcie_apple_s8000_port1_perst_held
if test -f /tmp/n71-resolv-before-WLAN; then
 cat /tmp/n71-resolv-before-WLAN > /etc/resolv.conf
 rm /tmp/n71-resolv-before-WLAN
fi
if test -f /tmp/n71-default-routes-before-WLAN; then
 while IFS= read -r route; do
  test -z "$route" || ip route replace $route
 done < /tmp/n71-default-routes-before-WLAN
 rm /tmp/n71-default-routes-before-WLAN
fi
test -z "$(ls -A /sys/bus/pci/devices)"
printf '%s\n' N71_MANAGED_WLAN_STOPPED
