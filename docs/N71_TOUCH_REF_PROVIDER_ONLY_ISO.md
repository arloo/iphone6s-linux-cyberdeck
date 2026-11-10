# N71/S8000 — isolated touch reference-clock provider stage

**Date:** 2026-11-10

**Status:** **LIVE PASS for clock-provider registration.** The candidate was subsequently booted successfully on the physical iPhone 6s. Clock output signaling and Z2 are still unverified.

## Objective

Isolate registration of the Apple A9/S8000 touch-reference clock *provider* before enabling the Z2 touchscreen, analog regulator, or core regulator. This is intentionally a single-variable Device Tree test on top of the **already boot-tested SPI2-HOST-ONLY** kernel and ramdisk.

Registration is not the same as clock enable. The intended driver probe registers the `touch_ref` 32.768 kHz clock via the common clock framework; the Z2 child remains disabled and is therefore not allowed to request that clock. The early stage must not trigger calibration, firmware upload, or SPI transfers.

## Exact single-node DT delta

The source and candidate S8000 N71 Device Tree blobs were decompiled and compared; the **sole** textual difference was:

```diff
 /soc/power-management@20e000000/clock-controller@78000 {
-    status = "disabled";
+    status = "okay";
 };
```

The SPI2 controller stays `okay`, its `touchscreen@0` child stays `disabled`, and the full original compressed ARM64 kernel `Image.gz` is **byte-identical** to the previously live-tested SPI2-HOST-ONLY kernel. Both touch power regulator providers remain disabled. No changes were made to pinmux, USB, PCIe, iOS NAND or Bluetooth firmware.

The kernel configuration includes `CONFIG_COMMON_CLK_APPLE_TOUCH=y`, so the candidate should exercise an actual clock-provider driver probe.

## Offline image and recoveries

| Artifact | SHA-256 |
| --- | --- |
| New Ventoy-compatible ISO: `CYBERDECK_A9_TOUCH_REF_PROVIDER_TEST.iso` | `3eb1410c02dff60363161928c4c8d84ea0ceee576094323e40e086d7a58c52b9` |
| Provider-only m1n1 RAM payload | `8b0a1a1ac9927e0ab89701523e1276f454739e46973d0d79644694ef231004df` |
| Original SPI2-HOST-ONLY payload (live-tested) | `97f9adf30f4be11cd2722a5773167db0d54ca93296e52da8fe93fc68858c79a1` |
| SPI2-OFF payload (live-tested) | `0c93711939a7d847c9ef323e16205bda0160253cc4021f4bdcc4b5821f94cc93` |
| Older original known-good payload | `220e086184d0cfdec1f04f3ea038e4c439378c8add6610727357fd2d4503c032` |

The new ISO is 82,182,144 bytes. The inner initramfs was extracted from the finished ISO, matched the generated image **byte for byte**, passed `xz -t`, and **12/12 embedded SHA256SUMS** checks passed. All five launcher scripts passed `sh -n`. ISO boot metadata retains both BIOS and UEFI El Torito entries.

Scripts available once PongoOS is confirmed at USB `05ac:4141`:

- `./02-linux.sh` — new touch reference-clock provider-only payload
- `./03-spi2-off.sh` — previously verified SPI2-OFF baseline
- `./04-known-good.sh` — original known-good baseline
- `./05-host-only.sh` — previously verified SPI2-HOST-ONLY baseline

## Subsequent live-device result (2026-11-10)

The operator booted this exact RAM-only ISO through PongoOS on the N71 phone. It reached the BusyBox root shell and USB gadget interface; the Dell regained direct read-only root-shell access after returning to Kubuntu. Live evidence:

- Device Tree \`clock-controller@78000/status\` reported \`okay\`, while \`touchscreen@0/status\` remained \`disabled\`.
- \`/sys/kernel/debug/clk/touch_ref\` existed with a calculated, **disabled** reference rate of \`32000 Hz\` (not an observed electrical waveform).
- Touch clock enable and prepare counts were both **0**; SPI2 generic power domain \`on\` and the SPI master \`spi0\` remained registered.
- No touch child input or \`spi0.0\` peripheral was registered. The filtered kernel log showed no panic or Oops.
- Afterward, **100 guarded SPI2 driver detach/rebind cycles** completed with domain \`on → off-0 → on\`, clock count \`1 → 0 → 1\` and the touch clock remaining disabled; the USB shell stayed reachable.

**The recorded 32,000 Hz is a software calculation from the inactive divider, not a measurement of the required active 32,768 Hz signal.** No on-device Z2 calibration was attempted during this stage.

## Physical test protocol (as originally designed, now completed for registration only)

1. Preserve the currently running SPI2-HOST-ONLY session until the human operator intentionally moves from Lightning to the SanDisk Ventoy USB. Only an existing SanDisk VID 0781 Ventoy partition may receive the new ISO; no disk formatting or overwrites.
2. Boot the new ISO through the existing F12/Ventoy/palen1x path. Check all 12 SHA-256 entries and confirm the Ventoy filesystem is unmounted before exchanging the USB cable.
3. Physically restart the iPhone, enter DFU, load PongoOS and confirm `05ac:4141` before transferring the new RAM payload.
4. If Linux reaches shell, return only the Dell to Kubuntu, keeping the iPhone alive. Verify the board, `05ac:4142`, root USB shell, SPI2 PM domain and driver.
5. Confirm the Device Tree shows the clock provider enabled but the Z2 child disabled; inspect `dmesg` and `/sys/kernel/debug/clk/touch_ref` for **registration without clock enable**. If available, inspect the original PMGR word read-only; compare it against the pre-probe baseline.
6. Confirm no new `spi0.0` peripheral, Z2 input device, regulator enable, spontaneous CS activity or probe error. Any unexpected behavior fails the stage; use manual DFU/PongoOS recovery and the verified host-only fallback.
7. Do not request `clk_prepare_enable()` or write PMGR/Chestnut registers in this provider-only stage. That is a different, separately gated hardware experiment.

## Limitations

The PMGR touch clock register offset is based on related Apple SoC mapping and earlier board tests; registering a provider does **not** electrically prove output frequency or signal integrity on N71. Boot stability and correct read-only probe behavior must be demonstrated on this specific phone. No success is claimed for touch, calibration ACK, BLE initialization or PCIe Wi-Fi.

All images and firmware remain private on the authorized host. This public record contains checksums and procedures only, with no per-device firmware, calibration, serial number or user account data.
