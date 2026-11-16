#!/bin/sh
# SPDX-License-Identifier: MIT
# Reversible display-only adjustment. Does not change CPU, radio or charge limits.
set -eu
umask 077
for board in apple,n71 apple,s8000; do
 tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board"
done
set -- /sys/class/backlight/*/brightness
[ "$#" = 1 ] && [ -f "$1" ] || exit 2
brightness=$1
maximum=${brightness%/*}/max_brightness
saved=/run/n71-original-brightness
mode=${N71_DISPLAY_ACTION:-status}
case "$mode" in
 status) ;;
 apply)
  mkdir -p /run
  if [ ! -e "$saved" ]; then cat "$brightness" > "$saved"; fi
  max=$(cat "$maximum");case "$max" in ''|*[!0-9]*) exit 2;; esac
  [ "$max" -gt 0 ] && [ "$max" -le 65535 ] || exit 2
  printf '%s\n' "$((max / 2))" > "$brightness"
  ;;
 restore)
  original=$(cat "$saved");case "$original" in ''|*[!0-9]*) exit 2;; esac
  [ "$original" -le "$(cat "$maximum")" ] || exit 2
  printf '%s\n' "$original" > "$brightness"
  ;;
 *) exit 2;;
esac
printf 'BRIGHTNESS=';cat "$brightness"
printf 'MAX_BRIGHTNESS=';cat "$maximum"
