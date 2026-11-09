# Technical research leads — not confirmed on this device

This project tests the **Samsung A9 iPhone 6s (N71/S8000)**. Results from N71m/S8003, A10 iPhone 7, iPad 7 or Apple Silicon MacBooks must not be described as tested on our device without hardware evidence.

## Touch: upstream Apple Z2

- The Linux kernel contains `drivers/input/touchscreen/apple_z2.c`, originally developed for Apple Z2 touch devices. Its Kconfig key is `CONFIG_TOUCHSCREEN_APPLE_Z2` and it requires SPI support.
- The tested kernel config has `CONFIG_INPUT_TOUCHSCREEN` disabled. The driver source exists in our kernel tree but no N71 touchscreen was bound at runtime.
- Start from the [Apple Z2 Linux driver series](https://lists.infradead.org/pipermail/linux-arm-kernel/2025-February/997546.html), then identify **actual N71 controller wiring and firmware requirements**. The existing implementation's other-device compatible strings do not establish N71 support.
- An independent [HoolockLinux touchscreen bring-up study](https://github.com/Pauli1Go/HoolockLinux-bringup-docs/blob/main/docs/touch.md) documents Z2/SIO/DMA issues on J172. This is background research, **not** a verified N71 patch.

## Bluetooth: BCM4350C5 on serial1

- Current N71 DTS contains `brcm,bcm4350-bt`; the kernel creates `hci0` and receives the chip ID and feature replies.
- Next blocker is **missing board-compatible `.hcd` firmware**. See [hardware state](HARDWARE_STATUS.md). Do not blindly copy a BCM4350C5 patch from a different OEM device.
- A [Broadcom firmware collection](https://github.com/winterheart/broadcom-bt-firmware) contains related patch files, but these have license restrictions and **are not known to be suitable for Apple's N71**.
- Reports from other 6s variants may be useful leads. Treat social demonstrations of N71m Bluetooth pairing as unverified for S8000 until code, firmware provenance and reproducible hardware tests are available.

## Wi-Fi: bus discovery first

- `CONFIG_WLAN` is disabled in the tested build; no wireless interface or PCI endpoint was enumerated on N71 at runtime.
- Determine **bus/host controller, chip and board resource map** before enabling a generic driver or guessing firmware names.
- The [Linux Broadcom driver documentation](https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html) lists BCM4350 PCIe support under `brcmfmac`. This is a driver research lead, **not proof** that the N71 WLAN endpoint is correctly exposed through PCIe or that generic firmware would work.
- Any Wi-Fi solution must account for permitted local calibration/NVRAM handling and demonstrate connection to a consented test AP.

## Primary upstream projects

- [HoolockLinux project](https://github.com/HoolockLinux)
- [HoolockLinux kernel](https://github.com/HoolockLinux/linux)
- [HoolockLinux documentation](https://github.com/HoolockLinux/docs)
- [Linux A9 Device Tree patch series](https://lore-kernel.gnuweeb.org/lkml/20240919161443.10340-12-towinchenmi%40gmail.com/T/)

All linked material remains owned/licensed by its original authors. This repository publishes only original code and verified observations.
