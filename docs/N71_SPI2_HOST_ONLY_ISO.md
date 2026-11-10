# N71/S8000 — SPI2 host-only RAM boot candidate

**Date:** 2026-11-10

**Status:** ISO verified offline and subsequently **boot-tested on the physical iPhone 6s**. See [on-device validation](N71_SPI2_HOST_ONLY_LIVE_VALIDATION.md) for measured hardware results.

## Why this candidate exists

The conservative `00-spi2-off` kernel has already booted on the physical Samsung A9 iPhone 6s. Native Linux USB gadget, a BusyBox root shell and the generic SPI2 power-domain state `off-0` were confirmed. The new `01-spi2-host-only` candidate changes exactly one semantic Device Tree property relative to that baseline: the S8000 SPI2 controller node becomes `status = "okay"` while the `apple,n71-multitouch` child stays disabled.

The on-device test should therefore isolate initialization of the SPI host, not attempt touch calibration.

## Offline package

A separate palen1x hybrid ISO was built, preserving original BIOS/UEFI boot entries:

| Item | Verification |
| --- | --- |
| Filename | `CYBERDECK_A9_SPI2_HOST_ONLY_TEST.iso` |
| Size | 71,499,776 bytes |
| SHA-256 | `b3d184ed0b0d497ff1a96df654219b396667b5de360e8376ded574585b470915` |
| Experimental host-only payload | `97f9adf30f4be11cd2722a5773167db0d54ca93296e52da8fe93fc68858c79a1` |
| Previously verified SPI2-OFF payload | `0c93711939a7d847c9ef323e16205bda0160253cc4021f4bdcc4b5821f94cc93` |
| Original known-good payload | `220e086184d0cfdec1f04f3ea038e4c439378c8add6610727357fd2d4503c032` |

The ISO was reconstructed from the pinned palen1x upstream image, with all three Linux payloads placed into the RAM initramfs. Its extracted initramfs matched the locally generated compressed image **byte for byte** and passed `xz -t`. All **10 embedded toolkit files** passed `sha256sum -c SHA256SUMS`. Both fallback launcher scripts passed `sh -n`. No phone or internal storage was accessed during this packaging.

The user’s previous separate palen1x ISO and Linux payloads were **not overwritten**.

## How to select a boot payload (once PongoOS is confirmed)

| Script | Action |
| --- | --- |
| `./02-linux.sh` | Load experimental **SPI2 host-only** Linux into RAM |
| `./03-spi2-off.sh` | Load the previously tested **SPI2-OFF** Linux into RAM |
| `./04-known-good.sh` | Load the older known-good Linux into RAM |

Only use these loaders after PongoOS appears on the phone and enumerates as `05ac:4141`. `LIBUSB_ERROR_IO` can appear during the USB handoff and is not, alone, a boot failure. Confirm a fresh kernel boot and a working USB network shell.

## Device-attended acceptance test

1. Boot the separate ISO from Ventoy, verify all 10 files, and reattach the Lightning cable after confirming the live medium is RAM-only.
2. Recover the iPhone from its current RAM Linux session via a physical attended reboot to normal iOS/Recovery/DFU, then follow the previously validated PongoOS procedure. Do not flash, restore or repartition iOS.
3. Choose `./02-linux.sh` after confirming `05ac:4141`.
4. Confirm the new kernel using `uname -a`, USB `05ac:4142`, root shell, N71/S8000 board identity, `/sys/bus/spi/devices`, driver probe messages and `/sys/kernel/debug/pm_genpd/spi2/current_state`.
5. Inspect `/proc/bus/input/devices` to confirm the Z2 touch device was **not** activated and no calibration attempted.
6. Stop at any unexpected panic, USB disconnect without re-enumeration, or PM-domain error. Recover physically using the alternative boot scripts if necessary.

**Lifecycle follow-up:** This candidate has the S5L host driver compiled **into the kernel**, so `rmmod` is not possible. However, **platform driver sysfs unbind/rebind was subsequently validated on the physical phone** with an independent timed rebind watchdog: domain `on → off-0 → on`, SPI reference-clock count `1 → 0 → 1`, controller `spi0` restored. See [live power-cycle validation](N71_SPI2_POWER_CYCLE_LIVE_VALIDATION.md). A matching modular kernel is only needed to test the distinct `rmmod`/`insmod` lifecycle. Earlier experimental `.ko` files must not be loaded into an incompatible kernel.

## Current staging state

The ISO was later copied to SanDisk Ventoy and reverified on the destination. The physical host-only Linux boot subsequently reached the BusyBox shell and registered SPI controller `spi0` with the SPI2 generic power domain `on`. The local copy script validates the SanDisk USB vendor ID, source and destination hashes, rejects overwriting any ISO, and safely unmounts Ventoy.

A successful SPI2-HOST-ONLY boot and SPI master registration **are now confirmed** in the [live validation report](N71_SPI2_HOST_ONLY_LIVE_VALIDATION.md). No SPI peripheral transfer, Z2 ACK, multitouch or Wi-Fi operation is claimed.
