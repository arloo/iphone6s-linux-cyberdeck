# N71/S8000 inverted Y metrics and guarded Type-1 touch report setup

2026-11-11. RFC 0010. The source and full ARM64 image are OFFLINE; the new candidate has not been booted on the actual iPhone yet. Full touch is not working.

## Live result in kernel #4

A supervised S8000/N71 RAM-only boot successfully acknowledged private controller calibration and both firmware blocks. The first and second runtime E3/D9 requests returned the same expected metadata handshake as in kernel #3: the second announced a 16-byte surface descriptor. One operator-selected Type-1 E7/D9 read returned E7 and a matching reply checksum, and the signed sensor spans measured approximately 5.8k x 10.4k units. Their ratio matches the physical 750x1334 screen ratio within **0.1%**. The vertical sensor axis is reversed. The RFC #9 validity check incorrectly required increasing Y endpoint order; thus it rejected an otherwise convincing descriptor and properly blocked AF.

The raw per-device surface boundaries and all proprietary calibration, firmware, IDs and USB logs remain in private local storage; the public report only states approximate spans and aspect error.

Original reference for signed coordinate handling: https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/input/touchscreen/hx-touch.c . The Corellium Linux driver applies (raw - start) divided by (end - start) and allows negative denominator when the Y axis is reversed.

## RFC #10 engineering changes

The patch is patches/0010-n71-inverted-y-metrics-type1-report-setup-rfc.patch and applies after RFCs 0001 through 0009 on pinned HoolockLinux Linux revision 68aadac820d01d0cd4efbd1fefd4c45f23be0a51.

- Accept either signed axis direction: require 512 to 20,000 units for the absolute span of each axis, a Type-1 E7 reply with a matching observed checksum, and geometry aspect ratio within 10% of 750:1334. The state explicitly reports a reverse-Y flag.
- Transform later raw signed finger coordinates to pixel coordinates 0..749, 0..1333 using the validated signed D9 bounds, checking signed denominators and clamping; no change to non-N71 boards. Actual touch frames have not yet been observed.
- Add manual, N71-only one-shot runtime_type1_setup: enabled ONLY after successful Type-1 descriptor fetch and geometry validation. Sends E4/9D with eight bytes 01 00 00 00 00 00 00 00 followed by E1 commit, then E4/BF with four bytes 9D 81 09 00 followed by E1 commit, following published Project Sandcastle hx-touchd Type-1 configuration. Stop on first transport error. No automatic retries or timer loops.
- Permit the already-existing manual one-shot AF=00 report setup ONLY after success of 9D and BF for Type-1; preserve separate Type-2 behavior (not used on this device).
- Expose one-shot attempt state and result codes through passive runtime_state text output. Root-only sysfs writes, IRQ serialization mutex and S8000/N71 machine guard continue to apply.

Corellium Project Sandcastle source: https://github.com/corellium/projectsandcastle/blob/master/hx-touchd/hx-touchd.c

## Offline and physical acceptance

The full ARM64 kernel and source replay are validated separately; the private ram image reuses the same m1n1, original calibration DTB, matched firmware initramfs and disabled S8003 DTB. The previous kernel #4 RAM image and earlier fallbacks must remain untouched and usable. Public synthetic tests cover reverse-Y geometry, false-accept geometry, pixel mapping, Type-1 E4 9D/BF frame checksums, manual-only gating and privacy.

Supervised next hardware test:
1. Enter DFU, load PongoOS, send the new private RAM-only image once. Verify USB 05ac:4142, firmware-start logs, no initial manual actions.
2. One EE wake and exactly two E3/D9 requests, inspecting the response and USB health after each step.
3. One Type-1 E7/D9 16-byte descriptor fetch. Require reply E7, matching observed checksum, plausible geometry and reversed-Y indication. If not, STOP.
4. One Type-1 9D/BF setup, inspect status. Then, if SPI transport is healthy, one AF setup.
5. Check IRQ142 count, GPIO level and actual EVDEV Type-B tracking ID, 750x1334 coordinates, release, two-finger contact and edge access.
6. If no IRQ or EVDEV, stop and assess the type-specific runtime EB report framing against the source driver. Do not toggle GPIO IRQ polarity blindly, and do not consider firmware-start alone proof of working touch.

This RFC does not modify Apple NAND or switch power and reset states. If USB fails, recover with the unchanged previous RAM-only payload under supervision. S8003 remains deferred.
