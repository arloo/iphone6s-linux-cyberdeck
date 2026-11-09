# iPhone 6s Linux Cyberdeck — A9 Bring-up Lab

**Community-driven, hardware-first Linux bring-up for the Apple iPhone 6s (Samsung A9 / S8000 / N71).**

We are making a real iPhone 6s into a usable Linux cyberdeck. **Touchscreen, Wi-Fi and Bluetooth are the top priorities**. A custom framebuffer interface and an ARM64 diagnostic shell already run on the device, but a usable phone-side input and wireless stack are not yet available.

> [!WARNING]
> **Experimental hardware research, not a supported phone OS.** Booting custom kernels through checkm8/PongoOS can leave the device in DFU/Recovery or require manual recovery. This project's current tests are RAM-only and deliberately avoid writes to internal storage. Do not assume this eliminates all risks. Back up your device and proceed at your own risk.

## Verified hardware, November 9, 2026

| Component | Observed result | Status |
|---|---|---|
| Device | iPhone 6s, Apple A9 Samsung `apple,n71`, `apple,s8000` | Verified |
| Boot | `checkm8 -> PongoOS 2.6.3 -> m1n1 -> Linux` | Verified |
| Kernel | `7.3.0-rc1-g6831bc701a6c`, `aarch64` | Booted |
| CPU | 2 logical CPUs, Apple A9 | Detected |
| Memory | 2,023,104 kB (`/proc/meminfo`) | Detected |
| LCD framebuffer | `/dev/fb0`, 750 × 1334, 32-bpp | Working |
| USB gadget networking | iPhone `172.16.42.1`, host `172.16.42.2`, USB `05ac:4142` | Working |
| Interactive shell | BusyBox shell via USB Telnet (port 23) | Working, insecure |
| Hardware buttons | `gpio-keys` exposed as `/dev/input/event0` | Detected |
| Touchscreen | No touch input device; `CONFIG_INPUT_TOUCHSCREEN` disabled | **Priority 1 — missing** |
| Wi-Fi | No wireless interface; `CONFIG_WLAN` disabled | **Priority 1 — missing** |
| Bluetooth | Broadcom `BCM4350C5` patchram **build 0825** loaded privately; 25 BLE advertising reports received in a 12-second passive on-device scan | **BLE radio verified; pairing pending** |
| Internal storage | No block devices enumerated | Not used; avoid NAND writes |
| Power / battery | No `/sys/class/power_supply` data | Not established |

This matrix reports **observations**, not promises. A detected controller or framebuffer does not imply the entire subsystem is functional.

## Immediate goals — contributions wanted

1. **Touch:** characterize the touchscreen controller and transport, required firmware and calibration, Device Tree nodes, interrupt and power sequencing, and deliver multitouch events through `/dev/input/eventX`.
2. **Wi-Fi:** identify the WLAN transport on S8000/N71, enable the necessary kernel stack and device tree description, and validate firmware / board-specific calibration without publishing private data.
3. **Bluetooth:** private board-compatible BCM4350C5 firmware initialization and BLE scanning are now **verified**. Next validate pairing, bonding, reconnection and power management. No Apple firmware is distributed here.
4. Replace plain Telnet with an authenticated local service; package an independently reproducible test image only after validating hardware.

See [hardware findings](docs/HARDWARE_STATUS.md), [bring-up notes](docs/BRINGUP.md), [live driver worklog](docs/DRIVER_WORKLOG.md), [driver research leads](docs/RESEARCH_LEADS.md), [roadmap](docs/ROADMAP.md) and [firmware policy](docs/FIRMWARE_POLICY.md).

## What is already here?

- `tools/cyberprobe.c`: original minimal ARM64 TCP connect, banner, HTTP HEAD and bounded PCAP capture utility (authorization required).
- `tools/hci-probe.c`: original AArch64 HCI ioctl probe; prints controller capabilities and counters without exposing the device address, with optional volatile up/down operations.
- `tools/ble-probe.c`: original passive BLE scanner, verified on the iPhone 6s radio, counting advertising reports without logging nearby device identifiers.
- `tools/deck`: original BusyBox-based diagnostics launcher with a mirrored console mode.
- `scripts/collect-hardware.sh`: focused, read-only diagnostic collector intended to run in the phone's Linux shell.
- Documentation and issue templates for the three blocking hardware drivers.

We intentionally **do not redistribute** Apple's iOS firmware, per-device calibration, proprietary boot payloads or firmware blobs, cloned kernel sources, device logs with identifiers, or the user's original local workspace. Upstream sources should be cloned independently from their own repositories.

## How it currently runs

The tested boot chain uses the existing [HoolockLinux project](https://github.com/HoolockLinux) and its [documentation](https://github.com/HoolockLinux/docs). Our host was Linux (Kubuntu); an experimental palen1x live image was used for the checkm8/PongoOS stage. A custom RAM-only initramfs transported the tools. Once Linux booted on the iPhone, a normal Linux host with USB CDC support accessed the ramdisk shell:

```sh
# Host-side only, over direct USB gadget networking:
ip -br addr
ping -c 3 172.16.42.1
telnet 172.16.42.1 23
# In the iPhone shell:
uname -a
deck info
deck net
```

**Do not expose an unauthenticated root Telnet service to an untrusted network.** This is a temporary USB-link development interface.

## Community

We welcome testers, kernel engineers, Apple device-tree contributors, Broadcom wireless contributors, postmarketOS developers and reverse engineers.

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting logs or patches.
- Report observed hardware state precisely: N71 **S8000** (Samsung) versus N71m **S8003** (TSMC), kernel commit, firmware version/source, and reproducible steps.
- Never upload device serials, MACs, private NVRAM, calibration blobs, Apple firmware or account credentials.
- Use pull requests for source changes; open focused issues for missing drivers.
- Please link upstream work instead of claiming ownership of HoolockLinux, Asahi Linux, PongoOS or checkm8.

## License and credits

Original material in this repository is MIT licensed. External kernel and bootloader projects retain **their own licenses**. Please see [LICENSE](LICENSE) and [firmware policy](docs/FIRMWARE_POLICY.md).

Credits to HoolockLinux, Asahi Linux, Linux kernel contributors, checkra1n/PongoOS contributors and the broader open-source iPhone Linux community.
