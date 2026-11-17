#!/bin/sh
# SPDX-License-Identifier: MIT
# N71/S8000 Kali-compatible first-stage field diagnostic profile.
# Not a Kali Linux distribution: official Kali ARM64 rootfs remains pending.
set -e
export PATH=/opt/kali/bin:/usr/sbin:/usr/bin:/sbin:/bin

help() {
 cat <<'EOF'
CYBERDECK A9 / KALI TOOL PROFILE
No privileged scanning or RF injection is automated.
Use ONLY networks and hosts you own or are authorized to test.

n71-kali status               Installed and missing tools
n71-kali network              wlan0/usb0 addresses and routes
n71-kali ping HOST            Two ICMP echo probes
n71-kali dns HOST             DNS lookup
n71-kali trace HOST           Traceroute (max 10 hops)
n71-kali port HOST PORT       Single TCP port connect test
n71-kali capture [COUNT]      Passive capture if tcpdump is installed
n71-kali help                 This page

Optional Kali chroot: not installed; do not use unverified mirror images.
Monitor mode, injection, external USB modules and full Kali are NOT ready.
EOF
}

valid_host() {
 case "$1" in
   ''|*[!a-zA-Z0-9._:-]*) echo "Invalid hostname or IP"; exit 3 ;;
 esac
 [ "${#1}" -le 253 ] || exit 3
}

count_ports() {
 case "$1" in ''|*[!0-9]*) echo "Invalid port"; exit 3 ;; esac
 [ "$1" -ge 1 ] && [ "$1" -le 65535 ] || exit 3
}

MODE="$1"
case "$MODE" in
 ""|help|--help) help ;;
 status)
   echo "N71-KALI stage=BusyBox + networking"
   for name in ip ifconfig ping nslookup traceroute nc arp ssh wget tcpdump nmap; do
     if command -v "$name" >/dev/null 2>&1; then
       echo "INSTALLED $name"
     else
       echo "PENDING   $name"
     fi
   done
   echo "Kali ARM64 userspace: NOT installed"
   echo "Persistent rootfs: NOT installed"
   ;;
 network)
   echo "-- wlan0 --"; ifconfig wlan0
   echo "-- usb0 --"; ifconfig usb0
   echo "-- routes --"; ip route show
   ;;
 ping)
   valid_host "$2"
   ping -c 2 -W 2 "$2"
   ;;
 dns)
   valid_host "$2"
   nslookup "$2"
   ;;
 trace)
   valid_host "$2"
   traceroute -n -m 10 -w 1 -q 1 "$2"
   ;;
 port)
   valid_host "$2"
   count_ports "$3"
   echo "Authorized TCP connect to $2:$3"
   nc -z -v -w 3 "$2" "$3"
   ;;
 capture)
   count="$2"
   [ -n "$count" ] || count=12
   case "$count" in *[!0-9]*) exit 3 ;; esac
   [ "$count" -ge 1 ] && [ "$count" -le 50 ] || exit 3
   if ! command -v tcpdump >/dev/null 2>&1; then
     echo "tcpdump not installed yet; passive capture unavailable"
     exit 4
   fi
   # Passive capture only, bounded frames/bytes; no monitor or packet injection.
   tcpdump -n -i wlan0 -s 96 -c "$count" -q
   ;;
 *)
   help
   exit 2
   ;;
esac
