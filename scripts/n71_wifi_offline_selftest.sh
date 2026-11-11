#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# OFFLINE-ONLY end-to-end N71 A9 BCM4350 readiness preflight.
# No USB commands, phone, NAND, MMIO, DMA or radio access.
set -euo pipefail
if [[ "$#" -ne 8 ]];then
  echo "Usage: n71_wifi_offline_selftest.sh PRIVATE_MACHO PRIVATE_ADT BASE_CONFIG WIFI_CONFIG BASE_MODULE_SYMVERS PRIVATE_WIFI_BUILD_DIR PRIVATE_FIRMWARE_SOURCE PRIVATE_FIRMWARE_STAGING" >&2
  exit 2
fi
HERE="$(cd "$(dirname "$0")/.." && pwd -P)"
for required in python3 aarch64-linux-gnu-readelf modinfo;do
 if ! command -v "$required" >/dev/null 2>&1;then
   echo "N71_WIFI_OFFLINE_PREFLIGHT_BLOCKED_MISSING_TOOL" >&2
   exit 3
 fi
done
KERNEL="$1"
ADT="$2"
BASE="$3"
WIFI="$4"
SYMVERS="$5"
BUILD="$6"
FIRMWARE_SOURCE="$7"
FIRMWARE_STAGE="$8"
for file in "$KERNEL" "$ADT" "$BASE" "$WIFI" "$SYMVERS";do
 if [[ ! -f "$file" || -L "$file" ]];then
   echo "N71_WIFI_OFFLINE_PREFLIGHT_BLOCKED_MISSING_FILE" >&2
   exit 4
 fi
done
for dir in "$BUILD" "$FIRMWARE_SOURCE" "$FIRMWARE_STAGE";do
 if [[ ! -d "$dir" || -L "$dir" ]];then
   echo "N71_WIFI_OFFLINE_PREFLIGHT_BLOCKED_MISSING_PRIVATE_DIR" >&2
   exit 5
 fi
done
python3 "$HERE/tools/n71_s8000_adt_window_gate.py" "$ADT" >/dev/null
echo "N71_WIFI_PREFLIGHT_ORIGINAL_ADT_DART1_TOPOLOGY_PASS"
python3 "$HERE/tools/n71_s8000_root_resource_gate.py" "$KERNEL" "$ADT" >/dev/null
echo "N71_WIFI_PREFLIGHT_ORIGINAL_ROOT_CONSTRUCTOR_RESOURCES_PASS"
python3 "$HERE/tools/n71_s8000_provider_order_gate.py" "$ADT" >/dev/null
echo "N71_WIFI_PREFLIGHT_PROVIDER_ORDER_ADT_ONLY_PASS_RUNTIME_UNVERIFIED"
python3 "$HERE/tools/n71_wifi_kernel_baseline_gate.py" "$BASE" "$WIFI" >/dev/null
echo "N71_WIFI_PREFLIGHT_ORIGINAL_TOUCH_DISPLAY_USB_CONFIG_PRESERVED_PASS"
python3 "$HERE/tools/n71_bcm4350_firmware_integrity_gate.py" \
 --original-private-source "$FIRMWARE_SOURCE" \
 --private-linux-staging "$FIRMWARE_STAGE" >/dev/null
echo "N71_WIFI_PREFLIGHT_PRIVATE_C2_C5_HASH_INTEGRITY_PASS"

C="$BUILD/net/wireless/cfg80211.o"
U="$BUILD/drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.o"
B="$BUILD/drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.o"
G="$BUILD/drivers/gpio/gpio-apple-pmic.o"

python3 "$HERE/tools/n71_wifi_kernel_symbol_gate.py" \
 "$SYMVERS" "$C" "$U" "$B" "$G" >/dev/null
echo "N71_WIFI_PREFLIGHT_RADIO_SYMBOL_COVERAGE_SINGLE_KNOWN_PKCS7_BLOCKER"

# Two already-linked modules: only compare metadata; NEVER load them.
VERSION_FILE="$BUILD/include/generated/utsrelease.h"
[[ -f "$VERSION_FILE" ]] || {
 echo "N71_WIFI_PREFLIGHT_BLOCKED_KERNEL_VERSION_UNKNOWN" >&2; exit 6;
}
EXPECTED=$(sed -n 's/^#define UTS_RELEASE "\([^"]*\)"/\1/p' "$VERSION_FILE")
[[ -n "$EXPECTED" ]] || {
 echo "N71_WIFI_PREFLIGHT_BLOCKED_KERNEL_VERSION_UNKNOWN" >&2; exit 6;
}
for mod in \
 "$BUILD/drivers/gpio/gpio-apple-pmic.ko" \
 "$BUILD/drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.ko";do
 if [[ ! -s "$mod" ]];then
  echo "N71_WIFI_PREFLIGHT_BLOCKED_MISSING_LINKED_MODULE" >&2;exit 7
 fi
 LC_ALL=C aarch64-linux-gnu-readelf -h "$mod" | grep -q 'Machine:.*AArch64' || {
  echo "N71_WIFI_PREFLIGHT_BLOCKED_NON_ARM64_MODULE" >&2;exit 8;
 }
 VM=$(modinfo -F vermagic "$mod")
 case "$VM" in
  "$EXPECTED "*) : ;;
  *) echo "N71_WIFI_PREFLIGHT_BLOCKED_ABI_VERSION" >&2;exit 9;;
 esac
done
echo "N71_WIFI_PREFLIGHT_TWO_ARM64_KO_VERMAGIC_PASS"
echo "N71_WIFI_OFFLINE_PREFLIGHT_COMPLETE"
echo "STILL_BLOCKED: kernel_PKCS7_export, physical_S8000_PCIe_port1, DART1_DMA, actual_BCM4350_communication"
echo "NO_HARDWARE_ACCESS_NO_WIFI_CLAIM_NO_PRIVATE_FILE_EXPORT"
