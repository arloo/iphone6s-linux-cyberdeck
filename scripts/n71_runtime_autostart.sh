#!/bin/sh
# SPDX-License-Identifier: MIT
# N71/S8000 batt2 RAM boot: nonblocking PMIC and Bluetooth initialization.
# Only a detached, one-shot worker may arm a bounded SN2400 input trial.
# The independent kernel VBUS/thermal/lease rollback is never bypassed.
set -u
MODE=${1:---boot}
case "$MODE" in --boot|--charge-worker) : ;; *) echo UNSUPPORTED_STARTUP_MODE; exit 2 ;; esac
case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) : ;; *) echo SKIP_KERNEL; exit 0 ;; esac
[ -r /proc/device-tree/compatible ] || { echo SKIP_BOARD; exit 0; }
for board in apple,n71 apple,s8000; do
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board" || exit 1
done
UDC=/sys/class/udc/20c100000.usbdev/state
BAT=/sys/class/power_supply/bq27540-0
if [ "$MODE" = --charge-worker ]; then
    [ -e /run/n71_runtime_attempted ] || { echo STARTUP_NOT_CONFIRMED_SKIP_CHARGER; exit 1; }
    mkdir /run/n71_charge_worker_started 2>/dev/null || {
        echo CHARGER_WORKER_ALREADY_ATTEMPTED; exit 0;
    }
    sha256sum -c /usr/lib/cyberdeck/n71-runtime.sha256 \
        > /run/n71_charge_hashes.log 2>&1 || {
        echo WORKER_HASH_CHECK_FAILED; exit 1;
    }
# The previously observed USB gadget was rebound at boot uptime ~28 seconds.
# Require >=45 seconds total uptime plus 15 consecutive configured samples.
# A disconnect resets stability. Maximum 120 attempts; never bypass VBUS guard.
i=0
stable=0
while [ "$i" -lt 120 ] && [ "$stable" -lt 15 ]; do
    uptime_s=$(cut -d. -f1 /proc/uptime 2>/dev/null)
    case "$uptime_s" in ''|*[!0-9]*) echo USB_UPTIME_UNAVAILABLE_SKIP_CHARGER; exit 1 ;; esac
    if [ "$uptime_s" -ge 45 ] && [ "$(cat "$UDC" 2>/dev/null)" = configured ]; then
        stable=$((stable + 1))
    else
        stable=0
    fi
    i=$((i + 1))
    [ "$stable" -ge 15 ] || sleep 1
done
if [ "$stable" -lt 15 ]; then
    echo USB_STABILITY_TIMEOUT_SKIP_CHARGER
        exit 0
fi
echo USB_POST_ENUMERATION_STABILITY_CONFIRMED
# Independent guards are stricter than the kernel's 10%-to-4.2V emergency
# safety bounds. High SOC/voltage is normal after iOS reached 100%: skip it.
# iOS may hand over the phone at 100%/4.22 V. Observe at most 20 minutes
# for a safe charging window without touching SN2400 while voltage is high.
# If UDC drops, battery becomes unsafe or the window never arrives, skip.
window_checks=0
while [ "$window_checks" -lt 40 ]; do
    if [ "$(cat "$UDC" 2>/dev/null)" != configured ]; then
        echo USB_LOST_BEFORE_CHARGE_SKIP
        exit 0
    fi
    capacity=$(cat "$BAT/capacity" 2>/dev/null)
    temp=$(cat "$BAT/temp" 2>/dev/null)
    voltage=$(cat "$BAT/voltage_now" 2>/dev/null)
    health=$(cat "$BAT/health" 2>/dev/null)
    case "$capacity:$temp:$voltage" in
        *[!0-9:]*|::*|*:|:*) echo BATTERY_GAUGE_INVALID_SKIP_CHARGER; exit 0 ;;
    esac
    if [ "$capacity" -lt 35 ] || [ "$temp" -lt 100 ] || \
       [ "$temp" -ge 375 ] || [ "$voltage" -lt 3500000 ] || \
       [ "$health" != Good ]; then
        echo "BATTERY_GUARD_SKIP_CHARGER cap=$capacity temp_tenths=$temp voltage_uV=$voltage"
        exit 0
    fi
    if [ "$capacity" -lt 99 ] && [ "$voltage" -lt 4150000 ]; then
        echo "N71_SAFE_CHARGE_WINDOW_CONFIRMED cap=$capacity temp_tenths=$temp voltage_uV=$voltage"
        break
    fi
    window_checks=$((window_checks + 1))
    [ "$window_checks" -lt 40 ] || break
    sleep 30
done
if [ "$window_checks" -ge 40 ]; then
    echo HIGH_SOC_WINDOW_TIMEOUT_SKIP_CHARGER
    exit 0
fi
# One 300 mA input-current lease, max 3600 seconds. This never implies
# 300 mA net battery current. SN2400 retains its independent VBUS/thermal
# monitoring and automatic restoration at the first bad sample.
if grep -q '^n71_sn2400_input_trial ' /proc/modules; then
    echo CHARGER_MODULE_ALREADY_PRESENT_NO_REARM
    exit 0
fi
if /usr/bin/n71-module-once /usr/lib/cyberdeck/n71-sn2400-input-trial.ko \
    'armed=1 input_ua=300000 lease_seconds=3600'; then
    echo CHARGER_LOAD_RC=0
else
    echo CHARGER_LOAD_FAILED_NO_RETRY
    exit 1
fi
    exit 0
fi
# Main /init path must return promptly. The 20-minute high-SOC observation
# belongs only to the detached worker and never blocks touch/USB/UI setup.
[ ! -e /run/n71_runtime_attempted ] || { echo ALREADY_ATTEMPTED; exit 1; }
: > /run/n71_runtime_attempted
sha256sum -c /usr/lib/cyberdeck/n71-runtime.sha256 \
    > /run/n71_runtime_hashes.log 2>&1 || { echo HASH_CHECK_FAILED; exit 1; }
i=0
while [ "$(cat "$UDC" 2>/dev/null)" != configured ]; do
    i=$((i + 1))
    [ "$i" -lt 15 ] || { echo USB_NOT_CONFIGURED; exit 1; }
    sleep 1
done
if /usr/bin/n71-module-once /usr/lib/cyberdeck/gpio-apple-pmic.ko; then
    echo PMIC_GPIO_LOAD_RC=0
else
    echo PMIC_GPIO_LOAD_FAILED_SKIP_CHARGER
    exit 1
fi
# Bluetooth startup is independent of the charging preflight.
i=0
while ! dmesg | grep -q 'BCM4350C5 (003.006.007) build 0825'; do
    i=$((i + 1))
    [ "$i" -lt 20 ] || break
    sleep 1
done
if [ -d /sys/class/bluetooth/hci0 ]; then
    /usr/bin/n71-hci-probe up
else
    echo HCI_NOT_PRESENT
fi
/usr/bin/n71-battery-status
if [ ! -x /usr/bin/nohup ] || [ ! -x /usr/bin/setsid ]; then
    echo DETACHED_CHARGE_RUNNER_UNAVAILABLE_SKIP_CHARGER
else
    /usr/bin/nohup /usr/bin/setsid /bin/sh /usr/bin/n71-runtime-autostart --charge-worker \
    > /run/n71_charge_monitor.log 2>&1 < /dev/null &
    echo CHARGER_WORKER_SPAWNED
fi
echo RUNTIME_STARTUP_FINISHED_PCIE_NOT_ACTIVATED
