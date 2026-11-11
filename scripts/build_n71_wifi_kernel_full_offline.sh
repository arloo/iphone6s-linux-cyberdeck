#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build a SEPARATE complete N71 ARM64 Wi-Fi kernel + modules, OFFLINE ONLY.
# Arguments: PINNED_LINUX_SOURCE KNOWN_GOOD_CONFIG KNOWN_GOOD_IMAGE FRESH_PRIVATE_OUTPUT
# Does not create a bootable m1n1/initramfs bundle, access an iPhone, publish
# private firmware, modify the trusted boot, or enable experimental PCIe.
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: build_n71_wifi_kernel_full_offline.sh LINUX_SOURCE BASE_CONFIG BASE_IMAGE FRESH_PRIVATE_OUT" >&2
  exit 2
fi

HERE="$(cd "$(dirname "$0")" && pwd -P)"
SRC="$(realpath -e -- "$1")"
CONFIG="$(realpath -e -- "$2")"
TRUSTED_IMAGE="$(realpath -e -- "$3")"
OUT="$(realpath -m -- "$4")"

if [[ ! -f "$TRUSTED_IMAGE" || -L "$3" || ! -f "$CONFIG" ||
      -L "$2" || ! -d "$SRC" || -L "$1" ]];then
  echo "N71_WIFI_FULL_BUILD_BLOCKED: untrusted baseline or source" >&2
  exit 3
fi
if [[ -e "$OUT" || -L "$OUT" ]]; then
  echo "N71_WIFI_FULL_BUILD_BLOCKED: output must be a NEW private directory" >&2
  exit 4
fi
if [[ "$OUT" == "$SRC" || "$OUT/" == "$SRC/"* ||
      "$OUT" == "$(dirname "$TRUSTED_IMAGE")" ]];then
  echo "N71_WIFI_FULL_BUILD_BLOCKED: cannot overwrite original Linux source/image" >&2
  exit 5
fi

# This generates an OUT-OF-TREE config and four independent AArch64
# relocatable module objects before starting the full kernel compilation.
"$HERE/build_n71_wifi_objects_offline.sh" "$SRC" "$CONFIG" "$OUT"

# Fail closed if anyone reused a previous kernel vmlinux object via symlink.
if [[ -L "$OUT/vmlinux.o" || -L "$OUT/vmlinux" ||
      -L "$OUT/arch/arm64/boot/Image" ||
      -L "$OUT/Module.symvers" ]];then
  echo "N71_WIFI_FULL_BUILD_BLOCKED: cross-build output alias detected" >&2
  exit 6
fi

make -s -j2 -C "$SRC" O="$OUT" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- Image modules

python3 "$HERE/../tools/n71_wifi_alternate_kernel_gate.py" \
  "$TRUSTED_IMAGE" "$CONFIG" "$OUT"

echo "N71_WIFI_FULL_ALT_ARM64_BUILD_AND_STATIC_MODULE_GATE_PASS"
echo "S8000_PCIE_DART1_AND_WIFI_HARDWARE_STILL_UNVERIFIED"
echo "NO_NEW_BOOTABLE_RAM_BUNDLE_OR_DEVICE_ACCESS"
