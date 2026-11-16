#!/bin/sh
# SPDX-License-Identifier: MIT
# Owner-private image supplies an authorized public key, not an SSH host secret.
# Generate a unique host key on the iPhone RAM filesystem on each fresh boot.
set -eu
umask 077
for board in apple,n71 apple,s8000; do
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx "$board"
done
[ -x /usr/bin/n71-dropbear ] && [ -x /usr/bin/n71-dropbearkey ] &&
[ -x /usr/bin/n71-ssh-start ] && [ -s /root/.ssh/authorized_keys ]
mkdir -p /run /usr/lib/cyberdeck/ssh
chmod 700 /root /root/.ssh /usr/lib/cyberdeck/ssh
chmod 600 /root/.ssh/authorized_keys
if [ ! -s /usr/lib/cyberdeck/ssh/host_ed25519 ]; then
    /usr/bin/n71-dropbearkey -t ed25519 \
        -f /usr/lib/cyberdeck/ssh/host_ed25519 \
        > /run/n71-ssh-keygen-PRIVATE.log 2>&1
fi
chmod 600 /usr/lib/cyberdeck/ssh/host_ed25519
sha256sum /usr/bin/n71-dropbear \
          /usr/bin/n71-dropbearkey \
          /usr/bin/n71-ssh-start \
          /root/.ssh/authorized_keys \
          /usr/lib/cyberdeck/ssh/host_ed25519 \
          > /usr/lib/cyberdeck/n71-ssh.sha256
chmod 600 /usr/lib/cyberdeck/n71-ssh.sha256
exec /bin/sh /usr/bin/n71-ssh-start
