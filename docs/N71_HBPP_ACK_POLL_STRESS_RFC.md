# N71/S8000 — bounded calibration ACK polling fault-injection study

**Date:** 2026-11-10
**Hardware:** Samsung Apple A9 iPhone 6s (N71) with a user-confirmed aftermarket replacement display. The touchscreen worked normally under iOS, but has not achieved full-resolution input under Linux.

## Live evidence versus offline implementation

**Real N71 evidence from earlier Linux boots:** an initial Z2 calibration DATA transfer of 1,038 bytes to RAM address `0x10009000` returned `REQ_CAL=0x1f01` on its first acknowledgment poll. The experimental driver immediately stopped and returned `-EIO`, although the configured loop permitted up to 50 polls for transient statuses. A separate experiment observed `IDLE=0x4879` for all 50 attempts. Neither reached the required `ACK_DATA=0x4bc1`.

**Verified source bug:** `apple_z2_hbpp_wait_ack()` previously treated `REQ_CAL` as a terminal error for **all** expected acknowledgment types, despite the possibility that calibration processing is still pending. That makes a later valid `ACK_DATA` unobservable in the first case. It does not prove the controller actually would have returned `ACK_DATA` if we had continued polling.

## Minimal proposed correction

`patches/0003-n71-hbpp-cal-data-reqcal-pending-rfc.patch` alters exactly one condition: when the expected reply is **`ACK_DATA`**, and the observed status is `REQ_CAL`, classify it as **pending** instead of immediately terminal. The poller retains the original finite limit of 50 polls and bounded delay between attempts. All other unexpected statuses remain terminal. The separate register-write `ACK_REG` path still treats `REQ_CAL` as an error.

The patch does **not** bypass ACK verification: only the exact `ACK_DATA` value advances the firmware state. Repeating `REQ_CAL` for the full poll budget produces `-EIO`. It does not modify calibration payload, SPI timing, chip select, 32 kHz clock or power rails.

## Aggressive offline testing

- The isolated ARM64 Z2 driver and touch reference-clock objects compiled successfully with this patch alongside the power-rollback and strict HBPP-read modifications.
- A deterministic synthetic reference (`tools/touch/hbpp_ack_replay.py`) was used to check all short combinations of common statuses, deadline boundaries, `REQ_CAL → ACK_DATA` and `REQ_CAL → IDLE → ACK_DATA` transitions, incompatible `ACK_REG` responses and timeout behavior.
- **100,000 seeded pseudo-random acknowledgment sequences** were checked for false positive acceptance; the software reference never accepted any word other than `ACK_DATA`.
- **10,000 seeded pseudo-random calibration frames** (1–4,096 bytes) were compared byte for byte with an independent 16-bit SPI serialization model.
- An additional **1,000 fault-injection frames** had corrupt commands, header lengths, address bytes, header checksums and payload checksums; the frame validator rejected each corrupted sample.
- The resulting public test suite passed **61/61 Python cases** plus the existing synthetic HBPP audit.

These tests validate the *software model and encoding invariants*. They do **not** constitute successful physical calibration or support firmware-protocol claims for the aftermarket controller.

## Separate real-device stability stress

While the iPhone was running the known-good **clock-provider-only** RAM kernel (Z2 child still disabled), its built-in Apple SPI host completed **100/100** guarded driver unbind/rebind cycles. Every iteration checked the SPI2 domain `on → off-0 → on`, the controller reference clock enable count `1 → 0 → 1`, the touch-reference clock staying at count `0`, and reappearance of `spi0`.

After the stress, the phone's USB gadget was still reachable, the same clock and domain states were intact, and a filtered kernel log showed no panic, Oops or SPI timeout. No Z2 SPI transfers were made during this power-controller stress. A 100-cycle test does not establish long-term thermal or production hardware durability.

## Gated physical acceptance

1. Boot the **newly compiled** combined safe-Z2 kernel in RAM on the same N71. Confirm the baseline USB and SPI2 behavior with the touchscreen child still disabled.
2. Validate board-specific PMGR touch reference, analog/core regulator and reset GPIO readbacks. Stop if an unexpected state cannot be restored. The installed aftermarket panel's controller/version must be validated using a strict 8-byte `READ_DATA` status-and-checksum parser.
3. Only under a deliberate, bounded Z2 boot with the approved firmware/calibration and recovery available, distinguish three outcomes: late valid `ACK_DATA`, persistent `REQ_CAL` timeout, or `IDLE` timeout. Log status sequences and timing but never raw proprietary calibration payloads.
4. Treat any completed firmware boot as **only** a precondition. Full acceptance is actual stable 750×1334 multitouch evdev with edge taps, drag/release, and two simultaneous contacts.

No firmware blobs, per-device calibration, serial numbers, Apple private ADT nodes or personal email are published.

Relevant external context: [upstream Apple Z2 driver](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/81122fba08fa3ccafab6ed272a5c6f2203923a7e/drivers/input/touchscreen/apple_z2.c) and [independent HoolockLinux J172 hardware lifecycle work](https://github.com/Pauli1Go/HoolockLinux-bringup-docs/blob/main/docs/touch.md). The latter is **not** proof of N71 support.
