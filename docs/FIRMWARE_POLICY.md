# Firmware and privacy policy

This repository only contains original source code, reviewed public technical observations and build/diagnostic instructions.

We do **not** distribute:
- Apple IPSW contents, `BlueTool` images, iOS firmware, PongoOS/vendor binaries or proprietary firmware blobs;
- Bluetooth `.hcd` firmware unless distribution rights are conclusively established;
- Wi-Fi NVRAM, SysCfg, calibration records, unique board data or device identifiers;
- third-party kernel or bootloader sources copied without respecting their original licenses;
- device serial, IMEI, Bluetooth/Wi-Fi MAC addresses, private SSH keys or user-specific tokens.

For Bluetooth we verified a Broadcom `BCM4350C5` HCI response and a missing firmware request. **A random BCM4350C5 patch from another platform must not be treated as an Apple N71-compatible or legally redistributable firmware.** Confirm board variant, requirements and license before a private test.

For Wi-Fi, separate common redistributable firmware from private per-device NVRAM/calibration. A driver probe is not equivalent to usable, properly calibrated RF hardware.

For touch, verify that any necessary controller firmware and calibration are sourced lawfully. A working driver on another device model is not by itself proof of compatibility.

Sources include [HoolockLinux](https://github.com/HoolockLinux) and the [Broadcom firmware collection](https://github.com/winterheart/broadcom-bt-firmware), where redistribution may be restricted by vendor licenses.
