#!/bin/sh
# SPDX-License-Identifier: MIT
# Read-only PCIe identity gate: accept only the onboard Broadcom BCM4350.
# The second argument is sysfs root; production Wi-Fi acceptance ALWAYS /sys.
set -eu

fail() { printf 'N71_ONBOARD_BCM4350_IDENTITY_FAIL:%s\n' "$1"; exit 1; }

[ "$#" -eq 2 ] || fail usage_interface_sysfs_root
IFACE=$1
case "$IFACE" in
  ""|*[!a-zA-Z0-9_.-]*|.|..) fail invalid_interface ;;
esac

[ -d "$2" ] || fail sysfs_root_absent
ROOT=$(cd "$2" && pwd -P) || fail sysfs_root_invalid
[ -d "$ROOT/bus/pci/devices" ] || fail pci_bus_absent
[ -e "$ROOT/class/net/$IFACE/phy80211" ] || fail ieee80211_phy_absent
[ -e "$ROOT/class/net/$IFACE/device" ] || fail parent_device_absent

DEV=$(readlink -f "$ROOT/class/net/$IFACE/device") || fail parent_device_unresolved
[ -d "$DEV" ] || fail parent_device_unresolved
case "$DEV" in
  "$ROOT"/devices/*) : ;;
  *) fail device_outside_sysfs_root ;;
esac

# Endpoint must appear AS an actual PCI function on this same sysfs tree;
# merely naming a USB dongle "wlan0" is insufficient.
MATCH=0
for PCINODE in "$ROOT"/bus/pci/devices/*; do
  [ -e "$PCINODE" ] || continue
  ACTUAL=$(readlink -f "$PCINODE") || continue
  if [ "$ACTUAL" = "$DEV" ]; then MATCH=1; break; fi
done
[ "$MATCH" -eq 1 ] || fail not_pci_endpoint

[ -f "$DEV/vendor" ] || fail missing_pci_vendor
[ -f "$DEV/device" ] || fail missing_pci_device_id
VENDOR=$(cat "$DEV/vendor") || fail vendor_read_failed
DEVICE=$(cat "$DEV/device") || fail device_id_read_failed
[ "$VENDOR" = "0x14e4" ] || fail not_broadcom_vendor
[ "$DEVICE" = "0x43a3" ] || fail not_bcm4350_pci_device

[ -e "$DEV/driver" ] || fail missing_driver
DRIVER=$(readlink -f "$DEV/driver") || fail driver_unresolved
[ "$(basename "$DRIVER")" = "brcmfmac" ] || fail not_brcmfmac

printf '%s\n' 'N71_ONBOARD_BCM4350_PCIE_IDENTITY_PASS'
