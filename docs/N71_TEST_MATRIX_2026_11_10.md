# N71/S8000 cyberdeck — evidence-based test matrix

**Date:** 2026-11-10
**Board:** iPhone 6s, Samsung Apple A9, N71/S8000; **user-confirmed non-original replacement display** (controller revision unknown)
**Working runtime:** ARM64 Linux 7.3.0-rc1-g68aadac820d0-dirty **build #5** (bounded clock-settling fix and safe Z2 patches), BusyBox RAM root shell, USB gadget.

This matrix separates **live hardware results**, **offline results**, and **still-blocked functionality**. Tests on another device or an earlier kernel release are not treated as successes on the current runtime.

| Subsystem / gate | Status | Evidence and next requirement |
| --- | --- | --- |
| Boot to native Linux | **LIVE PASS** | Current kernel is running on the phone without persistent iOS NAND modifications |
| USB network and root shell | **LIVE PASS** | `05ac:4142`, `172.16.42.1`, **100/100 ping replies after the integrated HBPP test** (0% loss, average 2.370 ms) |
| Safe Z2-patched kernel RAM boot | **LIVE PASS: Z2 DISABLED** | `7.3.0-rc1-g68aadac820d0-dirty`, confirmed directly after DFU/PongoOS boot; 25/25 post-stress USB pings, no kernel fault signatures. [Live evidence](N71_Z2_HBPP_SAFE_KERNEL_LIVE_BOOT.md) |
| SPI2 controller probe | **LIVE PASS** | `apple-s5l-spi`, `spi0`, 48 MHz controller reference |
| SPI2 domain baseline | **LIVE PASS** | `off-0` in SPI2-OFF test, `on` in host-only test |
| SPI2 binding-cycle stress | **LIVE PASS** | **100/100** guarded sysfs platform unbind/rebind cycles on the **new patched kernel**, power `on → off-0 → on`, clock count `1 → 0 → 1`; Z2 clock stayed disabled |
| Touch reference-clock provider-only | **LIVE PASS: PROVIDER REGISTRATION** | `touch_ref` present, Linux clock framework reports 32,000 Hz with enable/prepare counts `0/0`, PMGR candidate baseline `0x800002ee`; no electrical waveform verification or Z2 probe. Separate RAM-only ISO: 12/12 checksums |
| Touch reference clock enable/rollback | **LIVE PASS, BUILD #5** | On-device 20 ms CCF pulse: PMGR `0x800002ee → 0x000802dc → 0x800002ee`; enable/prepare counts `0/0`, no rollback warning. Exact physical output frequency unmeasured. [Live verification](N71_TOUCH_CLOCK_AND_ANALOG_LIVE_VALIDATION.md) |
| Touch analog rail | **LIVE PASS; CORE READ-ONLY** | Chestnut `0x05: 0x0f → 0x1f → 0x0f`, ~59 ms actual enabled interval; delayed backup watchdog confirmed baseline, independent regulator/clock/reset snapshots match. Core PMU `0x319=0x01` unchanged. [Live verification](N71_TOUCH_CLOCK_AND_ANALOG_LIVE_VALIDATION.md) |
| HBPP/Z2 bootloader communication | **LIVE PASS: TWO STRICT READS** | On kernel #5: integrated analog/clock/reset/SPI 1 MHz mode 3 gave status REQ_CAL/IDLE, ATN IDLE, validated READ_DATA 0x4c39/checksum 0x0166 and version 0x434d15c1, second validated read. Watchdog and baseline PASS; Z2 automatic firmware child stays disabled. [Live report](N71_HBPP_STATUS_ONLY_LIVE_SUCCESS.md) |
| HBPP calibration DATA acknowledgment | **NOT PASSED** | Prior N71 runs returned `REQ_CAL=0x1f01` or `IDLE=0x4879`; required `ACK_DATA=0x4bc1` absent. Source poller incorrectly stopped at first `REQ_CAL`; bounded correction compiled offline but not yet tested on phone. Replacement-panel firmware/calibration compatibility is unknown |
| Full-resolution multitouch | **NOT PASSED** | Actual aftermarket panel worked normally under iOS (user-confirmed), but Linux controller ID/firmware compatibility remain unknown. Prior separate N71 research reached only coarse/quadrant reports; acceptance requires real 750 × 1334 multitouch evdev data |
| Bluetooth BCM4350C5 | **EARLIER KERNEL PASS, CURRENT PENDING** | Old RAM Linux validated loaded N71-matched firmware and passive BLE advertisements; current kernel has Bluetooth stack but **no `hci0`** until matching PMIC GPIO / serdev setup is validated |
| Wi-Fi BCM4350 PCIe | **BLOCKED** | Private ADT metadata maps WLAN to PCIe **port 1**, while current kernel enumerates **zero PCIe devices**. Host controller/DART link and board-matched firmware are not yet initialized |
| Isolation of storage and baseband PCIe | **REQUIRED SAFETY GATE** | Never use port 0 (storage) or port 2 (baseband) for experimentation; prototype WLAN on port 1 separately |
| Kernel Z2 cleanup and clock rollback | **CLOCK PATH LIVE PASS; Z2 PATH NOT YET EXERCISED** | Bounded clock disable rollback now verified on actual N71, but Z2 firmware/calibration error paths remain UNTESTED while touch child is disabled |
| Regression suite and privacy gate | **PASS** | Synthetic ACK sequences, DATA frames, bounded clock-settling regression, strict HBPP controller-ID model, privacy pre-push guard |

