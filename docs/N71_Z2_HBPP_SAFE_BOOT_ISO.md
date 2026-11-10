# N71/S8000 — Z2 HBPP safe-patched RAM boot ISO

**Date:** 2026-11-10
**Status:** **OFFLINE VERIFIED; SUBSEQUENT LIVE BOOT AND 100-CYCLE SPI2 HOST STRESS PASSED.** Z2 touch activation still untested.

See [the verified physical boot and SPI2 stress report](N71_Z2_HBPP_SAFE_KERNEL_LIVE_BOOT.md) for the subsequent on-device results.

## Why this image exists

Three previously reviewed kernel-source improvements have been integrated into a **single new ARM64 Linux image**:

1. Z2 first-HBPP-handshake error now reaches the touch power/reset cleanup path.
2. A malformed HBPP memory/register-read status or checksum is rejected before accepting a controller-version word.
3. While **waiting for calibration `ACK_DATA` only**, transient `REQ_CAL` no longer aborts immediately; the finite 50-poll budget and strict ACK requirement remain.

The fourth hardware property is a safety gate: **the Z2 SPI child is still disabled** in the boot Device Tree. This is a **kernel stability and provider registration smoke test**, not a working touchscreen, a calibration retry or a claim that the fixes have already worked on the physical panel. The touchscreen installed on this iPhone is a non-original replacement that the user confirmed worked correctly under iOS.

## Build provenance and integrity

The Linux sources are based on the already tested Samsung A9/N71 tree at `68aadac820d0`. A separate, private kernel-source worktree contains exactly the modified Apple Z2 and touch clock files. Three public GPL RFC patches document these changes:

- `patches/0001-n71-z2-rollback-and-touch-ref-clock-rfc.patch`
- `patches/0002-n71-hbpp-read-strict-validation-rfc.patch`
- `patches/0003-n71-hbpp-cal-data-reqcal-pending-rfc.patch`

The kernel was rebuilt using the same GCC 15.2 ARM64 cross-toolchain and baseline configuration as the previously booted kernel, in a **distinct output tree**. Existing source files and known-good boot images were preserved. The linked `vmlinux` exists, `Image.gz` passed gzip integrity verification, and both changed kernel driver objects were rebuilt.

| Artifact | SHA-256 |
| --- | --- |
| **New Ventoy ISO** `CYBERDECK_A9_Z2_HBPP_SAFE_TEST.iso` | `dec928f133bb4439fa1e32b821d2557cb880f4d57d68309e81da3dc92c0fe6c5` |
| New ARM64 `Image.gz` | `cf10e696910595ce673e0f3b6968127bafc7f92aabfd6761dda1c175b50f8c2c` |
| New m1n1 RAM-only experimental payload | `857e14d2b0ec33af3569f5f87baa6c5498e813a3416d1d04c8b87000ba430992` |
| Reused **on-device tested** clock-provider-only payload | `8b0a1a1ac9927e0ab89701523e1276f454739e46973d0d79644694ef231004df` |
| Reused SPI2-HOST-ONLY fallback | `97f9adf30f4be11cd2722a5773167db0d54ca93296e52da8fe93fc68858c79a1` |
| Reused SPI2-OFF fallback | `0c93711939a7d847c9ef323e16205bda0160253cc4021f4bdcc4b5821f94cc93` |
| Original known-good fallback | `220e086184d0cfdec1f04f3ea038e4c439378c8add6610727357fd2d4503c032` |

ISO size: **92,798,976 bytes** (approximately 88.5 MiB). The original upstream palen1x BIOS/UEFI El Torito boot structures are retained.

## Completed offline acceptance

- The new m1n1 + ARM64 payload was packed independently of all known-good images.
- The final ISO's extracted `/boot/initramfs.xz` matched the locally generated image **byte for byte**.
- The extracted archive passed `xz -t`; the ARM64 kernel passed `gzip -t`.
- **All 14 embedded toolkit files** passed `sha256sum -c SHA256SUMS`.
- All six launcher scripts passed `sh -n`.
- The Linux Device Tree preserved the already live-tested `touch_ref` provider enabled, SPI2 host enabled and Z2 child disabled.
- An initial absent-Ventoy check confirmed the copy helper refuses to touch any disk unless a matching existing SanDisk/Ventoy partition is found. No USB transfer has yet occurred.

## Recovery tools embedded in the ISO

| Script | Action |
| --- | --- |
| `01-pongo.sh` | Normal iOS/Recovery → guided DFU → PongoOS |
| `02-linux.sh` | **New safe-patched kernel**, Z2 child disabled |
| `03-spi2-off.sh` | Previously live-tested SPI2-OFF kernel |
| `04-known-good.sh` | Original preserved Linux baseline |
| `05-host-only.sh` | Previously live-tested SPI2-HOST-ONLY kernel |
| `06-provider-only.sh` | **Last known on-device stable touch-reference-clock provider** kernel |

Any `02`–`06` transfer requires the phone in PongoOS at USB `05ac:4141`. A failed RAM boot may require physical iPhone DFU recovery. No tools here require writing iOS NAND.

## Next operator-assisted step (not done yet)

1. Keep the current stable Linux session active on the phone. Physically disconnect Lightning from the Dell and insert the existing SanDisk Ventoy USB key.
2. Copy the ISO with the verified local helper, check destination SHA-256 and unmount Ventoy before removal.
3. Boot Dell F12 → SanDisk Ventoy → **`CYBERDECK_A9_Z2_HBPP_SAFE_TEST.iso`** in normal mode.
4. In palen1x shell, run `cd /opt/cyberdeck && sha256sum -c SHA256SUMS`, expecting 14 OK. Confirm Ventoy is not mounted before removing the USB key and reattaching iPhone.
5. Physically return iPhone from its current Linux RAM session to DFU; load PongoOS and confirm `05ac:4141`.
6. Run `./02-linux.sh` for **the first RAM-only smoke boot**. Stop if no BusyBox shell or USB gadget reappears; retain the known fallback scripts.
7. Restart **only the Dell** into Kubuntu and compare the phone's `uname -a`, `touch_ref` enable count, SPI2 domain/clock, no unintended Z2 input, dmesg and USB shell. The new kernel may have a `-dirty` local-version suffix because its source has three uncommitted experimental patches.
8. Do **not** claim that the calibration problem is fixed until a separately gated powered Z2 child test actually returns the correct ACK and full-resolution touch reports.

No private device calibration, PongoOS binary, runtime ADT, unique hardware data or full firmware image is included in this public report.
