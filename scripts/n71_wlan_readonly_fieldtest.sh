#!/bin/sh
# SPDX-License-Identifier: MIT
# Genuine N71/S8000 Linux RAM-only PCIe/WLAN baseline field test.
# Reads virtual Linux kernel procfs/sysfs metadata ONLY. No /dev/mem,
# ioremap, radio commands, firmware loading, clocks, PHY, NAND or reset.
# Diagnostic prints do not include MAC, Wi-Fi passwords or serials.
set -u

ROOT="${N71_READONLY_FIXTURE_ROOT:-}"
# Fixtures are ONLY for CI/unit tests, never real board activation.
case "$ROOT" in
    "") ;;
    /*) ;;
    *) printf '%s\n' 'N71_WLAN_FIELDTEST_REJECTED_RELATIVE_FIXTURE'; exit 2 ;;
esac

proc="$ROOT/proc"
sys="$ROOT/sys"
dt="$proc/device-tree/compatible"

log() { printf 'N71_WLAN_FIELDTEST_%s\n' "$1"; }
count_paths() {
    total=0
    for file in "$@"; do
        [ -e "$file" ] || continue
        total=$((total+1))
    done
    printf '%s\n' "$total"
}

if [ ! -f "$dt" ]; then
    log 'FAIL_NO_DT_COMPAT'
    exit 2
fi
if ! tr '\000' '\n' < "$dt" | grep -qx 'apple,n71'; then
    log 'SKIP_NOT_N71'
    exit 2
fi
if ! tr '\000' '\n' < "$dt" | grep -qx 'apple,s8000'; then
    log 'SKIP_NOT_S8000'
    exit 2
fi

log 'BOARD_N71_S8000_PASS'
log 'ACCESS_MODE_SYSFS_PROCFS_METADATA_ONLY'
log "PCIE_CORE_PRESENT=$([ -d "$sys/bus/pci" ] && echo YES || echo NO)"
log "PCI_DEVICES_COUNT=$(count_paths "$sys"/bus/pci/devices/*)"
log "IOMMU_GROUPS_COUNT=$(count_paths "$sys"/kernel/iommu_groups/*)"

pci_port1=0
dart1=0
for path in "$sys"/bus/platform/devices/*; do
    [ -e "$path" ] || continue
    case "${path##*/}" in
        *602000000*|*602004000*) pci_port1=$((pci_port1+1)) ;;
        *602008000*) dart1=$((dart1+1)) ;;
    esac
done
log "N71_PCIE_PORT1_PLATFORM_NODES_MATCHED=$pci_port1"
log "N71_DART1_PLATFORM_NODES_MATCHED=$dart1"

wlan_count=0
for path in "$sys"/class/net/*; do
    [ -e "$path" ] || continue
    case "${path##*/}" in
        wlan*|wlp*|wlx*) wlan_count=$((wlan_count+1)) ;;
    esac
done
log "WLAN_INTERFACES_COUNT=$wlan_count"

# Enumerated Linux PCI devices alone are not necessarily the BCM4350.
# No Wi-Fi association is inferred from a named interface or module.
if [ "$wlan_count" -gt 0 ]; then
    log 'WLAN_NETWORK_ASSOCIATION_NOT_TESTED'
else
    log 'WLAN_NATIVE_NOT_ENUMERATED_OR_NOT_NAMED'
fi
log 'NO_PHYSICAL_MMIO_DMA_RESET_OR_RADIO_COMMANDS=YES'
log 'TEST_FINISHED'
exit 0
