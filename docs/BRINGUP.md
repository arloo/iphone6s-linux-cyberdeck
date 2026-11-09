# RAM-only bring-up and recovery notes

This is a **record of verified results**, not a universal one-click installer.

## Tested hardware

- Apple iPhone 6s (Samsung-fabricated A9, N71/S8000).
- x86_64 Dell host booting a Linux environment with a direct Lightning connection.
- PongoOS 2.6.3 and HoolockLinux AArch64 test ramdisk.

## Confirmed boot stages

1. iPhone connected over USB; entering DFU produced USB device `05ac:1227`.
2. checkm8 reached PongoOS 2.6.3: phone displayed `pongoOS>`, host enumerated `05ac:4141`.
3. A bundled m1n1 + kernel / initramfs boot image of approximately 12.3 MB was uploaded to RAM.
4. The iPhone showed `Run /init as init process` and `HoolockLinux test ramdisk shell`.
5. USB gadget re-enumerated as `05ac:4142`; a full Linux host detected an Ethernet interface.
6. iPhone `usb0` at `172.16.42.1` responded to ping, followed by successful Telnet to port 23.
7. The shell returned the kernel version, CPU/memory status, hardware input nodes and framebuffer details.

The original stripped-down palen1x environment lacked USB mass-storage and USB Ethernet modules; an embedded-initramfs toolkit was used for boot, while Kubuntu provided the host-side USB Ethernet drivers after boot.

**Important:** The correct bootloader, image and Device Tree must match your specific device. The tested 6s is Samsung/S8000, not TSMC/S8003.

## Display

`/dev/fb0` accepts a 4,002,000-byte BGRX framebuffer (750 × 1334 × 4). A saved framebuffer image and demo UI were written in RAM; a mirrored interactive BusyBox shell was confirmed visually on the phone.

## Safety and recoverability

- Internal iPhone storage is **not** mounted or written by this project.
- Firmware and OS images are not redistributed here.
- Temporary RAM modifications disappear on device reboot.
- A failed exploit can require DFU/Recovery exit and reboot; do not select a destructive restore unless independently required.
- Avoid publishing serial numbers, addresses and complete unreviewed logs.
- Root Telnet is only acceptable for isolated USB lab testing and will be replaced.

## Upstream

- [HoolockLinux/docs](https://github.com/HoolockLinux/docs)
- [HoolockLinux/linux](https://github.com/HoolockLinux/linux)
- [HoolockLinux/m1n1](https://github.com/HoolockLinux/m1n1)

For exact bootloader build and image packaging requirements, consult upstream documentation rather than hardcoding unknown versions or proprietary binaries.
