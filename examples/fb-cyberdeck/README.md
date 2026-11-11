# Experimental N71 framebuffer cyberdeck display

An **experimental static ARM64 userspace program** renders a dark/cyan/pink cyberdeck panel to the standard Linux fbdev screen while reading real multitouch events from evdev. No X11/Wayland/compositor, iOS app layer or proprietary firmware is included.

**Physical status as of 2026-11-11:** with the N71 Linux RAM-only autoinit image already running, a static ARM64 program compiled from this C source was copied to the device's volatile /run directory over its USB gadget interface and started as PID 249. The program successfully opened the 750x1334 32-bit framebuffer and event0, stayed running, and its expected magenta and amber pixels could be read back from the fbdev buffer. **Visual confirmation on the physical LCD and corner-button acceptance are not yet recorded.** This readback is not a certified display panel scanout test.

## Build

Requirements: Linux host, AArch64 cross compiler with static libc, Python 3, Pillow, and a locally available TrueType font you have a right to use. No fonts or proprietary assets are distributed with the repository. A local 14x24 raster header is generated as a build artifact and gitignored.

    make -C examples/fb-cyberdeck

The binary is under build/cyberdeck-fb-aarch64. Verify its SHA256 before transfer to an **authorized device** already booted into Linux. The program requires functional /dev/fb0 and /dev/input/event0. It is presently locked to exactly 750x1334 32-bit fbdev and refuses unknown formats/offsets.

## User interface and verification

- Top: CYBERDECK / A9 and current ARM64 / touch status.
- Four amber edge targets near left/right and upper/lower regions. Successful new finger presses change their center squares to cyan.
- Live crosshair circles follow up to 32 active Type-B multitouch slots. Bottom status displays event/frame counts and maximum concurrent contacts.
- RESET clears target-test counters; EXIT stops the test. Root can also terminate the process with SIGTERM.
- On graceful exit the program tries to restore its previously captured framebuffer pixels. This is best effort; it does not change backlight, firmware or Apple NAND.

The program reads evdev without EVIOCGRAB and neither changes the kernel input protocol nor issues SPI reports. A physical touch acceptance test should compare the four target colors/positions to actual finger presses. The frame renderer is a proof of concept, **not a final GUI framework or verified latency benchmark**.

## Safety and privacy

This source contains no private board calibration, Apple firmware, ECID, serial, MAC or credentials. The ELF produced from it is never installed into an Apple root filesystem: the initial demonstration is RAM-only. A temporary HTTP transfer server was bound to the host's USB-gadget IP, used to copy this public-code executable into RAM and stopped immediately after SHA verification.
