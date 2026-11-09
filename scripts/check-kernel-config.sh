#!/bin/sh
# Run on a Linux build host. Prints whether expected options are enabled.
set -eu
CFG="${1:-}"
if [ -z "$CFG" ] || [ ! -f "$CFG" ]; then
  echo "Usage: $0 /path/to/kernel/.config" >&2
  exit 2
fi
for key in INPUT_TOUCHSCREEN TOUCHSCREEN_APPLE_Z2 SPI SPI_APPLE WLAN CFG80211 MAC80211 BRCMFMAC PCIE_APPLE BT BT_BCM BT_HCIUART BT_HCIUART_BCM FW_LOADER; do
  line=$(grep -E "^(CONFIG_${key}=|# CONFIG_${key} is not set)" "$CFG" | head -1 || true)
  if [ -z "$line" ]; then line="CONFIG_${key}: absent or not selected"; fi
  printf '%-30s %s\n' "$key" "$line"
done
