#!/bin/sh
# SPDX-License-Identifier: MIT
# Read existing power_supply properties; do not program charging controls.
printf 'Kernel: '; uname -r
found=0
for supply in /sys/class/power_supply/*; do
    [ -d "$supply" ] || continue
    found=1
    printf '\nSupply: %s\n' "${supply##*/}"
    for prop in type present status capacity voltage_now current_now temp charge_now charge_full charge_full_design cycle_count online; do
        if [ -r "$supply/$prop" ]; then
            printf '%s=' "$prop"
            cat "$supply/$prop"
        fi
    done
done
if [ "$found" = 0 ]; then
    echo 'NO_POWER_SUPPLY_REGISTERED: battery level and charging are UNKNOWN'
fi
echo 'Units follow Linux power_supply ABI: voltage uV, current uA, temperature 0.1 C.'
echo 'A cable connection alone does not confirm charging; compare timestamped samples.'
