#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Repeatable OFFLINE ONLY Apple N71 ARM64 Wi-Fi object build.
# Arguments: LINUX_SOURCE_TREE BASELINE_KERNEL_CONFIG FRESH_PRIVATE_OUT_DIR
# No access to phone, GPIO, PCIe, DART, NAND, boot image or private firmware.
set -euo pipefail
if [[ $# -ne 3 ]]; then
  echo "Usage: build_n71_wifi_objects_offline.sh LINUX_TREE BASELINE_CONFIG NEW_PRIVATE_OUT" >&2
  exit 2
fi
SRC="$(realpath -e -- "$1")"
BASE="$(realpath -e -- "$2")"
OUT="$(realpath -m -- "$3")"
REPO="$(realpath -e -- "$(dirname "$0")/..")"

if [[ ! -f "$SRC/Makefile" || ! -x "$SRC/scripts/config" ||
      ! -f "$SRC/drivers/gpio/gpio-apple-pmic.c" ||
      ! -f "$SRC/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c" ]]; then
  echo "OFFLINE_WIFI_BUILD_BLOCKED: expected source tree missing" >&2
  exit 3
fi
case "$OUT/" in
  "$REPO/"*|"$SRC/"* )
    echo "OFFLINE_WIFI_BUILD_BLOCKED: output inside a source/public tree" >&2
    exit 4 ;;
esac
if [[ -e "$OUT" || -L "$OUT" ]]; then
  echo "OFFLINE_WIFI_BUILD_BLOCKED: output already exists" >&2
  exit 5
fi
for setting in CONFIG_ARCH_APPLE=y CONFIG_MODULES=y CONFIG_PCI=y CONFIG_APPLE_DART=y; do
  if ! grep -Fxq -- "$setting" "$BASE"; then
    echo "OFFLINE_WIFI_BUILD_BLOCKED: incompatible ARM64 Apple kernel baseline" >&2
    exit 6
  fi
done
for exe in aarch64-linux-gnu-gcc aarch64-linux-gnu-readelf; do
  if ! command -v "$exe" >/dev/null 2>&1; then
    echo "OFFLINE_WIFI_BUILD_BLOCKED: cross compiler missing" >&2
    exit 7
  fi
done

install -d -m 700 -- "$OUT"
cp -- "$BASE" "$OUT/.config"
chmod 600 "$OUT/.config"

"$SRC/scripts/config" --file "$OUT/.config" \
  -e WIRELESS -e WLAN -e NETDEVICES \
  -m CFG80211 -m BRCMFMAC -m BRCMUTIL \
  -e BRCMFMAC_PCIE -e FW_LOADER \
  -d BRCMFMAC_SDIO -d BRCMFMAC_USB
make -s -C "$SRC" O="$OUT" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- olddefconfig

for setting in CONFIG_WIRELESS=y CONFIG_WLAN=y CONFIG_CFG80211=m \
               CONFIG_BRCMFMAC=m CONFIG_BRCMUTIL=m \
               CONFIG_BRCMFMAC_PCIE=y CONFIG_APPLE_DART=y; do
  if ! grep -Fxq -- "$setting" "$OUT/.config"; then
    echo "OFFLINE_WIFI_BUILD_BLOCKED: a required Kconfig feature is unavailable" >&2
    exit 8
  fi
done

make -s -j2 -C "$SRC" O="$OUT" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- prepare
make -s -j2 -C "$SRC" O="$OUT" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- \
  drivers/gpio/gpio-apple-pmic.o \
  net/wireless/cfg80211.o \
  drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.o \
  drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.o

for obj in \
  drivers/gpio/gpio-apple-pmic.o \
  net/wireless/cfg80211.o \
  drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.o \
  drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.o; do
  if [[ ! -s "$OUT/$obj" ]] ||
     ! LC_ALL=C aarch64-linux-gnu-readelf -h "$OUT/$obj" |
       grep -q 'Machine:.*AArch64'; then
    echo "OFFLINE_WIFI_BUILD_BLOCKED: ARM64 kernel object validation failed" >&2
    exit 9
  fi
done
echo "N71_BCM4350_GPIO_CFG80211_BRCMUTIL_BRCMFMAC_ARM64_OBJECT_BUILD_PASS"
echo "ARM64_OBJECT_COUNT=4"
echo "N71_PCIE_DART1_AND_NATIVE_WLAN_NOT_VALIDATED"
echo "NO_DEVICE_ACCESS_NO_PRIVATE_FIRMWARE_NO_BOOT_IMAGE"
