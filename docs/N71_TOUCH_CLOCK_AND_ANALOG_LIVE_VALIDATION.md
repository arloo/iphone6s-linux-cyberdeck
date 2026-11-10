# N71/S8000 Z2 — live clock rollback and Chestnut analog-rail qualification

**Test date:** 2026-11-10
**Target:** Samsung Apple A9 iPhone 6s (N71), replacement aftermarket display; the user confirmed that its touch function was normal under iOS.
**Kernel:** `7.3.0-rc1-g68aadac820d0-dirty`, **build #5**, dated 2026-11-10 15:44 CET.
**Result:** Real-device clock rollback **PASS**, real-device analog supply enable/restore **PASS**, full HBPP/Z2 firmware bring-up **NOT TESTED**.

## 1. Correct RAM-only boot

The iPhone booted the specific `CYBERDECK_A9_Z2_CLOCK_SETTLE_TEST.iso` payload in volatile RAM from DFU/PongoOS. The Dell reached its BusyBox root shell over the USB gadget `05ac:4142`; initial packet test: **4/4**.

The onboard kernel reported build `#5`, rather than the earlier safe-patched `#4`. SPI2's device tree was `okay`, the touch-reference-clock provider was `okay`, while `touchscreen@0` remained **disabled**. This deliberately prevents automatic Z2 probing or an unreviewed proprietary firmware/calibration transfer.

## 2. Patched touch clock — real hardware acceptance

A diagnostic module was rebuilt for the exact running kernel ABI; all its undefined kernel symbols were matched against the built kernel exports. The module explicitly selected the **output** `touch_ref` clock through the common clock framework, not its 24 MHz parent.

The module used a **single bounded 20 ms activation**, through the revised clock provider:

| Stage | Live PMGR readback |
| --- | --- |
| Before CCF enable | `0x800002ee` |
| With `touch_ref` enabled | `0x000802dc` |
| After CCF disable | `0x800002ee` |

The live kernel logged `PASS: CLOCK_ON_20MS_AND_EXACT_BASELINE_RESTORED`. **No touch-clock rollback/readback warning** was present in the filtered dmesg output on build #5, in contrast to the older build #4. Afterward, both `touch_ref` enable and prepare counts were `0`, while SPI2's domain remained `on` and its controller reference clock count remained `1`.

The driver still reports a *calculated* 32,000 Hz for the inactive touch reference. This is **not** an electrical measurement of the output waveform or proof of exactly 32.768 kHz.

## 3. Post-clock read-only hardware audit

An independently rebuilt, no-write diagnostic acquired two snapshots 150 ms apart. Both were byte-for-byte consistent, reporting:

- PMGR candidate touch-clock word `0x800002ee`; adjacent register word `0x00000000`.
- Main D2255 PMU core switch `0x319 = 0x01`; related `0x219 = 0x00`.
- Chestnut analog-power register `0x05 = 0x0f`.
- Touch reset GPIO 75 is configured as **output, level low**, corresponding to asserted active-low reset. The IRQ and SPI pin configurations were stable.

A probe intentionally returns `-ECANCELED` after printing its results, so BusyBox `insmod` may report an expected cancellation and repeat the init callback. A subsequent **success** must be established from the actual register log, not the process exit status.

## 4. Chestnut analog power — real hardware acceptance

Using the existing, previously physically tested `touch_chestnut_guard` source, rebuilt for the exact current kernel, we performed a bounded enable/restore sequence over I²C-0 address `0x27`, register `0x05`. All other LCD supply bits were preserved.

The helper only permits the exact transitions `0x0f → 0x1f` for enable and `0x1f → 0x0f` for restore; it refuses every other starting value.

| Stage | Live Chestnut register |
| --- | --- |
| Baseline | `0x0f` |
| Touch analog bit 4 asserted | `0x1f` |
| Direct restoration | `0x0f` |
| Independent delayed watchdog | Already at `0x0f`; no additional write |
| Subsequent standalone read-only inspection | `0x0f` |

A **20 ms application sleep** was requested, but kernel timestamps between activation and successful restoration indicate approximately **59 ms of actual enabled time**, including module-loading overhead. Do not present that as a precisely met 20 ms rail pulse.

Because the helper's `-ECANCELED` return may trigger another init attempt, the log also shows an expected **REFUSED enable** when that redundant attempt observes an already enabled `0x1f`, and **REFUSED restore** when the backup watchdog observes the already restored `0x0f`. These are fail-closed guard messages, **not** additional enable or restore writes. Before an integrated status-only experiment, the helper should be refactored into a one-shot resident module or equivalent non-retrying harness.

After the analog experiment, an independent board snapshot again matched all baseline registers and reset/IRQ pin values. No SPI Z2 transfer occurred and the reference clock remained off.

## 5. Post-experiment stability

- USB gadget still enumerated as `05ac:4142`.
- **100/100** post-test ICMP packets delivered, **0% loss**, average RTT **2.483 ms**.
- SPI2 power domain `on`, SPI clock enable count `1`, `touch_ref` counts `0 / 0`.
- No relevant kernel panic, Oops, I²C error or touch-clock rollback failure appeared in the filtered diagnostic logs.
- All **69/69** public automated tests and the synthetic HBPP packet audit passed.

## 6. What remains before touch activation

These tests separately qualify the clock provider, the analog enable switch and the known board reset configuration. They **do not** prove the integrated power-up order, the physical 32 kHz clock waveform, firmware compatibility with the aftermarket panel, a successful `ACK_DATA`, or multitouch input.

The next controlled experiment must couple the resources in one bounded, reversible **status-only** diagnostic:

1. Verify unchanged PMGR clock, Chestnut, main PMU, SPI host, asserted reset, and no existing SPI children.
2. Keep reset asserted; switch only Chestnut's touch analog enable bit, retain core's existing `0x01`, request the **output** `touch_ref` via CCF, and check the expected PMGR active readback.
3. Configure the isolated SPI2 CS0 peripheral at **1 MHz, mode 3, 8-bit words, 5 µs CS setup and 10 µs hold**, without binding or triggering the full Apple Z2 firmware driver.
4. After the board-defined reset delay, issue only the documented HBPP ATN/NOP and bounded register-read commands. Accept a 32-bit controller-version value only if the reply has `READ_DATA=0x4c39` and a valid checksum. Log status and version metadata only, never proprietary firmware/calibration contents.
5. On *every* exit, reassert reset, disable the clock, restore Chestnut to the exact baseline, verify both supply registers and clock counts, and keep an independent recovery mechanism ready. Stop on any mismatch; do not retry automatically or fuzz vendor commands.
6. Only after HBPP is stable, address the still-failed calibration `ACK_DATA=0x4bc1`; full acceptance remains accurate 750×1334 evdev multitouch.

The currently running phone is intentionally left on the stable **#5 RAM-only kernel with Z2 child disabled**. No user storage, iOS NAND, private provisioning, unique calibration or Apple firmware was written or published in this test.
