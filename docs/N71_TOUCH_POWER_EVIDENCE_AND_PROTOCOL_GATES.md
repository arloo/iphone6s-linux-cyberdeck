# N71/S8000 Z2: power register evidence, protocol boundary and next test gates

**Date:** 2026-11-10
**Status:** Prior real-device readbacks reinterpreted; 2026-11-10 SPI host cycle verified; **no successful Z2 calibration or touch input**.

## Distinguish observed hardware from hypotheses

The Samsung Apple A9 iPhone 6s reached a RAM-only Linux BusyBox shell with the built-in S5L SPI host driver, `spi0` and its dedicated power domain `on`. Ten guarded host-only platform unbind/rebind cycles passed: `on → off-0 → on`, with the SPI reference clock enable count `1 → 0 → 1`. Those cycles did not touch the external Z2 regulators or load firmware.

In *earlier* N71 experiments (separate RAM boot, private log files retained locally), an intentionally scoped hardware helper reported these register readbacks:

| Register/observation | Captured state | Interpretation and confidence |
| --- | --- | --- |
| Candidate PMGR touch reference | `0x800002ee` | Disable bit set; enable bit clear; divider `750`, approximately 32 kHz for a 24 MHz parent **if this really is the A9 touch clock** |
| Candidate PMGR touch reference after enable | `0x000802dc` | Enable bit set; disable and busy bits clear; divider `732` (~32,787 Hz at 24 MHz) |
| Main PMU core switch `0x319` | Low bit `1` | Prior OS left the Z2 core switch enabled |
| Chestnut analog register `0x05` | `0x0f` then `0x1f` | Only touch analog bit `0x10` changed, preserving the lower LCD-related bits |
| Subsequent clock readback | `0x800002ee` | The baseline word appeared again; **not** proof every error path restores the register |

These are historical observations, not live measurements of the **current** host-only Linux boot. Neither the clock output waveform nor the voltage at the Z2 pads has been independently measured. The PMGR offset was derived from a related A10 implementation and requires independent mapping confirmation for S8000 before the touch clock provider is enabled for general use.

## What the previous firmware boot proves and does not prove

The earlier Z2 bootloader communication succeeded for short status/register transactions at 1 MHz SPI mode 3 with configured chip-select setup/hold timing. A per-device calibration frame was **1,038 bytes** (10-byte header, 1,024-byte payload and 4-byte trailer), targeting RAM at `0x10009000`. The expected acknowledgment `ACK_DATA=0x4bc1` did **not** arrive.

The previous probes reported `REQ_CAL=0x1f01` after one status check or `IDLE=0x4879` after 50 bounded polls. Both are **not** successful DATA acknowledgments. Changing the calibration word byte order also did not solve the error.

The original firmware container has a `NOP=0x18e1` prefix before preconstructed DATA records, while the locally generated calibration DATA frame does not. This is a testable **protocol framing hypothesis**, not a proven bug: Apple may intentionally use different framing for calibration and firmware segments. Never combine the NOP-prefix and 16-bit transfer hypotheses in the same test.

## What the reference implementations add

The maintained upstream Apple Z2 driver supports the general SPI firmware-boot, calibration and multitouch architecture. A separate, hardware-tested J172 implementation documents an explicit state machine from `OFF` through `HBPP_READY` and `FIRMWARE_READY` to `REPORTS_READY`, with rollback between phases.

These are valuable design patterns, but J172 has a different SoC/board integration, and its verified touchscreen behavior must not be presented as working N71 support.

- [Upstream Apple Z2 touchscreen implementation](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/4b11f2336e23d5c55b76591bd8ac39b059f68ad0/drivers/input/touchscreen/apple_z2.c)
- [Independent J172 touch bring-up notes](https://github.com/Pauli1Go/HoolockLinux-bringup-docs/blob/main/docs/touch.md)

## Experimental order

1. Maintain the known-good N71 RAM boot and its USB root shell. Record board identity, current SPI2 domain, SPI driver, `gpio-keys`, core PMU, Chestnut analog, PMGR touch-clock candidate and reset GPIO using a **read-only** board-matched helper.
2. Require exactly captured before/after baseline words; stop on any unknown status bit, missing readback, unexpected reset, or independent USB failure. The offline gate `tools/touch/n71_power_gate.py` models these invariants and includes negative synthetic regression cases.
3. Validate the PMGR offset and pinmux dependencies from the board-matched Apple Device Tree, not an A10 assumption. Any clock enable test must capture the full raw word and verify exact restoration.
4. Stage a dedicated RAM boot with the relevant provider registrations and **Z2 SPI child still disabled**, then confirm these providers' read-only functionality. Do not enable all regulators and initiate calibration in the same first probe.
5. Only after power/reset/recovery gates succeed, test a single bounded HBPP **status-only** handshake with timestamps and SPI-controller transfer metadata but without vendor payload logging.
6. Compare one documented framing hypothesis at a time (baseline first, optional prefixed NOP second). Always return to captured regulator/clock/reset baseline after a failed attempt. No fuzzing or unbounded retries.
7. A successful `ACK_DATA` merely advances to the firmware state. Functional acceptance requires a persistent evdev device and calibrated 750 × 1334 per-finger coordinates, corners, drags, releases and genuine two-finger tracking.

## Privacy and source status

No private Apple firmware, calibration records, serials, MAC addresses, personal email or device-specific provisioning content is included. Public source is an RFC; it is **not** a verified A9 multitouch solution. The current physical iPhone was not reset or modified to generate this report.
