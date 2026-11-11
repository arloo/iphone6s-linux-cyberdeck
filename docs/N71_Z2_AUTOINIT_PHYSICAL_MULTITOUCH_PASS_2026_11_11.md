# N71/S8000 native Linux touchscreen: automatic startup and multitouch PASS

**Date:** 2026-11-11. **Device:** physical iPhone 6s Samsung A9/S8000/N71. **Runtime:** supervised DFU/PongoOS RAM-only HoolockLinux kernel #5 with modified private initramfs. **Acceptance:** automatic controller initialization and two simultaneous contacts verified after Linux boot, without a single operator-issued manual touch sysfs command.

## New hardware boot (no NAND changes)

A new private RAM-only payload retained the previously validated kernel binary, device tree, controller calibration, firmware, bootloader and boot arguments. Only the initramfs was changed to include the *public* N71-restricted autoinit script from scripts/n71_z2_autostart.sh and a single call in init. The phone re-enumerated from PongoOS USB 05ac:4141 to Linux USB 05ac:4142. Host USB network checks succeeded 3/3.

On-device /run/n71_z2_autostart.log (only non-identifying status lines):

    [n71-z2-auto] START
    [n71-z2-auto] WAKE_OK
    [n71-z2-auto] D9_FIRST_OK
    [n71-z2-auto] D9_SECOND_OK
    [n71-z2-auto] D9_SURFACE_OK
    [n71-z2-auto] TYPE1_SETUP_OK
    [n71-z2-auto] COMPLETE:PROTOCOL_READY

Read-only verification of Z2 sysfs showed that startup automatically completed wake once, D9 metadata twice, one Type-1 long surface descriptor fetch with consistent E7 reply/checksum and plausible reversed-Y geometry, Type-1 9D/BF report setup and AF enable with E1 response and checksum agreement. All observed control error values were zero. No further controller writes occurred after boot.

## Physical contact acceptance, no manual Z2 setup

The operator then performed finger taps, drags toward corners, and two simultaneous fingers. A bounded host-initiated Linux EVDEV capture read native 24-byte input_event records from /dev/input/event0, reconstructing live ABS_MT_SLOT and ABS_MT_TRACKING_ID state at each EV_SYN/SYN_REPORT boundary.

| Physical metric | Result |
|---|---:|
| Captured EVDEV events (reached cap) | 4,096 |
| SYN_REPORT frames decoded | 581 |
| Maximum simultaneous active tracking IDs | **2** |
| SYN_REPORT frames with two active touches | **138** |
| Tracking ID starts in bounded sample | 12 |
| Tracking ID releases in bounded sample | 10 |
| Observed pixel X range (750-wide display) | 5 to 724 |
| Observed pixel Y range (1334-high display) | 14 to 1331 |
| Touch IRQ count during sample | **1 to 935** |
| Automatic startup with real two-finger touch | **PASS** |

The bounded sample reached its 4,096-event limit, *before* the user-provided completion signal. Therefore the two extra starts over releases cannot be interpreted as stuck contacts or failure to release; the capture is truncated. Earlier supervised first-contact and two-finger tests already verified release handling. Edge-range observations strongly support broad panel coverage but are not calibrated, position-labelled edge-accuracy tests.

After this test Linux USB remained reachable, including 2/2 ICMP responses. In a later four-second deliberate no-touch interval, touch IRQ remained unchanged at 2163; no continuous IRQ storm was detected in that short window. The existing boot-time short (20-byte) response warning appeared once *before* the automatic runtime setup, without new subsequent Z2 error or kernel Oops/panic messages.

## Engineering significance and remaining scope

**Hardware-validated:** the iPhone 6s touchscreen is operational under native Linux automatically after each supervised RAM boot when the experiment's private initramfs is used. Single-finger movement/release and two simultaneous contacts have produced actual Linux input events. This is significantly stronger than successful firmware transfer or only an SPI handshake.

**Still open:** measure latency, sustained use, exact edge/corner calibration, behaviour after repeated cold starts, long idle/suspend-resume behaviour and robust integration of the startup stage into a production distribution. The phone has not been made to boot Linux persistently from its internal flash, and the display, Wi-Fi, Bluetooth and full GUI/cyberdeck objective remain separate workstreams.

**Privacy:** the public repository contains the startup script and aggregate, sanitized test results. It does not contain the private RAM boot image, proprietary controller firmware, per-device calibration, raw D9 coordinates, physical event stream, USB serial/ECID, cryptographic keys or user secrets. Known-good fallback boot payloads remain on the authorized host.
