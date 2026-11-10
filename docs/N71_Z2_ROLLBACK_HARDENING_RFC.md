# N71/S8000 touchscreen rollback hardening — offline RFC

**Date:** 2026-11-10
**Status:** Source changes isolated in a separate private Linux worktree; ARM64 driver objects compile. **No experimental touchscreen activation on the phone.**

## Proven controller baseline

The real iPhone 6s Samsung A9 (N71/S8000) has successfully run Linux ARM64 with `apple-s5l-spi` bound and SPI2 power domain `on`. A guarded sysfs unbind/rebind test also proved that the SPI2 domain transitions `on → off-0 → on`, with the SPI reference clock enable count `1 → 0 → 1`.

A more intensive ten-cycle test subsequently exercised the SPI driver unbind/rebind path repeatedly, with **10/10 successful cycles**, no child devices, no touch SPI transactions, and a watchdog fallback. These tests do **not** cover the touchscreen analog regulator, core supply, 32 kHz touch reference, or HBPP protocol.

## Source-level failures found

### 1. HBPP first-handshake error could strand the touch supply

In the N71 HBPP startup path, `apple_z2_boot_hbpp()` called `apple_z2_power_on()` and then performed an initial ATN/NOP handshake while reset was asserted. If that first handshake failed, it returned immediately and **skipped** `apple_z2_power_off()`.

The isolated patch routes the error to a shared teardown label. The cleanup asserts reset, disables the touch reference clock and releases regulator enable references. It also retains the later HBPP error path and prevents a successful initialization from triggering cleanup.

### 2. Touch reference clock driver discarded the previous register value

`apple_touch_clk_enable()` reprogrammed the PMGR touch reference clock using the expected A10-like register layout. `disable()` only cleared the enable bit and set the disable bit, without restoring the original divider or full register value. The actual A9 PMGR offset/register semantics remain **unverified**.

The isolated patch records the register before enabling, rejects an unknown/busy initial state, checks write operations, attempts rollback on enable failure, restores the captured baseline at disable and validates readback. Hardware testing of this clock path is explicitly blocked until the A9 register mapping has been confirmed independently.

## Device Tree dependencies

The current N71/S8000 DT source keeps all of the following **disabled**:

- `touchscreen@0` (Z2 SPI child)
- Core `touch-vdd` regulator from main PMU output `0x319`, mask `0x01`
- Chestnut display PMU parent, with touch analog `touch-avdd` output register `0x05`, mask `0x10`
- PMGR `touch_ref` 32.768 kHz clock provider (`clock-controller@78000`)

The built-in PMU switch provider and Chestnut MFD support were found in the kernel source and config, but **being compiled is not evidence those disabled DT providers are safely usable on the device**. In particular, the touch clock's PMGR offset was ported from an A10 reference and has not been electrically validated on A9.

Do not enable the Z2 child alone. Its core power, analog supply, touch reference, reset GPIO and interrupt source must all be assessed in a single rollback/recovery plan first. The device-specific calibration payload and vendor firmware stay private and are not included in this patch.

## Validation gates

1. New Linux source worktree is isolated from the previously on-device verified SPI2-HOST-ONLY build. No changes to the running kernel.
2. Compile the changed ARM64 objects with Clang 21 and the N71 configuration; build a full ARM64 `Image.gz` only as a separate candidate.
3. Verify both S8000 and S8003 DTBs still leave `touchscreen@0` disabled and SPI2 host enabled.
4. Run synthetic error-path tests for each failure step and rollback mismatch, without physical register writes.
5. Only then consider a specific board-matched touch clock/register **readback-only** test; do not reuse a historical PMGR value without checking the live state.
6. On an attended real-device run, allow bounded status-only Z2 transport diagnostics only after external reset, regulators, 32 kHz reference and rollback state have been independently validated. Do not combine the optional NOP and 16-bit transport hypotheses.

**Acceptance criteria for full-resolution multitouch remain:** a persistent evdev device with calibrated 750 × 1334 coordinates at corners, smooth drag and release, repeatable two-finger tracking, and reproducibility across RAM boots.

## Data handling

This RFC intentionally contains no proprietary firmware, per-device calibration, identity records, private memory dump, Apple user directory or email address. The original PongoOS recovery images remain separately preserved.

The patch is **research-stage** until a physical N71 touchscreen test verifies power integrity and functionality.
