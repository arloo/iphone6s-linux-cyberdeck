# N71 Z2/HBPP calibration ACK: bounded protocol review

**Date:** November 10, 2026

**Target:** iPhone 6s Samsung A9 (N71/S8000); Linux 7.3.0-rc1, RAM-only.

## Verified baseline (November 9 on-device)

- Physical SPI2 controller responded at 1 MHz, mode 3, chip-select setup 5 microseconds and hold 10 microseconds.
- The bootloader's status handshake exposed `REQ_CAL=0x1f01` and `IDLE=0x4879`; a version-register read reported `0x434d15c1`.
- The experimental driver attempted a 1,038-byte calibration packet for 1,024 bytes of device-specific calibration, targeting controller RAM address `0x10009000`.
- Expected `ACK_DATA=0x4bc1` did not arrive. The initial revision observed `REQ_CAL` after one poll; a bounded revision with 50 polls observed `IDLE=0x4879`. Repeating with the opposite 16-bit calibration byte-swap setting did not change the result.
- The probe failed with `-EIO` and did not register a persistent touch input device. The controller was returned to reset and the known baseline power/clock values restored.

## Source-level review (November 10; **no live SPI writes**)

Local reference: private out-of-tree `apple_z2_v2.c`; exact source is kept in the private build tree, not published here.

- The calibration builder makes a **10-byte header + 1,024-byte payload + 4-byte checksum = 1,038 bytes**. Its 16-bit word length is `0x0100`. These lengths are internally consistent.
- The driver emits a big-endian 16-bit wire encoding, with 32-bit values sent low-halfword first, and computes additive header/data checksums. A packet-structure audit alone cannot verify the actual controller-accepted framing.
- The SPI transport configures `bits_per_word=8` and uses a single transfer for this frame (below its 4,096-byte internal chunk threshold). That explains the **software intent** to keep CS asserted but does not independently verify the electrical CS waveform.
- The 50-poll test and the swapped/unswapped comparison **do not** establish a root cause. Do not mislabel the idle status as an accepted ACK.

## Next experiments (review gate required)

1. Perform offline synthetic tests of packet length, header fields and checksum encoding against an independently validated HBPP reference, without including private calibration bytes.
2. Inspect CS continuity, transfer count, controller IRQ timing and actual `spi_sync` completion from a strictly bounded, status-only trace. Observe before modifying transport behavior.
3. Compare the accepted N1 bootloader sequence against the reviewed iOS driver, especially preceding ATN/NOP/REQ_CAL transitions.
4. Only after the precise framing difference is identified, build an isolated driver patch and perform a **single RAM-only** test with guarded clock/analog power rollback.
5. A successful ACK is not enough to declare a usable touchscreen: firmware initialization and verified, calibrated multitouch `evdev` coordinates must follow.

**No proprietary Apple firmware, per-device calibration, MAC or raw ADT is in this report. No iOS NAND writes or speculative vendor-command fuzzing are permitted.**

## November 10: synthetic encoder audit and isolated transport diagnostic

The repository now includes a standard-library-only synthetic test harness:

- `tools/touch/hbpp_cal_audit.py` reconstructs the experimental 8-bit-wire calibration frame and compares it byte-for-byte against a separate legacy-struct / 16-bit-word SPI serialization reference. **No private calibration is needed.**
- The 1,024-byte synthetic case produces a 1,038-byte frame, including 10-byte header and 4-byte trailer. The target is `0x10009000`; header checksum, payload sum and declared length validate.
- The swapped and unswapped payload variants have the same header and additive checksum; therefore an unchanged ACK under both settings cannot distinguish their wire payload byte order.
- The software model treats `REQ_CAL` and `IDLE` as *pending*, not successful `ACK_DATA`. Nine repository-wide tests pass offline.
- These tests prove **internal consistency only**, not that Apple's controller accepted a physical SPI transfer. They do not account for CS voltage/timing, clock edges, FIFO behavior, IRQ state or the exact N1 firmware state machine.

A **private**, separately named ARM64 diagnostic module was also built offline against the exact running kernel `7.3.0-rc1-g6831bc701a6c` using LLVM 21, with matching vermagic. Its default calibration transfer remains the original 8-bit transport; an opt-in 16-bit-word test mode would preserve the same on-wire bytes by adjusting host memory word order, while guarding target address and frame length. Binary, vendor firmware and private calibration remain on the local host. **The diagnostic module has not been loaded or bound on the phone, and no new SPI/PMIC writes have been performed.**

Before any live experiment, verify that a new word-width test can be reversed reliably, capture a status-only trace of the existing 8-bit transport and retain a known-good USB shell. Do not interpret an offline module build as proof of controller operation. The reported iPhone 6s upstream touch-next port has demonstrated only coarse/quadrant touch despite reaching a later runtime stage; genuine full-resolution X/Y remains an unsolved requirement.
