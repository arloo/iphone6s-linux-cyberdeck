#!/bin/sh
# SPDX-License-Identifier: MIT
# Optional showcase splash for a verified RAM-only N71 initramfs.
# DEBUG is the default. Touch, USB, SSH and the existing UI remain unchanged.
set -eu
mode=/usr/lib/cyberdeck/boot-mode
asset=/usr/lib/cyberdeck/splash.bgrx.gz
manifest=/usr/lib/cyberdeck/splash.sha256
log=/run/n71-splash.log

if [ ! -f "$mode" ] || [ "$(cat "$mode")" != showcase ]; then
    echo N71_SPLASH_DEBUG_MODE
    exit 0
fi
if [ ! -f "$asset" ] || [ ! -f "$manifest" ] || [ ! -c /dev/fb0 ]; then
    echo N71_SPLASH_UNAVAILABLE
    exit 0
fi
size=$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || true)
bpp=$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || true)
stride=$(cat /sys/class/graphics/fb0/stride 2>/dev/null || true)
if [ "$size" != "750,1334" ] || [ "$bpp" != 32 ] || [ "$stride" != 3000 ]; then
    echo N71_SPLASH_FRAMEBUFFER_MISMATCH
    exit 0
fi
if ! sha256sum -c "$manifest" > "$log" 2>&1; then
    echo N71_SPLASH_HASH_MISMATCH
    exit 0
fi
# Validate uncompressed byte count before writing a single byte to fb0.
if [ "$(gzip -dc "$asset" | wc -c)" -ne 4002000 ]; then
    echo N71_SPLASH_RAW_SIZE_MISMATCH
    exit 0
fi
if gzip -dc "$asset" > /dev/fb0; then
    echo N71_SPLASH_DISPLAYED_RAM_ONLY
else
    echo N71_SPLASH_FRAMEBUFFER_WRITE_FAILED
fi
