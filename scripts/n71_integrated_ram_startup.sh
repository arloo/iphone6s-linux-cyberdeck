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
/bin/sh /usr/bin/n71-connectivity-autostart > /run/n71-connectivity-autostart-PRIVATE.log 2>&1
N71_DISPLAY_ACTION=apply /bin/sh /usr/bin/n71-balanced-display > /run/n71-display-profile.log 2>&1
# Give the original init/getty handoff time to finish before owning the display.
/bin/sh -c 'sleep 3; exec /run/n71-cyberdeck-shell' </dev/null > /run/n71-ui-runtime-PRIVATE.log 2>&1 &
echo "$!" > /run/n71-cyberdeck-shell.pid
printf 'N71_INTEGRATED_SERVICES_READY_UI_SCHEDULED\n'
