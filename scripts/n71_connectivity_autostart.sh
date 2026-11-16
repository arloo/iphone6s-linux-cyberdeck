#!/bin/sh
# SPDX-License-Identifier: MIT
# N71 RAM-only connectivity. Called after the existing charging/HCI startup.
# Credentials, firmware, machine-id and BlueZ bonds belong only in a private image.
set -eu
umask 077
fail() { echo "CONNECTIVITY_FAIL_$1"; exit 1; }
case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) ;; *) fail KERNEL;; esac
for board in apple,n71 apple,s8000; do
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board" || fail BOARD
done
mkdir -p /run
mkdir /run/n71-connectivity.lock 2>/dev/null || fail BUSY
trap 'rmdir /run/n71-connectivity.lock' EXIT
sha256sum -c /usr/lib/cyberdeck/n71-connectivity.sha256 > /run/n71-connectivity-hashes.log 2>&1 || fail HASH
rt=/tmp/n71-bluez-runtime
[ -d "$rt" ] && chmod 700 "$rt" || fail BLUEZ_RUNTIME
[ -r /etc/passwd ] && [ -r /etc/group ] && [ -s /etc/machine-id ] || fail DBUS_IDENTITY
# A PID is usable only when /proc confirms the exact expected executable.
alive() {
    [ -r "$1" ] || return 1
    n71_pid=$(cat "$1")
    case "$n71_pid" in ''|*[!0-9]*) return 1;; esac
    [ -r "/proc/$n71_pid/cmdline" ] || return 1
    tr '\000' '\n' < "/proc/$n71_pid/cmdline" | grep -Fxq "$2"
}
if ! alive "$rt/dbus.pid" "$rt/bin/dbus-daemon"; then
    "$rt/run" dbus-daemon --config-file="$rt/dbus.conf" --fork --print-pid > "$rt/dbus.pid" 2> "$rt/dbus-PRIVATE.log" || fail DBUS
fi
if ! alive "$rt/daemon.pid" "$rt/bin/bluetoothd"; then
    "$rt/run" bluetoothd --nodetach --configfile="$rt/main.conf" > "$rt/daemon-PRIVATE.log" 2>&1 </dev/null &
    echo "$!" > "$rt/daemon.pid"
fi
i=0
until "$rt/run" bluetoothctl --timeout 2 show > "$rt/controller-PRIVATE.log" 2>&1 && grep -q 'Controller ' "$rt/controller-PRIVATE.log"; do
    i=$((i+1)); [ "$i" -lt 10 ] || fail BLUEZ_CONTROLLER; sleep 1
done
"$rt/run" bluetoothctl --timeout 3 power on > "$rt/power-PRIVATE.log" 2>&1 || fail BT_POWER
"$rt/run" bluetoothctl --timeout 3 discoverable off > "$rt/discoverable-PRIVATE.log" 2>&1 || fail BT_DISCOVERABLE
printf 'BLUETOOTH_SERVICE_READY\n'
module=pcie_apple_s8000_port1_perst_held
if [ ! -d "/sys/module/$module" ]; then
    /tmp/n71-managed-loader /tmp/n71-managed-wlan.ko 'armed=1 stage=29' > /run/n71-managed-load-PRIVATE.log 2>&1 || fail WLAN_MODULE
fi
i=0
until [ "$(cat /sys/module/$module/parameters/runtime_state 2>/dev/null)" = 2 ]; do
    [ "$(cat /sys/module/$module/parameters/runtime_state 2>/dev/null)" != -1 ] || fail WLAN_WORKER
    i=$((i+1)); [ "$i" -lt 30 ] || fail WLAN_TIMEOUT; sleep 1
done
iface=
for d in /sys/class/net/*; do
    if [ -e "$d/phy80211" ] && [ "$(cat "$d/device/vendor" 2>/dev/null)" = 0x14e4 ] && [ "$(cat "$d/device/device" 2>/dev/null)" = 0x43a3 ]; then
        [ -z "$iface" ] || fail MULTIPLE_WLAN
        iface=$(basename "$d")
    fi
done
[ -n "$iface" ] || fail WLAN_ABSENT
ip link set dev "$iface" up
if ! alive /tmp/n71-wpa-live.pid /tmp/n71-wpa_supplicant; then
    /tmp/n71-wpa_supplicant -B -i "$iface" -D nl80211 -c /tmp/n71-wpa-live.conf -P /tmp/n71-wpa-live.pid > /tmp/n71-wpa-managed-PRIVATE.log 2>&1 || fail WPA_START
fi
i=0
until /tmp/n71-wpa_cli -p /tmp/n71-wpa-ctrl -i "$iface" status > /tmp/n71-wpa-status-PRIVATE && grep -q '^wpa_state=COMPLETED$' /tmp/n71-wpa-status-PRIVATE; do
    i=$((i+1)); [ "$i" -lt 20 ] || fail WPA_TIMEOUT; sleep 1
done
if ! alive /tmp/n71-dhcp-live.pid udhcpc; then
    udhcpc -b -p /tmp/n71-dhcp-live.pid -i "$iface" -t 5 -T 2 -s /tmp/n71-udhcpc-script.sh > /tmp/n71-dhcp-managed-PRIVATE.log 2>&1 || fail DHCP_START
fi
i=0
until ip -4 addr show dev "$iface" | grep -q 'inet ' && ip -4 route show default | grep -q "dev $iface"; do
    i=$((i+1)); [ "$i" -lt 15 ] || fail DHCP_TIMEOUT; sleep 1
done
printf 'WIFI_AUTHENTICATED_DHCP_READY\nCONNECTIVITY_STARTUP_READY\n'
