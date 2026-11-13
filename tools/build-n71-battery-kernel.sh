#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build an isolated N71 diagnostic kernel; no hardware access or flashing.
set -euo pipefail
if [[ $# != 3 ]]; then
  echo "Usage: $0 KERNEL_SOURCE BASE_BUILD NEW_BUILD" >&2
  exit 2
fi
source_dir=$(realpath "$1")
base_build=$(realpath "$2")
new_build=$(realpath -m "$3")
[[ -f "$base_build/.config" && ! -e "$new_build" ]]
for symbol in BATTERY_BQ27XXX_HDQ_UART MUX_SN2400; do
  [[ $(sed -n "s/^CONFIG_${symbol}=//p" "$base_build/.config") == m ]]
done
cp -a --reflink=auto "$base_build" "$new_build"
"$source_dir/scripts/config" --file "$new_build/.config"   --enable BATTERY_BQ27XXX_HDQ_UART --enable MUX_SN2400   --set-str LOCALVERSION "-n71-batt1"
make -C "$source_dir" O="$new_build" ARCH=arm64   CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -C "$source_dir" O="$new_build" ARCH=arm64   CROSS_COMPILE=aarch64-linux-gnu- -j2 Image modules
"$source_dir/scripts/diffconfig" "$base_build/.config" "$new_build/.config"
sha256sum "$new_build/arch/arm64/boot/Image"
