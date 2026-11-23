#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# N71 Dell host: isolated USB2 root-hub port1 logical disable/re-enable.
# This is NOT necessarily a physical VBUS power-cycle.
# Never run during DFU exploit, Pongo, RAM-image upload, or live Linux USB.
set -euo pipefail
mode="${1:---check}"
port=/sys/bus/usb/devices/usb1/1-0:1.0/usb1-port1
target=/sys/bus/usb/devices/1-1
last_disabled=0
recover_port() {
  status=$?
  trap - EXIT INT TERM
  if ((last_disabled)); then
    if ! printf '0\n' > "$port/disable"; then
      echo 'N71_USB_PORT_REENABLE_FAILED: inspect the port before reconnecting' >&2
      exit 12
    fi
    echo 'N71_USB_PORT_RECOVERED_AFTER_INTERRUPTION'
  fi
  exit "$status"
}
[[ "$mode" == '--check' || "$mode" == '--reset' ]] || {
  echo 'Usage: bash scripts/n71-host-usb-port1-recover.sh --check|--reset' >&2
  exit 2
}
[[ -d "$port" && -r "$port/disable" ]] || {
  echo 'N71_USB_PORT1_SYSFS_MISSING' >&2
  exit 3
}
[[ "$(cat "$port/connect_type")" == hotplug ]] || {
  echo 'N71_USB_PORT1_NOT_HOTPLUG_REFUSE' >&2
  exit 3
}
peer="$(readlink -f "$port/peer")"
[[ "$peer" == */usb2-port1 ]] || {
  echo 'N71_USB_PORT1_PEER_MISMATCH_REFUSE' >&2
  exit 3
}
for process in palera1n pongoterm irecovery; do
  if pgrep -x "$process" >/dev/null 2>&1; then
    echo "N71_USB_PORT_BUSY_REFUSE=$process" >&2
    exit 4
  fi
done
if [[ -d "$target" ]]; then
  [[ -r "$target/idVendor" && -r "$target/idProduct" ]] || {
    echo 'N71_USB_DEVICE_ID_UNAVAILABLE_REFUSE' >&2
    exit 5
  }
  vendor="$(cat "$target/idVendor")"
  product="$(cat "$target/idProduct")"
  [[ "$vendor" == 05ac ]] || {
    echo 'N71_USB_FOREIGN_DEVICE_REFUSE' >&2
    exit 5
  }
  case "$product" in
    12a8|1227|1281|1338) ;;
    4141|4142)
      echo 'N71_USB_ACTIVE_PONGO_OR_LINUX_REFUSE' >&2
      exit 6
      ;;
    *)
      echo 'N71_USB_UNKNOWN_APPLE_MODE_REFUSE' >&2
      exit 6
      ;;
  esac
  echo "N71_USB_PORT1_APPLE_MODE=$product"
else
  echo 'N71_USB_PORT1_NO_DEVICE_DETECTED'
fi
[[ "$(cat "$port/disable")" == 0 ]] || {
  echo 'N71_USB_PORT1_ALREADY_DISABLED_REFUSE' >&2
  exit 7
}
echo "N71_USB_PORT1_STATE=$(cat "$port/state")"
if [[ "$mode" == '--check' ]]; then
  echo 'N71_USB_PORT1_PREFLIGHT_PASS_NO_CHANGES'
  exit 0
fi
[[ "$(id -u)" == 0 && -w "$port/disable" ]] || {
  echo 'N71_USB_RESET_NEEDS_OWNER_ROOT_TERMINAL' >&2
  exit 8
}
# Repeat identity / process gates immediately before action, minimizing TOCTOU.
for process in palera1n pongoterm irecovery; do
  if pgrep -x "$process" >/dev/null 2>&1; then
    echo "N71_USB_PORT_BECAME_BUSY_REFUSE=$process" >&2
    exit 4
  fi
done
if [[ -d "$target" ]]; then
  [[ "$(cat "$target/idVendor")" == 05ac ]] || {
    echo 'N71_USB_TARGET_CHANGED_REFUSE' >&2
    exit 5
  }
  case "$(cat "$target/idProduct")" in
    12a8|1227|1281|1338) ;;
    *) echo 'N71_USB_TARGET_MODE_CHANGED_REFUSE' >&2; exit 6 ;;
  esac
fi
trap recover_port EXIT INT TERM
last_disabled=1
printf '1\n' > "$port/disable"
echo 'N71_USB_PORT1_LOGICALLY_DISABLED'
sleep 2
printf '0\n' > "$port/disable"
last_disabled=0
echo 'N71_USB_PORT1_LOGICALLY_REENABLED'
sleep 2
echo "N71_USB_PORT1_FINAL_STATE=$(cat "$port/state")"
if [[ -d "$target" && -r "$target/idProduct" ]]; then
  echo "N71_USB_REENUMERATED_APPLE_MODE=$(cat "$target/idProduct")"
else
  echo 'N71_USB_NO_ENUMERATION_YET_RECONNECT_IPHONE'
fi
echo 'N71_USB_RESET_COMPLETED_NO_OTHER_PORTS_TOUCHED'
