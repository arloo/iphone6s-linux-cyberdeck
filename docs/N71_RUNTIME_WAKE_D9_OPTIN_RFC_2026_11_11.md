# N71/S8000: opt-in runtime wake and D9 report discovery

**Date:** 2026-11-11. **Stage:** offline ARM64 Z2 object and full Image.gz build PASS, private RAM-only payload staged and byte-reproduction checked; NOT YET PHYSICALLY BOOTED. The running iPhone remains on the previously tested kernel #2, and real touch remains BLOCKED.

## Grounded reason for investigating runtime initialization

On the Samsung A9 N71, the HBPP calibration and both private firmware blocks were acknowledged, the kernel logged firmware EXECUTE, and EVDEV event0 was registered. However GPIO142 remained high with touch IRQ total 1. Physical finger contact produced no touch events. One idle and one finger-held SPI runtime report request gave reply 0xEA, which is not a recognized E1 touch frame. An automatic earlier E1 reply was only 20 bytes in the existing parser. None of this proves the controller completed runtime scanning.

Two independently documented Z2 implementations show critical work between firmware start and contact reporting:

* Corellium Project Sandcastle (GPL-2.0-or-later): source https://github.com/corellium/projectsandcastle/blob/master/hx-touchd/hx-touchd.c. After its firmware boot it sends a 16-byte Z2 0xEE wake, performs two E3 D9 report-info transactions, then reads surface metadata and configures report types 9D/BF/AF as appropriate. This is a SOURCE REFERENCE; the public patch contains independently written code, not verbatim copies of the Sandcastle source.
* HoolockLinux iPad7 J172 hardware report: https://github.com/Pauli1Go/HoolockLinux-bringup-docs/blob/main/docs/touch.md. Its production-quality path uses DeviceInfo, surface D9, report initialization and runtime IRQ state transitions. The J172 A10 system is not electrically or operationally identical to the N71 A9.

## RFC 0008: minimal N71-only opt-in controls

The patch at patches/0008-n71-opt-in-z2-runtime-wake-d9-rfc.patch applies AFTER patches 0001 through 0007 to the pinned source commit 68aadac820d01d0cd4efbd1fefd4c45f23be0a51.

The manual controls appear at /sys/bus/spi/devices/spi0.0/ only on board compatible apple,n71:

- runtime_state (read-only): diagnostic flags and response summary, NO SPI side effects.
- runtime_wake (write-only): writing ASCII 1 transmits ONE 16-byte wake command 0xEE; guarded to one attempted transfer per boot, including transport error cases.
- runtime_d9 (write-only): writing ASCII 1 transmits ONE 16-byte E3 D9 report-info request; requires wake transport success; maximum TWO attempts per boot. Not a full D9 report read, and no touch report is configured automatically.

The command uses zeros in the first 14 bytes other than opcode and optional report, then a 16-bit little-endian sum of the first 14 bytes. The two wire candidate frames are:

- Wake: ee 00 00 00 00 00 00 00 00 00 00 00 00 00 ee 00
- D9 info: e3 d9 00 00 00 00 00 00 00 00 00 00 00 00 bc 01

The driver uses its existing mutex to prevent concurrency with threaded IRQ reads. No reset, firmware upload, clock or regulator change, GPIO polarity change, automatic retries or NAND operations were introduced. Operator-triggered writes are state-changing requests to the touch controller, NOT read-only electrical measurements. Responses are reduced to reply byte, optional status/size and computed checksum agreement; raw SPI payloads, private firmware and calibration are not published.

**Uncertainties:** Corellium's source predates N71 hardware validation. The meanings of 0xEA and 0x4969 on this iPhone remain unknown. Response checksum agreement is observational; lack of agreement does not alone mean a transport failure. A completed 0xEE SPI transfer does not prove the panel is awake.

## Offline reproducibility gates passed

The kernel driver object and complete ARM64 Image.gz linked with the host cross-compiler. The existing live-tested runtime-probe RAM image was reconstructed exactly from m1n1, bootargs, the unchanged private N71 DTB, the unchanged disabled S8003 DTB, the preserved previous kernel and the original private initramfs. Replacing ONLY the kernel Image.gz produced a separately staged 11,817,401-byte RAM-only experiment. The previously working N71 payload, runtime-probe payload, and older recovery image remain unchanged; no device-specific payloads were uploaded to GitHub.

The complete patch series 0001-0008 was replayed, in order, on an independent clean pinned kernel source; the resultant driver source matched the newly built private source byte-for-byte. Synthetic tests validate checksum framing and one-shot gating logic, not physical Z2 behavior.

## Physical test gates (not yet run)

1. Confirm the new private RAM-only image is correctly packed from the previously byte-reproduced working payload, with unchanged private firmware, calibration, DTBs and m1n1.
2. Physically supervised DFU/Pongo boot. Confirm HoolockLinux USB gadget, baseline firmware-start log, kernel input node, clock, rails and IRQ counts.
3. Read runtime_state to establish that wake/d9 attempts are both zero. Do NOT write until this holds and host USB stays stable.
4. Write ASCII 1 to runtime_wake ONCE, then examine runtime_state, dmesg, GPIO IRQ and USB connectivity. On error, STOP without retry.
5. After evaluating step 4, optionally write ASCII 1 to runtime_d9 ONCE. Any second E3 D9 request is a separate decision after inspecting the first response.
6. Only if report and interrupt delivery respond, proceed to actual EVDEV finger tap, coordinate, release, simultaneous two-finger and drag acceptance.

Fallback is the already hardware-booted Z2 runtime-read-once image, kept immutable alongside an older known-good RAM image. S8003/N71m experiments remain deferred. The full N71 touchscreen is NOT yet functional.
