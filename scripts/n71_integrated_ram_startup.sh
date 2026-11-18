#!/bin/sh
# SPDX-License-Identifier: MIT
# Candidate-only RAM boot hook. Private archive contains credentials and bond keys.
set -eu
umask 077
case "$(uname -r)" in 7.3.0-rc1-n71-batt2-*) ;; *) exit 1;; esac
for board in apple,n71 apple,s8000; do
 tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board"
done
mkdir -p /run
mkdir /run/n71-integrated-attempted 2>/dev/null || exit 1
sha256sum -c /usr/lib/cyberdeck/n71-integrated.sha256 > /run/n71-integrated-hash-PRIVATE.log 2>&1
# The complete operator-built archive is pinned above; never extract an unverified input.
tar -xzf /usr/lib/cyberdeck/n71-integrated-runtime-PRIVATE.tar.gz -C /
# A working USB SSH recovery path must not depend on WLAN/BlueZ startup.
# Launch asynchronously: original USB recovery remains available if this fails.
if [ -x /usr/bin/n71-ssh-provision-ram ]; then
    (
        attempts=0
        until ip -4 addr show dev usb0 2>/dev/null | grep -q 'inet 172.16.42.1/'; do
            attempts=$((attempts + 1))
            [ "$attempts" -lt 45 ] || exit 1
            sleep 1
        done
        /bin/sh /usr/bin/n71-ssh-provision-ram
    ) </dev/null > /run/n71-ssh-bootstrap-PRIVATE.log 2>&1 &
    echo "$!" > /run/n71-ssh-bootstrap.pid
fi
/bin/sh /usr/bin/n71-connectivity-autostart > /run/n71-connectivity-autostart-PRIVATE.log 2>&1
N71_DISPLAY_ACTION=apply /bin/sh /usr/bin/n71-balanced-display > /run/n71-display-profile.log 2>&1
# Optional verified RAM-only splash; never delay or block debug/USB recovery
# when the artwork is absent or the framebuffer write fails.
if [ -x /usr/bin/n71-boot-splash ]; then
    /bin/sh /usr/bin/n71-boot-splash > /run/n71-boot-splash.log 2>&1 || true
fi
# Physical visual test: a three-second splash could be missed. Give a
# successfully rendered Showcase splash eight visible seconds, then start
# the original touchscreen UI. Debug/no-splash retains its three-second handoff.
if grep -qx 'N71_SPLASH_DISPLAYED_RAM_ONLY' /run/n71-boot-splash.log 2>/dev/null; then
    n71_ui_delay=8
else
    n71_ui_delay=3
fi
( sleep "$n71_ui_delay"; exec /run/n71-cyberdeck-shell ) </dev/null > /run/n71-ui-runtime-PRIVATE.log 2>&1 &
echo "$!" > /run/n71-cyberdeck-shell.pid
echo "N71_UI_HANDOFF_DELAY=${n71_ui_delay}s"
printf 'N71_INTEGRATED_SERVICES_READY_UI_SCHEDULED\n'
