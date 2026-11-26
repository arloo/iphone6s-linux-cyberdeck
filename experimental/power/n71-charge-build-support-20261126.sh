#!/bin/sh
# SPDX-License-Identifier: MIT
# Historical owner-attended build support for the 2026-11-26 closed prefix epoch.
# Caller must attest direct USB500mA, exact native source/ELF, prior rollback,
# Good battery and closed/held S3E before this worker. No S3E access or renewal.
# Pinned to the OLD native binary; not a starter for the new two-hour image.
set -eu
BAT=/sys/class/power_supply/bq27540-0
MOD=/usr/lib/cyberdeck/n71-sn2400-input-trial.ko
ACTIVE=0
cleanup(){ if [ "$ACTIVE" = 1 ]; then rmmod n71_sn2400_input_trial; ACTIVE=0; echo BUILD_SUPPORT_NATIVE_MODULE_REMOVED; fi; }
check(){
 [ "$(cat "$BAT/health")" = Good ]
 c=$(cat "$BAT/capacity");t=$(cat "$BAT/temp");v=$(cat "$BAT/voltage_now")
 [ "$c" -ge 12 ] && [ "$t" -ge 100 ] && [ "$t" -lt 375 ] && [ "$v" -ge 3350000 ] && [ "$v" -lt 4100000 ]
}
[ "$(sha256sum "$MOD" | cut -d' ' -f1)" = b559145fd3c1c30ba3aea008544ffb2fcf7aa737b69773f53f1512b1d197eec7 ]
check
last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1)
if [ -d /sys/module/n71_sn2400_input_trial ]; then
 [ "$(cat /sys/module/n71_sn2400_input_trial/parameters/input_ua)" = 500000 ]
 [ "$(cat /sys/module/n71_sn2400_input_trial/parameters/lease_seconds)" = 30 ]
 case "$last" in *'RESTORE reason=30s-expired input=00 rc=0'*) :;;*)exit 31;;esac
 rmmod n71_sn2400_input_trial
else
 case "$last" in *'RESTORE reason=module-exit input=00 rc=0'*) :;;*)exit 31;;esac
fi
trap 'cleanup' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
ACTIVE=1
/usr/bin/n71-module-once "$MOD" 'armed=1 input_ua=500000 lease_seconds=3600'
start=$(cut -d. -f1 /proc/uptime)
echo BUILD_SUPPORT_500MA_3600S_STARTED_NO_S3E_ACCESS
sleep 4
while :; do
 check
 now=$(cut -d. -f1 /proc/uptime)
 [ $((now-start)) -lt 3540 ] || break
 last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1)
 case "$last" in *'MONITOR VBUS_uV='*'input_uA=500000'*) :;;*)echo NATIVE_MONITOR_STOP_OR_RESTORE;exit 32;;esac
 event=$(printf '%s
' "$last" | sed -n 's/^\[ *\([0-9]*\)\..*/\1/p')
 vbus=$(printf '%s
' "$last" | sed -n 's/.*VBUS_uV=\([0-9]*\).*/\1/p')
 [ -n "$event" ] && [ -n "$vbus" ] && [ $((now-event)) -le 6 ] && [ "$vbus" -ge 4750000 ] && [ "$vbus" -le 5500000 ]
 printf 'BUILD_CHARGE sec=%s cap=%s temp=%s cell_uV=%s current_uA=%s VBUS_uV=%s
' "$((now-start))" "$c" "$t" "$v" "$(cat "$BAT/current_now")" "$vbus"
 sleep 2
done
echo BUILD_SUPPORT_COMPLETED_FINITE_NO_RENEWAL
