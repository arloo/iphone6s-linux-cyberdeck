#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# N71 iPhone 6s S8000: RAM-only battery-observation kernel handoff.
# The validated PERST-held port1 module is bundled but not auto-loaded.
# Private firmware stays on the owner host; no boot image is distributed.
#
# Usage:
#   bash scripts/n71-batt2-pongo-ram-smoke.sh status
#   [owner physically enters DFU; previously tested Pongo boots to 05ac:4141]
#   sudo bash scripts/n71-batt2-pongo-ram-smoke.sh send
#
# Does NOT enter DFU, write flash/NAND, erase firmware, touch Wi-Fi/PHY,
# modify host routing/firewall, or enable DART1 MMIO/DMA or mobile baseband.
set -euo pipefail

MODE="${1:-status}"
if [[ "$MODE" != status && "$MODE" != send ]]; then
  echo "N71_BATT2_AUTOSTART_RAM_USAGE: status | send" >&2
  exit 2
fi

PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
IMAGE="$PROJECT/private-touch-live-test/n71-batt2-autostart-20261113/m1n1-n71-batt2-charging-bt-dart9-ram.bin"
PONGOTERM="$PROJECT/hoolock/bin/pongoterm"
PIN_SHA="acd50a55e0e44169b5bf66dd3222122715527801abbf17a0e4393595e6b299d9"
PIN_SIZE=13703936

test -f "$IMAGE" && ! test -L "$IMAGE" || {
  echo "N71_SMOKE_FAIL: pinned private RAM boot missing or symlinked" >&2
  exit 3
}
test -x "$PONGOTERM" || {
  echo "N71_SMOKE_FAIL: locally verified Pongo USB tool missing" >&2
  exit 3
}
ACTUAL_SIZE="$(stat -c %s -- "$IMAGE")"
[[ "$ACTUAL_SIZE" == "$PIN_SIZE" ]] || {
  echo "N71_SMOKE_FAIL: private RAM image size mismatch" >&2
  exit 4
}
ACTUAL_SHA="$(sha256sum -- "$IMAGE" | cut -d ' ' -f1)"
[[ "$ACTUAL_SHA" == "$PIN_SHA" ]] || {
  echo "N71_SMOKE_FAIL: private RAM image checksum mismatch" >&2
  exit 4
}
echo "N71_BATT2_AUTOSTART_RAM_HASH_AND_SIZE_PIN_PASS"

if lsusb -d 05ac:4142 | grep -q '05ac:4142'; then
  if [[ "$MODE" == send ]]; then
    echo "N71_SMOKE_REFUSED: the known-good iPhone RAM Linux is still running; do not reset remotely" >&2
    exit 5
  fi
  echo "N71_PHONE_EXISTING_SAFE_LINUX_USB_GADGET_ONLINE=YES"
  echo "N71_NEW_RAM_IMAGE_BOOT_NOT_ATTEMPTED=YES"
  exit 0
fi

if ! lsusb -d 05ac:4141 | grep -q '05ac:4141'; then
  echo "N71_PHONE_PONGO_NOT_ACTIVE; physical owner DFU/Pongo required before any send"
  [[ "$MODE" == status ]] && exit 0
  exit 6
fi
echo "N71_PHONE_PONGO_USB_GADGET_ACTIVE=YES"

if [[ "$MODE" == status ]]; then
  echo "N71_NEW_RAM_IMAGE_SENDING_REQUIRES_EXPLICIT_SEND=YES"
  exit 0
fi

[[ "$EUID" == 0 ]] || {
  echo "N71_SMOKE_REFUSED: Pongo USB write requires sudo, run with sudo bash..." >&2
  exit 7
}
LOG="/run/n71-batt2-autostart-ram-smoke-pongo.log"
umask 077
echo "N71_RAM_ONLY_PONGO_SEND_PINNED_IMAGE=START"
set +e
printf '/send %s\nbootm\n' "$IMAGE" | "$PONGOTERM" >"$LOG" 2>&1
tool_rc=$?
set -e
if grep -Fq "Uploaded $PIN_SIZE bytes" "$LOG"; then
  echo "N71_PONGO_PINNED_RAM_IMAGE_UPLOAD_COMPLETE=YES"
else
  echo "N71_SMOKE_UPLOAD_ACK_MISSING: inspect local Pongo log, do not retry blindly" >&2
  exit 8
fi
for ((i=0;i<18;i++)); do
  if lsusb -d 05ac:4142 | grep -q '05ac:4142'; then
    echo "N71_NEW_LINUX_USB_GADGET_HARDWARE_REENUMERATED=YES"
    echo "N71_PONGO_COMMAND_EXIT_CODE=$tool_rc"
    echo "N71_NATIVE_WIFI_BCM4350_STILL_NOT_PROVEN=YES"
    echo "N71_BATTERY_READINGS_AND_CHARGING_NOT_YET_VERIFIED=YES"
    echo "N71_NEXT: verify uname and run /usr/bin/n71-battery-status over USB"
    exit 0
  fi
  sleep 1
done
echo "N71_PONGO_HANDOFF_NOT_CONFIRMED: no 05ac:4142 after bounded window" >&2
echo "N71_PONGO_COMMAND_EXIT_CODE=$tool_rc"
echo "N71_SMOKE_STATUS=NOT_PROVEN_DO_NOT_RETRY_UNSUPERVISED" >&2
exit 9
