#!/bin/sh
# SPDX-License-Identifier: MIT
# N71/S8000 owner RAM-only charging supervisor. No NAND writes.
# Continuous charging attempt via guarded re-arming, NOT disabling the
# kernel module's 2s VBUS/thermal/cell-voltage checks or its 1h rollback.
# Fail closed: a missing USB link, expired lease, monitor stop or unexpected
# battery value leaves the pilot module alone and exits with error.
set -eu
umask 077

MODE=${1:---check}
DEVICE_MODULE=/usr/lib/cyberdeck/n71-sn2400-input-trial.ko
EXPECTED_SHA=06b497deb2baf3724fe3d03f72870df2910d40b27afd71e176df52f2358aafea
INPUT_UA=300000
LEASE_SECONDS=3600
REFRESH_AT_AGE=2400
MIN_RENEW_CAPACITY=35
MAX_RENEW_VOLTAGE_UV=4180000
LOCKFILE=/run/n71-charge-supervisor.lock
LOG=/run/n71-charge-supervisor.log

die() { echo "CHARGE_SUPERVISOR_FAIL_CLOSED: $*" >&2; exit 2; }
read_number() {
    value=$(cat "$1") || die "missing metric $1"
    case "$value" in ''|*[!0-9]*) die "non-integer metric $1" ;; esac
    printf '%s\n' "$value"
}
event_sec() { printf '%s\n' "$1" | sed -n 's/^\[ *\([0-9][0-9]*\)\.[0-9][0-9]*\].*/\1/p'; }
collect_events() {
    dmesg | awk '/n71-sn2400-trial:/ {
       # New APPLIED begins a new lease epoch. Previous RESTORE is expected.
       if (index($0,"APPLIED input_uA=300000")) { applied=$0; monitor=""; failure=""; }
       if (index($0,"MONITOR VBUS_uV=")) monitor=$0;
       if (index($0,"MONITOR_STOP") || index($0,"RESTORE") || index($0,"ROLLBACK_FAILED")) failure=$0;
    } END {print "APPLIED|" applied;print "MONITOR|" monitor;print "FAILURE|" failure}'
}
verify_immutable() {
    [ "$(id -u)" = 0 ] || die 'requires root on phone'
    [ -f "$DEVICE_MODULE" ] && [ ! -L "$DEVICE_MODULE" ] || die 'module missing or symlink'
    sha=$(sha256sum "$DEVICE_MODULE" | awk '{print $1}')
    [ "$sha" = "$EXPECTED_SHA" ] || die 'module digest mismatch'
    case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) ;; *) die 'unqualified kernel' ;; esac
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,n71 || die 'board not N71'
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,s8000 || die 'SoC not S8000'
    [ "$(cat /sys/class/udc/20c100000.usbdev/state)" = configured ] || die 'USB disconnected'
    grep -q '^n71_sn2400_input_trial ' /proc/modules || die 'SN2400 module missing'
    [ "$(cat /sys/module/n71_sn2400_input_trial/parameters/armed)" = Y ] || die 'charger not armed'
    [ "$(cat /sys/module/n71_sn2400_input_trial/parameters/input_ua)" = "$INPUT_UA" ] || die 'charger input mismatch'
    [ "$(cat /sys/module/n71_sn2400_input_trial/parameters/lease_seconds)" = "$LEASE_SECONDS" ] || die 'charger deadman missing'
}
verify_battery() {
    root=/sys/class/power_supply/bq27540-0
    cap=$(read_number "$root/capacity")
    temp=$(read_number "$root/temp")
    volt=$(read_number "$root/voltage_now")
    status=$(cat "$root/status")
    [ "$cap" -ge "$MIN_RENEW_CAPACITY" ] && [ "$cap" -le 100 ] || die 'battery capacity outside safe bounds'
    [ "$temp" -ge 100 ] && [ "$temp" -lt 390 ] || die 'battery temp outside safe bounds'
    [ "$volt" -ge 3600000 ] && [ "$volt" -lt "$MAX_RENEW_VOLTAGE_UV" ] || die 'voltage too near unknown cell limit'
    # A gauge may briefly report Not charging near zero net cell current.
    # It is not proof of a failed VBUS monitor; no current target is raised.
    case "$status" in Charging|Discharging|"Not charging") ;; *) die "unexpected battery status $status" ;; esac
}
verify_monitor() {
    now=$(awk '{print int($1)}' /proc/uptime)
    events=$(collect_events)
    applied=$(printf '%s\n' "$events" | grep '^APPLIED|' | cut -c9-)
    monitor=$(printf '%s\n' "$events" | grep '^MONITOR|' | cut -c9-)
    failure=$(printf '%s\n' "$events" | grep '^FAILURE|' | cut -c9-)
    case "$applied" in *"APPLIED input_uA=300000"*"automatic_restore_ms=3600000"*) ;; *) die 'no active 300mA lease proof' ;; esac
    case "$monitor" in *"MONITOR VBUS_uV="*"input_uA=300000"*) ;; *) die 'no live charger monitor proof' ;; esac
    applied_s=$(event_sec "$applied")
    monitor_s=$(event_sec "$monitor")
    [ -n "$applied_s" ] && [ -n "$monitor_s" ] || die 'unreadable kernel timestamps'
    age=$((now-applied_s))
    freshness=$((now-monitor_s))
    [ "$age" -ge 0 ] && [ "$age" -lt "$LEASE_SECONDS" ] || die 'lease is expired or uptime reset'
    [ "$freshness" -ge 0 ] && [ "$freshness" -le 15 ] || die 'charger monitor telemetry stale'
    [ "$monitor_s" -ge "$applied_s" ] || die 'monitor precedes lease'
    if [ -n "$failure" ]; then
        failure_s=$(event_sec "$failure")
        [ -n "$failure_s" ] || die 'fault timestamp unreadable'
        [ "$failure_s" -lt "$applied_s" ] || die 'hardware rolled back charger'
    fi
    echo "CHARGE_SUPERVISOR_PASS capacity=${cap}% voltage_uV=$volt temp_tenths=$temp lease_age_s=$age monitor_fresh_s=$freshness status=$status"
}
perform_one_renewal() {
    [ "$age" -lt $((LEASE_SECONDS-120)) ] || die 'too close to lease expiration'
    [ "$volt" -lt "$MAX_RENEW_VOLTAGE_UV" ] || die 'voltage guard at renewal'
    echo 'CHARGE_SUPERVISOR_RENEW_START'
    rmmod n71_sn2400_input_trial || die 'module unload failed; do not rearm'
    # No rearm after unsuccessful restore. The last charger event must be
    # a verified baseline restoration from this module unload.
    restore=$(dmesg | grep 'n71-sn2400-trial:' | tail -1)
    case "$restore" in *'RESTORE reason=module-exit input=00 rc=0'*) ;; *) die 'module baseline restoration not proven' ;; esac
    # Check the battery again before altering any current-limit register.
    verify_battery
    [ "$(cat /sys/class/udc/20c100000.usbdev/state)" = configured ] || die 'USB lost before rearm'
    /usr/bin/n71-module-once "$DEVICE_MODULE" 'armed=1 input_ua=300000 lease_seconds=3600' || die 'charger module rearm failed'
    sleep 4
    verify_immutable
    verify_battery
    verify_monitor
    [ "$age" -le 10 ] || die 'unexpected renewed lease timestamp'
    echo 'CHARGE_SUPERVISOR_RENEW_CONFIRMED'
}
cycle() {
    verify_immutable
    verify_battery
    verify_monitor
    if [ "$MODE" = --renew-now ] || { [ "$MODE" = --supervise ] && [ "$age" -ge "$REFRESH_AT_AGE" ]; }; then
        perform_one_renewal
    fi
}
case "$MODE" in --check|--renew-now|--supervise) ;; *) die 'usage: --check | --renew-now | --supervise' ;; esac
# The lock is required for all modes: never race two module reloads.
exec 9>"$LOCKFILE"
flock -n 9 || die 'another charging supervisor holds lock'
if [ "$MODE" = --supervise ]; then
    echo 'CHARGE_SUPERVISOR_START'
    while :; do
        cycle >>"$LOG" 2>&1 || die 'renewal cycle rejected'
        sleep 60
    done
else
    cycle
fi
