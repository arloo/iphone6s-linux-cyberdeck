#!/usr/bin/env bash
# Offline/public-source compile gate; NOT a boot-ready kernel image.
# Use a pinned, clean HoolockLinux source clone. Never touch hardware or NAND.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <pinned-public-kernel-checkout> <empty-out-directory>" >&2
  exit 2
fi
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
INPUT="$(realpath "$1")"
OUT="$(realpath -m "$2")"
EXPECTED="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sources"]["linux"]["commit"])' "$ROOT/manifests/upstreams.json")"
[[ -f "$INPUT/Makefile" ]] && [[ "$(git -C "$INPUT" rev-parse --is-inside-work-tree 2>/dev/null)" == true ]] || { echo "Not a full Git Linux source checkout or linked worktree" >&2; exit 3; }
[[ "$(git -C "$INPUT" rev-parse HEAD)" == "$EXPECTED" ]] || { echo "Kernel SHA mismatch" >&2; exit 4; }
[[ -z "$(git -C "$INPUT" status --porcelain)" ]] || { echo "Kernel upstream is dirty" >&2; exit 5; }
[[ ! -e "$OUT" ]] || { echo "Refusing existing output directory" >&2; exit 6; }
TEMP="$(mktemp -d)"
worktree="$TEMP/kernel"
cleanup() {
  git -C "$INPUT" worktree remove --force "$worktree" >/dev/null 2>&1 || :
  rm -rf -- "$TEMP"
}
trap cleanup EXIT
git -C "$INPUT" worktree add --detach "$worktree" "$EXPECTED" >/dev/null
for patch in "$ROOT"/patches/000{1,2,3,4,5}-*.patch; do
  [[ -f "$patch" ]] || { echo "Missing RFC patch" >&2; exit 7; }
  git -C "$worktree" apply --check "$patch"
  git -C "$worktree" apply "$patch"
  echo "SOURCE_PATCH_APPLIED $(basename "$patch")"
done
mkdir -p "$OUT"
# Default defconfig is for *compilation checking only*, not real N71 hardware.
make -C "$worktree" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig prepare
make -C "$worktree" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 \
  drivers/clk/clk-apple-touch.o drivers/input/touchscreen/apple_z2.o
file "$OUT/drivers/clk/clk-apple-touch.o"
file "$OUT/drivers/input/touchscreen/apple_z2.o"
LC_ALL=C readelf -h "$OUT/drivers/clk/clk-apple-touch.o" | grep -q 'Machine:.*AArch64'
LC_ALL=C readelf -h "$OUT/drivers/input/touchscreen/apple_z2.o" | grep -q 'Machine:.*AArch64'
echo "OFFLINE_KERNEL_OBJECTS_BUILD_PASS (not hardware-qualified)"
