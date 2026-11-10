#!/usr/bin/env bash
# S8000 A9 authorized host-side recovery observation only.
# No DFU transfer, USB reset, reboot, flash, kernel load or device writes.
set -euo pipefail

command -v lsusb >/dev/null || {
  echo "ERROR: lsusb required"; exit 3;
}
now="$(date -Iseconds)"
echo "OBSERVED_AT=$now"
if ! devices="$(lsusb)"; then
  echo "ERROR: lsusb could not enumerate host USB"; exit 3;
fi

if grep -qiE 'ID 05ac:4142' <<<"$devices"; then
  echo "PHONE_STATE=LINUX_GADGET_ENUMERATED"
  echo "NEXT=Verify shell and board baselines read-only; do not assume touch recovered."
  exit 0
fi
if grep -qiE 'ID 05ac:4141' <<<"$devices"; then
  echo "PHONE_STATE=PONGOOS_USB_ENUMERATED"
  echo "NEXT=Operator must select a previously verified RAM kernel; do not auto-upload."
  exit 0
fi
if grep -qiE 'ID 05ac:1227' <<<"$devices"; then
  echo "PHONE_STATE=APPLE_DFU_ENUMERATED"
  echo "NEXT=Operator must explicitly choose attended DFU/PongoOS boot; do not flash."
  exit 0
fi
if grep -qiE 'ID 05ac:128[01]' <<<"$devices"; then
  echo "PHONE_STATE=POSSIBLE_APPLE_RECOVERY_MODE"
  echo "NEXT=Verify with authorized device-aware tool; do not assume phone or act automatically."
  exit 2
fi
if grep -qiE 'ID 05ac:' <<<"$devices"; then
  echo "PHONE_STATE=APPLE_USB_DEVICE_OTHER"
  echo "NEXT=Physically verify which Apple device is present; no automated action."
  exit 2
fi

echo "PHONE_STATE=NOT_ENUMERATED"
echo "NEXT=Attended visual inspection and cable/power check only; do not reset USB root hub remotely."
exit 2
