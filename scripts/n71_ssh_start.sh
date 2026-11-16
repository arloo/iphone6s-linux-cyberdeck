#!/bin/sh
# SPDX-License-Identifier: MIT
# Start a pinned, key-only recovery server on the USB gadget address only.
set -eu
umask 077
for board in apple,n71 apple,s8000; do
 tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board"
done
mkdir -p /run
sha256sum -c /usr/lib/cyberdeck/n71-ssh.sha256 > /run/n71-ssh-hashes-PRIVATE.log 2>&1
if [ -r /run/n71-dropbear.pid ]; then
 pid=$(cat /run/n71-dropbear.pid)
 case "$pid" in ''|*[!0-9]*) exit 1;; esac
 if [ "$(readlink /proc/$pid/exe 2>/dev/null)" = /usr/bin/n71-dropbear ]; then
  printf 'N71_SSH_ALREADY_RUNNING\n';exit 0
 fi
fi
# Password, PAM, forwarding and SFTP support are compiled out as well as disabled here.
/usr/bin/n71-dropbear -F -r /usr/lib/cyberdeck/ssh/host_ed25519 \
 -p 172.16.42.1:22 -s -j -k -T 3 -P /run/n71-dropbear.pid \
 </dev/null > /run/n71-dropbear-PRIVATE.log 2>&1 &
echo "$!" > /run/n71-dropbear.pid
sleep 1
kill -0 "$(cat /run/n71-dropbear.pid)"
printf 'N71_SSH_USB_SERVICE_STARTED\n'
