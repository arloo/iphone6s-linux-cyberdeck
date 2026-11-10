# N71/S8000 touch reference-clock: live settling anomaly and bounded rollback fix

**Date:** 2026-11-10
**Hardware:** Samsung Apple A9 iPhone 6s, user-confirmed aftermarket touchscreen (previously fully functional under iOS).
**State:** This report records the initial **build #4 rollback warning** and its bounded-settling correction. **Subsequent build #5 live hardware testing PASSED without the warning**; see [the clock and analog rail live validation](N71_TOUCH_CLOCK_AND_ANALOG_LIVE_VALIDATION.md).

## Physical evidence: read-only baseline

On the already verified RAM-only Linux kernel `7.3.0-rc1-g68aadac820d0-dirty`, a newly compiled read-only diagnostic module sampled the board's clock, power, and GPIO pin configuration twice, separated by 150 ms. Both snapshots matched exactly, including:

| Register | Baseline value |
| --- | --- |
| Candidate PMGR touch reference-clock word | `0x800002ee` |
| PMGR adjacent word | `0x00000000` |
| D2255 main PMU touch-core switch `0x319` | `0x01` |
| D2255 `0x219` | `0x00` |
| Chestnut analog-power register `0x05` | `0x0f` |
| Relevant SPI, reset and IRQ pin configurations | Identical across the two reads |

These are readbacks, not independent measurements of analog voltage, reset-pad signal quality or the physical reference-clock waveform. No private calibration or firmware was transferred.

The read-only module was compiled specifically for the running kernel ABI and checked against 11,012 kernel exported-symbol records. Its intentional `-ECANCELED` return means that a shell message saying "Operation canceled" is expected **after logging complete read-only results**.

## Physical evidence: one bounded clock cycle

The first diagnostic attempt accidentally requested the **24 MHz parent input** by using `of_clk_get(provider_node, 0)`, which obtains a clock consumed by that node, not its output. The module correctly reported **NO PASS**, leaving the PMGR register unchanged. This attempt is not evidence of successful Z2 clock activation.

A corrected module used `of_clk_get_from_provider()` with the clock provider's zero-cell phandle specification, plus an exact `touch_ref` identity and rate guard. It then performed **one** 20 ms enable/disable cycle through the existing Linux common-clock-framework provider:

| Event | Actual PMGR word |
| --- | --- |
| Initial disabled baseline | `0x800002ee` |
| Enabled `touch_ref`, 20 ms pulse | `0x000802dc` |
| After the CCF disable call | `0x800002ee` |
| Following independent read-only baseline check | `0x800002ee`, analog `0x0f`, core `0x01` |

The common-clock-framework enable and prepare counts returned to **0 / 0**, while SPI2's domain remained `on` and USB stayed functional. The separate read-only diagnostic confirmed the analog/core and GPIO signatures were unchanged.

**Important failure signal:** the clock driver also logged:

```text
touch clock baseline readback mismatch: -5
```

This happened during the **immediate** readback inside its `.disable()` callback. The clock word had settled back to the exact baseline by the later independent read. The existing callback only cleared `saved_valid` on immediate readback success; therefore it might retain a software rollback latch even though the physical PMGR baseline is correct. Further active tests on the current boot were intentionally stopped.

The kernel reports 32,000 Hz for the disabled reference-clock configuration. The active divider word is consistent with about 32.8 kHz from a nominal 24 MHz parent, but **no physical output frequency has been measured**. CCF may cache the prior disabled-rate calculation.

## Source correction: patch 0004

`patches/0004-n71-touch-clock-bounded-restore-settle-rfc.patch` changes the Apple touch-clock provider's **normal disable** and **error rollback** paths to:

1. Write the complete, captured original register word.
2. Poll for the **exact original word** with the PMGR BUSY bit clear.
3. Stop after a hard maximum of **50 ms**, with 10 μs polling interval.
4. Clear the saved-baseline latch only on a verified exact match; keep the failure state otherwise.

This is a fail-closed behavior change; it does not relax the baseline comparison or silently treat an error as success. It changes no Apple firmware, panel calibration, external touch regulator, SPI framing or NAND storage.

The patch was applied to the isolated N71 kernel with earlier Z2 rollback, strict HBPP read-validation and bounded `REQ_CAL` handling. The modified ARM64 clock object was rebuilt with GCC 15.2 and the kernel was fully relinked. **69/69** automated regression tests plus the existing synthetic HBPP audit passed. Those results remain **offline** until the new image is actually loaded.

## New RAM-only ISO

| Artifact | SHA-256 |
| --- | --- |
| **New Ventoy ISO** `CYBERDECK_A9_Z2_CLOCK_SETTLE_TEST.iso` | `0c64c4edbe5c30fe85611c049088863875228672ea0c9d4c680a1746138b68ca` |
| New ARM64 `Image.gz` | `28f7ca057e55a315f7338a2b592afcce300fa39a45d46fff403e65c512710289` |
| New m1n1 RAM-only payload | `0e4d6aca08d40f49233a3180fcd4ee0229ba042038759fa1e4342fccbc456687` |

Size: **103,481,344 bytes**. The final ISO's initramfs was extracted and verified byte-identical with the compressed build output, passed `xz -t`, **16/16 embedded SHA-256 checks**, all **7 launcher shell-syntax checks**, and retained BIOS/UEFI El Torito boot entries.

Five separate rollback images remain inside the ISO:

- `./03-spi2-off.sh`: SPI2-OFF
- `./04-known-good.sh`: original known-good
- `./05-host-only.sh`: SPI2-HOST-ONLY
- `./06-provider-only.sh`: clock-provider-only
- `./07-prior-z2-safe.sh`: the previous **live-booted** Z2 safe-patched kernel

`./02-linux.sh` loads the new clock-settling kernel in RAM, with the **Z2 child still disabled**. This is the next kernel/provider smoke test, **not** a touch firmware/calibration test. A separately gated provider clock pulse should only be repeated after verifying that the new image boots and the baseline is unchanged.

## Next supervised physical gate

The ISO is staged on the authorized Dell only; it is **not yet transferred to the SanDisk Ventoy key**. Before copying, the operator must physically unplug the iPhone Lightning cable and attach the existing SanDisk Ventoy USB key. The dedicated copy helper pins the ISO SHA-256 and refuses to modify unidentified USB disks or overwrite existing images. Once copied and unmounted, Dell F12 → Ventoy → this exact ISO, followed by DFU → PongoOS → `./02-linux.sh`, loads the new RAM-only Linux kernel.

On the new boot, first verify kernel identity and the unchanged Z2-off/PMGR baseline. Then perform a single 20 ms guarded clock-provider cycle and require **both** an exact later PMGR readback and **no driver rollback warning**. Only then consider controlled analog power and HBPP status-only identification on the aftermarket panel.

No private device identifiers, calibration blobs, firmware payloads, personal emails, or raw per-device provisioning data are published here.
