#!/bin/sh
# SPDX-License-Identifier: MIT
# N71 batt2 RAM boot: once-only, hash-pinned charging + Bluetooth startup.
set -u
case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) ;; *) echo SKIP_KERNEL; exit 0;; esac
[ -r /proc/device-tree/compatible ] || { echo SKIP_BOARD; exit 0; }
for board in apple,n71 apple,s8000; do
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board" || exit 1
done
[ ! -e /run/n71_runtime_attempted ] || { echo ALREADY_ATTEMPTED; exit 1; }
: >/run/n71_runtime_attempted
sha256sum -c /usr/lib/cyberdeck/n71-runtime.sha256 > /run/n71_runtime_hashes.log 2>&1 || {
    echo HASH_CHECK_FAILED; exit 1
}
# Wait for host enumeration; do not increase current while still unconfigured.
i=0
while [ "$(cat /sys/class/udc/20c100000.usbdev/state 2>/dev/null)" != configured ]; do
    i=$((i + 1))
    [ "$i" -lt 15 ] || { echo USB_NOT_CONFIGURED; exit 1; }
    sleep 1
done
/usr/bin/n71-module-once /usr/lib/cyberdeck/gpio-apple-pmic.ko
printf 'PMIC_GPIO_LOAD_RC=%s\n' "$?"
/usr/bin/n71-module-once /usr/lib/cyberdeck/n71-sn2400-input-trial.ko     'armed=1 input_ua=300000 lease_seconds=3600'
printf 'CHARGER_LOAD_RC=%s\n' "$?"
# Patchram setup is asynchronous; wait for the already validated build.
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
echo RUNTIME_STARTUP_FINISHED_PCIE_NOT_ACTIVATED
