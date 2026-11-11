#!/bin/sh
# SPDX-License-Identifier: MIT
# On-device native Wi-Fi acceptance test. USB connectivity cannot pass.
set -eu
fail() { printf '%s\n' "N71_NATIVE_WIFI_FAIL:$1"; exit 1; }
[ "$#" -eq 4 ] || fail "usage_iface_ssid_gateway_peer"
IFACE=$1; SSID=$2; GATEWAY=$3; PEER=$4
case "$IFACE" in
 ""|*[!a-zA-Z0-9_.-]*|usb*|enx*|eth*|lo|sit*|tun*|tap*) fail "not_native_wifi" ;;
esac
[ -n "$SSID" ] || fail "missing_ssid"
[ -d "/sys/class/net/$IFACE" ] || fail "wlan_interface_absent"
[ -e "/sys/class/net/$IFACE/phy80211" ] || fail "wireless_phy_absent"
[ -d /sys/class/ieee80211 ] || fail "wireless_class_absent"
command -v iw >/dev/null 2>&1 || fail "missing_iw"
command -v ip >/dev/null 2>&1 || fail "missing_ip"
command -v ping >/dev/null 2>&1 || fail "missing_ping"
link=$(iw dev "$IFACE" link 2>/dev/null) || fail "iw_link_error"
case "$link" in *"Connected to "*) : ;; *) fail "not_associated" ;; esac
actual_ssid=$(printf '%s\n' "$link" | sed -n 's/^[[:space:]]*SSID: //p' | head -n 1)
[ "$actual_ssid" = "$SSID" ] || fail "wrong_ssid"
check_route() {
 addr=$1
 route=$(ip -4 route get "$addr" 2>/dev/null) || fail "route_unavailable"
 case " $route " in *" dev $IFACE "*) : ;; *) fail "route_not_wlan" ;; esac
}
check_route "$GATEWAY"
check_route "$PEER"
ping -I "$IFACE" -c 2 -W 2 "$GATEWAY" >/dev/null 2>&1 || fail "gateway_unreachable"
printf '%s\n' "N71_NATIVE_WIFI_GATEWAY_PASS"
ping -I "$IFACE" -c 2 -W 2 "$PEER" >/dev/null 2>&1 || fail "dell_unreachable"
printf '%s\n' "N71_NATIVE_WIFI_LAN_PEER_PASS"
printf '%s\n' "N71_NATIVE_WIFI_ACCEPTANCE_PASS: radio association and LAN reachability via WLAN, not USB"
