# N71/S8000 live RAM Linux: HBPP firmware startup, EVDEV registration, IRQ gate

**Date:** 2026-11-11. **Device class:** iPhone 6s, Samsung A9 S8000/N71, aftermarket screen confirmed working under iOS. **Evidence level:** supervised physical hardware; sanitized report.

## What passed

A newly assembled RAM-only m1n1/Linux payload was sent from PongoOS 2.6.3. The terminal reported a full 11,813,745-byte upload, then a USB disconnect and LIBUSB_ERROR_IO. The host subsequently enumerated the **HoolockLinux USB gadget 05ac:4142**, exposed CDC ACM and the USB networking interface, and received 3/3 ICMP responses from the phone at 172.16.42.1. The Pongo USB error was therefore **not** an end-to-end Linux boot failure.

On-device kernel banner: `7.3.0-rc1-g68aadac820d0-dirty #1`, ARM64, built 2026-11-11 10:16:38 CET. The instrumented logs observed:
- `apple-z2 spi0.0: calibration 1038 bytes to 0x10009000: acked`
- `apple-z2 spi0.0: blob of 65460 bytes: acked`
- `apple-z2 spi0.0: blob of 18600 bytes: acked`
- `apple-z2 spi0.0: bootloader version 0x434d15c1`
- `apple-z2 spi0.0: calibration request done, status 0x4969 (?)` — its meaning remains unresolved
- `apple-z2 spi0.0: firmware started at 0x10003400`

The kernel registered **iPhone 6s Touchscreen** at `/dev/input/event0`, with ABS_X 0..749, ABS_Y 0..1333, ABS_MT_SLOT 0..255, ABS_MT_POSITION_X/Y and tracking IDs. GPIO-keys separately registered at event1. This **proves driver registration and firmware start logging, not working digitizer input**.

## What failed the acceptance gate

An attended `evtest /dev/input/event0` capture ran while the operator tapped center, corners, swiped and attempted two simultaneous fingers. It printed device capabilities but **no touch event lines**. At and after the test, `/proc/interrupts` showed the touch interrupt `Apple-GPIO 142 Edge apple-z2-irq` counter still at **1**, without increasing. The debug GPIO listing showed GPIO142 as an **input, high, IRQ**; GPIO75 was an output high (active-low reset semantics). This read-only observation does not prove a specific root cause. USB remained reachable and the phone stayed booted.

## Next bounded diagnostic gate

1. Do **not** repeat DFU, firmware uploads or GPIO/IRQ polarity changes just to gather equivalent evidence.
2. Cross-check N71 IRQ routing and active level against device-tree/ADT and the physical aftermarket panel implementation. The current DT requests `IRQ_TYPE_EDGE_FALLING` on GPIO142; the live interrupt counter is stagnant.
3. Read GPIO/IRQ counters while performing supervised touches; distinguish no physical IRQ edges from correct edge delivery but an empty or mismatched report protocol.
4. If further action is required, develop a **read-only, bounded, rollback-safe diagnostic** before any live register, reset, clock, or SPI write.
5. Accept working touch only after physical Type-B EVDEV tracking IDs, in-range positions, release, and two simultaneous contacts are observed. S8003 testing remains deferred.

**Privacy:** No per-device calibration, Apple firmware, private ramdisk, serial, ECID, MAC, credentials or raw phone log is included in this report.
