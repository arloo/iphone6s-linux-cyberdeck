#!/bin/sh
# SPDX-License-Identifier: MIT
# Owner-attended N71/S8000 low-SOC recovery: a single bounded 300 mA
# input-current lease, not a replacement for the >=35% normal supervisor.
# Runs on iPhone Linux as root. No storage/NAND/MMIO/DART access.
# Host must independently verify USB configuration <=500 mA.
set -eu
umask 077

MODE=${1:---check}
MODULE=/usr/lib/cyberdeck/n71-sn2400-input-trial.ko
EXPECTED_SHA=06b497deb2baf3724fe3d03f72870df2910d40b27afd71e176df52f2358aafea
LOCK=/run/n71-charge-supervisor.lock
BAT=/sys/class/power_supply/bq27540-0
PARAM=/sys/module/n71_sn2400_input_trial/parameters
LEASE_SECONDS=600
TEMP_TRIP_TENTHS=375  # Stop at 37.5 C; operator max 38 C
REQUIRED_INPUT_UA=300000
MIN_CAPACITY=20
MAX_CAPACITY=34
MIN_VOLTAGE_UV=3500000
MAX_VOLTAGE_UV=4150000
ACTIVE=0
fail() { printf 'N71_LOW_SOC_RECOVERY_STOP: %s\n' "$*" >&2; exit 2; }
read_num() {
    value=$(cat "$1") || fail "missing metric"
    case "$value" in ''|*[!0-9]*) fail "invalid metric" ;; esac
    printf '%s\n' "$value"
}
loaded() { grep -q '^n71_sn2400_input_trial ' /proc/modules; }
check_battery() {
    capacity=$(read_num "$BAT/capacity")
    temp=$(read_num "$BAT/temp")
    voltage=$(read_num "$BAT/voltage_now")
    health=$(cat "$BAT/health") || fail 'missing battery health'
    [ "$capacity" -ge "$MIN_CAPACITY" ] && [ "$capacity" -le "$MAX_CAPACITY" ] || fail 'outside 20..34% recovery window'
    [ "$temp" -ge 100 ] && [ "$temp" -lt "$TEMP_TRIP_TENTHS" ] || fail 'temperature at/above 37.5C trip'
    [ "$voltage" -ge "$MIN_VOLTAGE_UV" ] && [ "$voltage" -lt "$MAX_VOLTAGE_UV" ] || fail 'battery voltage outside recovery window'
    [ "$health" = Good ] || fail 'battery health not Good'
}
check_platform() {
    [ "$(id -u)" -eq 0 ] || fail 'requires phone root'
    [ -f "$MODULE" ] && [ ! -L "$MODULE" ] || fail 'module missing/symlink'
    sha=$(sha256sum "$MODULE" | awk '{print $1}')
    [ "$sha" = "$EXPECTED_SHA" ] || fail 'module SHA mismatch'
    case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) : ;; *) fail 'unqualified kernel' ;; esac
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,n71 || fail 'not N71'
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,s8000 || fail 'not S8000'
    [ "$(cat /sys/class/udc/20c100000.usbdev/state)" = configured ] || fail 'USB gadget not configured'
    [ -z "$(grep '^n71_s3e' /proc/modules || true)" ] || fail 'storage DMA pilot loaded'
    [ -x /usr/bin/n71-module-once ] || fail 'verified module loader absent'
    check_battery
}
check_expired() {
    loaded || fail 'existing SN2400 module missing'
    [ "$(cat "$PARAM/armed")" = Y ] || fail 'unexpected module mode'
    [ "$(cat "$PARAM/input_ua")" = "$REQUIRED_INPUT_UA" ] || fail 'unexpected old current'
    [ "$(cat "$PARAM/lease_seconds")" = 3600 ] || fail 'unexpected old lease'
    last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1) || fail 'no old charger evidence'
    case "$last" in *'RESTORE reason=lease-expired input=00 rc=0'*) : ;; *)
        fail 'old lease not demonstrably restored to baseline' ;;
    esac
}
cleanup() {
    if [ "$ACTIVE" -eq 1 ]; then
        rmmod n71_sn2400_input_trial || { echo 'N71_RECOVERY_CRITICAL_RMMOD_FAILED: independent module timeout remains armed' >&2; return 1; }
        echo 'N71_RECOVERY_MODULE_REMOVED'
        last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1) || return 1
        case "$last" in *'RESTORE reason=module-exit input=00 rc=0'*) echo 'N71_RECOVERY_BASELINE_RESTORED=PASS' ;; *)
            echo 'N71_RECOVERY_BASELINE_RESTORE_UNCONFIRMED' >&2; return 1 ;;
        esac
        ACTIVE=0
    fi
}
case "$MODE" in --check|--run) : ;; *) fail 'usage: --check | --run' ;; esac
# The host attestation must be supplied only AFTER inspecting the exact
# active USB 2.0 configuration; do not infer amperage from charger type.
[ "${N71_HOST_USB_CONFIG_MAX_MA:-}" = 500 ] || fail 'host verified 500mA configuration required'
exec 9>"$LOCK"
flock -n 9 || fail 'another charging supervisor holds lock'
check_platform
check_expired
echo "N71_RECOVERY_PREFLIGHT_PASS capacity=$capacity temp_tenths=$temp voltage_uV=$voltage host_usb_config_mA=500 max_input_mA=300"
[ "$MODE" = --run ] || exit 0
# This is a deliberate narrowly scoped policy exception to the normal
# >=35% renewal guard. Do not alter any existing supervisor or kernel limits.
rmmod n71_sn2400_input_trial || fail 'cannot unload expired SN2400 module'
[ ! -e "$PARAM/input_ua" ] || fail 'old module did not exit'
check_battery
# Set cleanup before module activation so failure cannot leave an orphan.
trap 'cleanup' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
ACTIVE=1
/usr/bin/n71-module-once "$MODULE" "armed=1 input_ua=300000 lease_seconds=$LEASE_SECONDS" || fail '300mA recovery module arm rejected'
loaded || fail 'module not loaded after arm'
[ "$(cat "$PARAM/lease_seconds")" = "$LEASE_SECONDS" ] || fail 'lease mismatch'
[ "$(cat "$PARAM/input_ua")" = "$REQUIRED_INPUT_UA" ] || fail 'input mismatch'
sleep 4
last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1) || fail 'no new monitor'
case "$last" in *'MONITOR VBUS_uV='*'input_uA=300000'*) : ;; *) fail 'new monitor not observed' ;; esac
echo 'N71_RECOVERY_300MA_ARMED lease_seconds=600 temp_trip_C=37.5 no_nand_writes=YES'
# Stop at 9 minutes, 60 seconds before the kernel hard deadline.
# Every iteration rechecks thermal/cell/status; the module independently
# monitors USB VBUS and battery every 2 seconds and fails closed.
n=0
while [ "$n" -lt 270 ]; do
    sleep 2
    check_battery
    loaded || fail 'charger module disappeared'
    last=$(dmesg | grep 'n71-sn2400-trial:' | tail -1) || fail 'charger log unavailable'
    case "$last" in *'MONITOR_STOP'*|*'RESTORE '*) fail 'module stopped/reverted' ;; esac
    n=$((n+1))
    if [ $((n%15)) -eq 0 ]; then
        net=$(cat "$BAT/current_now") || fail 'current gauge unavailable'
        echo "N71_RECOVERY_MONITOR sec=$((n*2)) cap=$capacity temp_tenths=$temp cell_uA=$net"
    fi
done
echo 'N71_RECOVERY_9MIN_OBSERVATION_COMPLETE'
