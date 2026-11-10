# N71/S8000 cyberdeck — evidence-based test matrix

**Date:** 2026-11-10
**Board:** iPhone 6s, Samsung Apple A9, N71/S8000
**Working runtime:** ARM64 Linux 7.3.0-rc1-g68aadac820d0, BusyBox RAM root shell, USB gadget.

This matrix separates **live hardware results**, **offline results**, and **still-blocked functionality**. Tests on another device or an earlier kernel release are not treated as successes on the current runtime.

| Subsystem / gate | Status | Evidence and next requirement |
| --- | --- | --- |
| Boot to native Linux | **LIVE PASS** | Current kernel is running on the phone without persistent iOS NAND modifications |
| USB network and root shell | **LIVE PASS** | `05ac:4142`, `172.16.42.1`, **100/100 ping replies** (0% loss, average 2.559 ms) |
| SPI2 controller probe | **LIVE PASS** | `apple-s5l-spi`, `spi0`, 48 MHz controller reference |
| SPI2 domain baseline | **LIVE PASS** | `off-0` in SPI2-OFF test, `on` in host-only test |
| SPI2 binding-cycle stress | **LIVE PASS** | **10/10** guarded sysfs platform unbind/rebind cycles, clock count `1 → 0 → 1` |
| Touch reference-clock provider-only | **OFFLINE PASS; LIVE PENDING** | Separate Ventoy ISO `CYBERDECK_A9_TOUCH_REF_PROVIDER_TEST.iso`: one DT status change, **12/12** checksums, three recovery kernels |
| Touch reference physical clock | **BLOCKED** | PMGR register mappings and signal characteristics require on-device readbacks, with exact state restoration |
| Touch analog/core suppliers | **BLOCKED** | Board-matched PMU/Chestnut and GPIO reset need baseline and restore acceptance before Z2 boot |
| HBPP/Z2 bootloader communication | **PARTIAL, PRIOR SESSION** | Short status/register handshake observed in earlier experiments; current host-only kernel intentionally does not enable the touch child |
| HBPP calibration DATA acknowledgment | **NOT PASSED** | Prior N71 runs returned `REQ_CAL=0x1f01` or `IDLE=0x4879`; required `ACK_DATA=0x4bc1` absent |
| Full-resolution multitouch | **NOT PASSED** | A separate HoolockLinux N71 research branch reached coarse/quadrant detection but no useful full-resolution X/Y; acceptance requires real 750 × 1334 multitouch evdev data |
| Bluetooth BCM4350C5 | **EARLIER KERNEL PASS, CURRENT PENDING** | Old RAM Linux validated loaded N71-matched firmware and passive BLE advertisements; current kernel has Bluetooth stack but **no `hci0`** until matching PMIC GPIO / serdev setup is validated |
| Wi-Fi BCM4350 PCIe | **BLOCKED** | Private ADT metadata maps WLAN to PCIe **port 1**, while current kernel enumerates **zero PCIe devices**. Host controller/DART link and board-matched firmware are not yet initialized |
| Isolation of storage and baseband PCIe | **REQUIRED SAFETY GATE** | Never use port 0 (storage) or port 2 (baseband) for experimentation; prototype WLAN on port 1 separately |
| Kernel Z2 cleanup and clock rollback | **OFFLINE PASS** | Patch applies to current N71 source, changed ARM64 objects compile, baseline restoration has readback checks |
| Regression suite and privacy gate | **PASS** | **36/36** tests plus synthetic HBPP packet audit, GitHub noreply pre-push guard |

## Experimental sequence

1. **Clock provider-only live boot:** validate standalone registration and idle state, with the Z2 peripheral, regulators and firmware still disabled. No clock-enable write during the provider-only stage.
2. **Power-state baseline and rollback:** independently verify the PMGR clock candidate, main PMU, Chestnut analog regulator, pinctrl, reset line, and idle USB stability; stop on any mismatched raw readback.
3. **Single-variable HBPP bring-up:** run bounded status-only checks before any calibration, then compare one framing hypothesis at a time against the verified 10-byte-header DATA format. A status word not equal to `0x4bc1` is never considered successful acknowledgment.
4. **High-resolution evdev acceptance:** identify *actual* changing full-range X/Y and correct releases with two independent contacts; quadrants alone are not accepted.
5. **New-kernel Bluetooth revalidation:** build and check a PMIC GPIO driver module against the exact running kernel ABI before board-matched firmware installation in RAM; confirm `hci0` and passive BLE reception without exposing user identifiers.
6. **Isolated PCIe port-1 Wi-Fi:** only after static DT and host/DART register audits, validate link and enumeration, then recover the correct BCM4350 firmware to RAM. Avoid touching storage/baseband ports.

The short-term goal is a **reproducible Linux hardware platform**, followed by usable multitouch, Wi-Fi and Bluetooth in a full-screen native cyberdeck. Passing a boot or a host controller test must never be misrepresented as a functional touchscreen or Wi-Fi link.

## Privacy and source handling

No raw Apple Device Tree, unique device calibration, provisioning, personal account data or firmware image is included. The public project records portable code, test contracts and evidence summaries only. Full firmware/calibration binaries remain on the authorized machine.

Background: [prior documented N71 coarse-touch experiments](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/drivers/touch.md) and the [upstream Apple Z2 driver](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/4b11f2336e23d5c55b76591bd8ac39b059f68ad0/drivers/input/touchscreen/apple_z2.c).