## Experimental sequence

1. **Clock provider-only live boot:** validate standalone registration and idle state, with the Z2 peripheral, regulators and firmware still disabled. No clock-enable write during the provider-only stage. **Later live result:** registered `touch_ref`, clk enable/prepare counts `0/0`; this is not a calibrated physical frequency measurement.
2. **Power-state baseline and rollback:** **PASSED separately** for clock and analog rail on the build #5 phone; main PMU and pinctrl stable. The combined status-only Z2 sequence remains untested. [Results](N71_TOUCH_CLOCK_AND_ANALOG_LIVE_VALIDATION.md).
3. **Identify the installed aftermarket panel:** DONE at the controller-protocol level: two checksum-correct HBPP reads and the 0x434d15c1 version register. Exact aftermarket panel vendor and compatibility with private calibration are still unknown. [Live proof](N71_HBPP_STATUS_ONLY_LIVE_SUCCESS.md).
4. **Single-variable HBPP bring-up:** run bounded status-only checks before any calibration, then compare one framing hypothesis at a time against the verified 10-byte-header DATA format. A status word not equal to `0x4bc1` is never considered successful acknowledgment.
5. **High-resolution evdev acceptance:** identify *actual* changing full-range X/Y and correct releases with two independent contacts; quadrants alone are not accepted.
6. **New-kernel Bluetooth revalidation:** build and check a PMIC GPIO driver module against the exact running kernel ABI before board-matched firmware installation in RAM; confirm `hci0` and passive BLE reception without exposing user identifiers.
7. **Isolated PCIe port-1 Wi-Fi:** only after static DT and host/DART register audits, validate link and enumeration, then recover the correct BCM4350 firmware to RAM. Avoid touching storage/baseband ports.

The short-term goal is a **reproducible Linux hardware platform**, followed by usable multitouch, Wi-Fi and Bluetooth in a full-screen native cyberdeck. Passing a boot or a host controller test must never be misrepresented as a functional touchscreen or Wi-Fi link.

## Privacy and source handling

No raw Apple Device Tree, unique device calibration, provisioning, personal account data or firmware image is included. The public project records portable code, test contracts and evidence summaries only. Full firmware/calibration binaries remain on the authorized machine.

Background: [prior documented N71 coarse-touch experiments](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/drivers/touch.md) and the [upstream Apple Z2 driver](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/4b11f2336e23d5c55b76591bd8ac39b059f68ad0/drivers/input/touchscreen/apple_z2.c).
