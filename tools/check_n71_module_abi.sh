#!/bin/sh
# SPDX-License-Identifier: MIT
# Offline check: prevent mixing an experimental module and unrelated kernel.
# The expected release must come from the target kernel, NOT the build host.
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <module.ko> <target-kernel-release>" >&2
  exit 2
fi
MODULE="$1"
RELEASE="$2"
[ -s "$MODULE" ] || { echo "FAIL: module missing" >&2; exit 1; }
command -v modinfo >/dev/null 2>&1 ||
  { echo "FAIL: modinfo unavailable" >&2; exit 1; }
VERMAGIC=$(modinfo -F vermagic "$MODULE") ||
  { echo "FAIL: cannot read module vermagic" >&2; exit 1; }
case "$VERMAGIC" in
  "$RELEASE "*)
    echo "PASS: module release matches requested target kernel"
    echo "NOTE: identical release strings do not guarantee a safe driver or ABI."
    ;;
  *)
    echo "FAIL: module vermagic does not match target release" >&2
    exit 1
    ;;
esac
