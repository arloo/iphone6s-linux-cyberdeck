# N71/S8000 — aftermarket touchscreen assembly: hardware provenance gate

**Date:** 2026-11-10
**User-confirmed hardware fact:** The original Apple display has been replaced with a **non-original aftermarket screen**. The exact replacement brand, controller silicon revision, and flex part number have not yet been established.

## Consequences for our Linux Z2 bring-up

On the iPhone 6s, touch-controller hardware is associated with the display assembly. A replacement therefore may alter the actual touch-controller implementation or revision, even when the same phone's board, SPI2 pins and Apple N71 Device Tree remain unchanged. There is no evidence yet that this aftermarket screen uses an incompatible controller, a different protocol, or the same original controller. **Do not assume any of those outcomes.**

The existing N71 physical test remains valid: an electrical touch-side device answered the N1/HBPP status and register handshake (including the prior bootloader-version word). This establishes real communications with the **installed replacement assembly**, not proof of full Apple Z2 protocol equivalence.

The prior failure to receive calibration `ACK_DATA=0x4bc1` may have multiple causes, including DATA framing, checksum, SPI transfer timing, prerequisites, mismatched calibration data, different firmware/controller revision or incorrect expected ACK semantics. An aftermarket replacement is a plausible additional factor, **not a root cause established by the logs**.

## New acceptance and diagnostic gates

1. **Preserve the current working Linux session.** Do not disassemble the phone or disturb display connectors while it is running.
2. At a **planned** return to iOS, establish an independent behavioral baseline: whether ordinary one-finger taps, edge touches, drags, simultaneous multi-finger gestures and 3D Touch (if the installed part supports it) work on this exact aftermarket display. Report any failures separately. iOS functionality does not prove that our RAM-only Linux firmware/calibration configuration matches the replacement.
3. Capture the replacement's supplier, part number or flex markings **only when safely accessible**, or use the original packaging/receipt. Do not publish unique identifiers or private photos without review. Never infer the chip solely from the external glass.
4. During a bounded Z2 status-only session, collect **sanitized** controller-version, protocol mode and chip-ID metadata when available via documented reads. Compare those fields with reference research while **not** claiming that a version word uniquely identifies the display vendor.
5. Independently validate the firmware variant and calibration's expected panel/controller compatibility before staging the proprietary payload in the phone's volatile RAM. The original device's calibration blob is **not automatically interchangeable** with aftermarket display hardware.
6. Perform the already gated power, reset, clock and SPI transaction tests first, one variable at a time; capture exact before/after readbacks and halt on mismatch. No brute-force firmware uploads, EEPROM writes or unbounded vendor-command fuzzing.
7. If an original Apple panel later becomes available, a controlled A/B test could discriminate panel-specific behavior from a Linux transport/driver defect. This is an optional diagnostic, **not** a prerequisite for improving the current aftermarket panel's support.
8. Real success remains full-resolution **750×1334** stable evdev multitouch (corners, drags, releases, two independent contacts). Coarse quadrant reporting and temporary input-node registration are inadequate.

## Sources / scope

- Apple repair guidance: https://support.apple.com/it-it/103256 (non-genuine display compatibility issues).
- iFixit iPhone 6s display teardown: https://www.ifixit.com/News/7444/iphone-6s-display-teardown (digitizer and 3D Touch assembly distinction).
- Technical repair analysis: https://microsoldering.com/iphone-6s-plus-touch-ic (6s-family controller hardware associated with replacement display assembly).

This note does not identify the user, the supplier, or unique device firmware/calibration. The publicly published source and test report stay in English; the private project log may retain operational details.

**Status:** AFTERMARKET SCREEN CONFIRMED. CONTROLLER REVISION AND FIRMWARE COMPATIBILITY UNKNOWN. No new physical SPI/calibration writes performed while creating this note.
