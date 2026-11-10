#!/bin/sh
# SPDX-License-Identifier: MIT
# Offline-only validation of a compiled Samsung A9/N71 Device Tree.
# It never contacts a phone, modifies a DTB, or touches hardware.
set -eu

usage() {
  echo "Usage: $0 <s8000-n71.dtb> <off|host-only>" >&2
  exit 2
}
[ "$#" -eq 2 ] || usage
DTB="$1"
MODE="$2"
[ -s "$DTB" ] || { echo "FAIL: missing compiled DTB" >&2; exit 1; }
command -v fdtget >/dev/null 2>&1 ||
  { echo "FAIL: install dtc (fdtget)" >&2; exit 1; }
case "$MODE" in
  off) EXPECT=disabled ;;
  host-only) EXPECT=okay ;;
  *) usage ;;
esac

get_s() { fdtget -t s "$DTB" "$1" "$2"; }
get_x() { fdtget -t x "$DTB" "$1" "$2"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

MODEL=$(get_s / compatible) || fail "no model compatibility"
case "$MODEL" in
  "apple,n71 apple,s8000 "*) : ;;
  *) fail "not a Samsung A9/N71 DTB" ;;
esac

SPI=/soc/spi@20a088000
TOUCH=$SPI/touchscreen@0
PD=/soc/power-management@20e000000/power-controller@801c8
BUS=$(get_s "$SPI" status) || fail "SPI2 status absent"
[ "$BUS" = "$EXPECT" ] || fail "SPI2 status mismatch"
CHILD=$(get_s "$TOUCH" status) || fail "touchscreen status absent"
[ "$CHILD" = disabled ] || fail "touchscreen must be disabled"
SPIPD=$(get_x "$SPI" power-domains) || fail "SPI2 power-domains absent"
PDPH=$(get_x "$PD" phandle) || fail "SPI2 PMGR domain phandle absent"
[ "$SPIPD" = "$PDPH" ] || fail "SPI2 genpd phandle mismatch"
COMPAT=$(get_s "$SPI" compatible) || fail "SPI2 compatible absent"
case " $COMPAT " in
  *" apple,s5l-spi "*) : ;;
  *) fail "SPI2 driver compatibility missing" ;;
esac

echo "PASS: N71/S8000 mode=$MODE, touch=disabled, SPI2 genpd linked"
echo "NOTE: DTB structural validation is not evidence of safe hardware operation."
