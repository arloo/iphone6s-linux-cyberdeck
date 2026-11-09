#!/bin/sh
# Read-only, targeted hardware collector for a live iPhone 6s Linux root shell.
# Review the output locally before posting ANY part of it.
set -eu
echo "CYBERDECK A9 - sanitized-structure hardware probe"
echo "IMPORTANT: do not publish raw kernel logs or private firmware."
echo "== DATE + KERNEL =="
date -u 2>/dev/null || true
uname -a
echo "== DEVICE TREE =="
if [ -r /proc/device-tree/model ]; then tr -d '\000' < /proc/device-tree/model; echo; fi
if [ -r /proc/device-tree/compatible ]; then tr '\000' '\n' < /proc/device-tree/compatible; fi
echo "== MEMORY =="
grep -E '^MemTotal:|^MemAvailable:' /proc/meminfo 2>/dev/null || true
echo "== INPUT DEVICES =="
cat /proc/bus/input/devices 2>/dev/null || true
echo "== INTERFACES (NAMES ONLY) =="
ls /sys/class/net 2>/dev/null || true
echo "== BLUETOOTH ADAPTER NAMES (NO MACS) =="
ls /sys/class/bluetooth 2>/dev/null || true
echo "== PCI & SPI DEVICE NAMES =="
ls /sys/bus/pci/devices /sys/bus/spi/devices 2>/dev/null || true
echo "== FIRMWARE FILENAMES (NO BYTES) =="
find /lib/firmware -maxdepth 3 -type f 2>/dev/null || true
echo "== FRAMEBUFFER =="
cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || true
cat /sys/class/graphics/fb0/stride 2>/dev/null || true
cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || true
echo "== BLOCK NAMES =="
cat /proc/partitions 2>/dev/null || true
echo "Done. No state was deliberately changed."
