# N71/S8000 SPI2 host-only — first on-device validation

**Date:** 2026-11-10
**Status:** **PASS: SPI host probe, generic power domain ON, USB shell available; touch remains disabled.**

## Purpose and scope

The `01-spi2-host-only` stage was designed as an intermediate, RAM-only hardware bring-up experiment after a successful `00-spi2-off` boot. It sets `/soc/spi@20a088000/status` to `okay` but leaves `touchscreen@0/status` as `disabled`. The goal is to prove that the Apple S5L SPI controller can probe on the real Samsung A9 (Apple S8000/N71) without activating a touchscreen peripheral.

This test **does not** validate Z2 calibration, SPI transfers, touchscreen gestures, Wi-Fi, or Bluetooth.

## Boot record

- Dell XPS loaded the pinned Ventoy ISO `CYBERDECK_A9_SPI2_HOST_ONLY_TEST.iso` through palen1x.
- The operator entered DFU, reached PongoOS `05ac:4141`, and ran `/opt/cyberdeck/02-linux.sh`.
- PongoOS confirmed `Uploaded 11249548 bytes` and reported `LIBUSB_ERROR_IO` during the USB transition.
- The phone display independently showed `apple-s5l-spi 20a088000.spi: S5L SPI controller, ref clock 48000000 Hz` and the BusyBox debug shell.
- The Dell was rebooted into Kubuntu *without rebooting the phone*. The host then enumerated USB `05ac:4142`, assigned `172.16.42.2/24`, received 3/3 USB ping replies, and successfully opened the phone's BusyBox root shell on `172.16.42.1:23`.

## On-device evidence (read-only)

| Check | Observed output | Assessment |
| --- | --- | --- |
| Kernel | `Linux ... 7.3.0-rc1-g68aadac820d0 ... aarch64` | New experimental build boots |
| Device Tree compatible | `apple,n71`, `apple,s8000`, `apple,arm-platform` | Correct phone |
| SPI controller DT status | `/proc/device-tree/soc/spi@20a088000/status` -> `okay` | Expected stage |
| Touch child DT status | `/proc/device-tree/soc/spi@20a088000/touchscreen@0/status` -> `disabled` | Expected safety gate |
| Driver binding | `/sys/bus/platform/devices/20a088000.spi/driver` -> `apple-s5l-spi` | **PASS** |
| SPI controller class | `/sys/class/spi_master/spi0` exists | **PASS** |
| Reference clock | Kernel log: `48000000 Hz` | **PASS** |
| SPI2 generic power domain | `/sys/kernel/debug/pm_genpd/spi2/current_state` -> `on` (read repeatedly) | **PASS** |
| Comparison with SPI2-OFF | Previous physical boot showed `off-0` | Stage switch verified |
| Peripheral SPI devices | `/sys/bus/spi/devices` empty | No touch probe, as expected |
| Input | Only `gpio-keys` event0 | No touchscreen input, as expected |
| Runtime PM | Platform controller's `power/runtime_status` -> `unsupported` | **No runtime-suspend claim** |
| Loaded modules | `/proc/modules` empty | SPI host driver built into this kernel |
| Remote shell | Working USB-gadget root Telnet | **PASS** |

The filtered dmesg contains a prior `g_multi` gadget probe failure (`-22`), followed by successful ramdisk-configured USB gadget operation. A `serial serial0-0: deferred probe pending: (reason unknown)` line appears at approximately 10.7 seconds. No Oops or kernel panic was observed in the filtered logs. The deferred serial probe has **not** been attributed to SPI2; it requires separate root-cause analysis.

## Interpretation

The real-device transition from SPI2-OFF to SPI2-HOST-ONLY demonstrates that the SPI master driver can bind and keep the dedicated generic power domain active, without registering the Z2 touchscreen child.

These observations **do not establish safe power-down/rebind behavior**, because the host driver is built into the running kernel, runtime PM reports `unsupported`, and no driver unbind/rebind was attempted. They also do not prove that the bus can transmit or receive useful bytes. The original bootloader ACK problem remains unresolved.

Next gated work: produce a matching modular host variant with explicit power-domain cleanup review and safe power-down recovery; validate the stage offline before any live unbind or touch power action. Only then move to a controlled Z2 presence/protocol test with a preserved known-good RAM boot image.

## Integrity and privacy

- No iOS NAND writes, permanent bootloader changes, touchscreen calibration requests, or SPI register writes were deliberately initiated by the diagnostic commands.
- Root Telnet is unencrypted and should remain restricted to the isolated USB gadget interface.
- Public report contains no individual phone provisioning dumps, iOS identity, personal account data, or private firmware.
