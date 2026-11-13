#!/bin/sh
# SPDX-License-Identifier: MIT
# Bounded power-source observation; reads gauge properties and writes a RAM log.
set -eu
count=${1:-60}
interval=${2:-10}
out=${3:-/run/n71-battery-charge-test.tsv}
for value in "$count" "$interval"; do
    case "$value" in ''|*[!0-9]*) echo 'Expected integer arguments' >&2; exit 2;; esac
done
[ "$count" -ge 1 ] && [ "$count" -le 60 ]
[ "$interval" -ge 1 ] && [ "$interval" -le 10 ]
supply=/sys/class/power_supply/bq27540-0
[ -d "$supply" ]
# Refuse an existing log or symlink; do not overwrite earlier evidence.
set -C
printf 'uptime_s\tcapacity_pct\tstatus\tcurrent_uA\tvoltage_uV\ttemp_deciC\tcharge_uAh\n' > "$out"
i=0
while [ "$i" -lt "$count" ]; do
    up=$(cut -d ' ' -f 1 /proc/uptime)
    cap=$(cat "$supply/capacity")
    state=$(cat "$supply/status")
    current=$(cat "$supply/current_now")
    voltage=$(cat "$supply/voltage_now")
    temperature=$(cat "$supply/temp")
    charge=$(cat "$supply/charge_now")
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$up" "$cap" "$state" "$current" "$voltage" "$temperature" "$charge" >> "$out"
    [ "$cap" -ge 15 ] && [ "$temperature" -lt 450 ] || {
        echo 'Observation stopped: low charge or high temperature' >&2
        exit 3
    }
    i=$((i + 1))
    [ "$i" -ge "$count" ] || sleep "$interval"
done
