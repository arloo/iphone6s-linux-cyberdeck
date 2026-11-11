# iPhone 6s Linux Cyberdeck — A9 Bring-up Lab

**Community-driven, hardware-first Linux bring-up for the Apple iPhone 6s.** Active experimental target: **N71 / S8000 (Samsung A9)**. **N71m / S8003 (TSMC A9) experiments are deferred until compatible hardware becomes available**; all its hardware statuses remain NOT TESTED.

We are making a real iPhone 6s into a usable Linux cyberdeck. **Touchscreen, Wi-Fi and Bluetooth are the top priorities**. A custom framebuffer interface and an ARM64 diagnostic shell already run on the device, but a usable phone-side input and wireless stack are not yet available.

> [!WARNING]
> **Experimental hardware research, not a supported phone OS.** Booting custom kernels through checkm8/PongoOS can leave the device in DFU/Recovery or require manual recovery. This project's current tests are RAM-only and deliberately avoid writes to internal storage. Do not assume this eliminates all risks. Back up your device and proceed at your own risk.

## Verified hardware, November 11, 2026 — S8000/N71 only

| Component | Observed result | Status |
|---|---|---|
| Device | iPhone 6s, Apple A9 Samsung `apple,n71`, `apple,s8000` | Verified |
| Boot | `checkm8 -> PongoOS 2.6.3 -> m1n1 -> Linux` | Verified |
| Kernel | `7.3.0-rc1-g68aadac820d0-dirty` **build #5**, `aarch64` RAM boot | **LIVE PASS** |
| CPU | 2 logical CPUs, Apple A9 | Detected |
| Memory | 2,023,104 kB (`/proc/meminfo`) | Detected |
| LCD framebuffer | `/dev/fb0`, 750 × 1334, 32-bpp | Working |
| USB gadget networking | iPhone `172.16.42.1`, host `172.16.42.2`, USB `05ac:4142` | Working |
| Interactive shell | BusyBox shell via USB Telnet (port 23) | Working, insecure |
| Hardware buttons | `gpio-keys` exposed as `/dev/input/event0` | Detected |
| Touchscreen | **Live device-specific HBPP calibration ACK_DATA=0x4bc1 received on first poll** after one 1040-byte NOP-prefixed upload split into five 256-byte-bounded SPI transfers. Strict checksum-validated ID reads, watchdog rollback and USB continuity verified. A later RAM-only boot **ACKed both firmware blocks and started the controller**, registering /dev/input/event0; physical touch events remain absent and GPIO142 IRQ count is stagnant. | **Calibration + firmware start + EVDEV registration PASS; real touch events blocked** |
| Wi-Fi | No wireless interface; `CONFIG_WLAN` disabled | **Priority 1 — missing** |
| Bluetooth | Broadcom `BCM4350C5` patchram **build 0825** loaded privately; 25 BLE advertising reports received in a 12-second passive on-device scan | **BLE radio verified; pairing pending** |
| Internal storage | No block devices enumerated | Not used; avoid NAND writes |
| Power / battery | No `/sys/class/power_supply` data | Not established |

This matrix reports **observations**, not promises. A detected controller or framebuffer does not imply the entire subsystem is functional.

## Immediate goals — contributions wanted

1. **Touch:** strict HBPP reads **and real segmented calibration ACK_DATA=0x4bc1 now PASS on N71/S8000**. **Next:** investigate GPIO142 interrupt delivery/report handling with read-only, bounded tests, then prove an actual 750x1334 tap with tracking ID and simultaneous multitouch. The firmware now starts and /dev/input/event0 is registered, but no real touch events were captured.
2. **Wi-Fi:** identify the WLAN transport on S8000/N71, enable the necessary kernel stack and device tree description, and validate firmware / board-specific calibration without publishing private data.
3. **Bluetooth:** private board-compatible BCM4350C5 firmware initialization and BLE scanning are now **verified**. Next validate pairing, bonding, reconnection and power management. No Apple firmware is distributed here.
4. **Security gate:** replace plain Telnet with authenticated USB-bound SSH before connecting Linux to additional networks. A RAM-only source-based packaging process is available offline; boot remains separately hardware-qualified.

See [hardware findings](docs/HARDWARE_STATUS.md), [bring-up notes](docs/BRINGUP.md), [live touchscreen test and calibration blocker](docs/TOUCH_LIVE_TEST.md), [driver worklog](docs/DRIVER_WORKLOG.md), [research leads](docs/RESEARCH_LEADS.md), [roadmap](docs/ROADMAP.md) and [firmware policy](docs/FIRMWARE_POLICY.md).

**November 11 offline next-stage:** [N71 one-shot runtime read diagnostic](docs/N71_RUNTIME_READ_ONCE_DIAGNOSTIC_RFC_2026_11_11.md) and [RFC patch 0007](patches/0007-n71-runtime-read-once-irq-diagnostics-rfc.patch) compile on ARM64 and a private RAM image is ready. It is NOT live-tested, and physical touch input remains blocked.

**N71 experimental runtime initialization:** [RFC 0008](patches/0008-n71-opt-in-z2-runtime-wake-d9-rfc.patch) and [diagnostic plan](docs/N71_RUNTIME_WAKE_D9_OPTIN_RFC_2026_11_11.md) provide explicit root-initiated wake/D9 queries based on published Z2 protocol sources. NO automatic wake, no physical test yet; real touchscreen input remains blocked.

## Physical-device recovery and calibration breakthrough

The [November 10 USB disconnect incident](docs/N71_CAL_NOP_USB_DISCONNECT_2026_11_10.md) remains important safety evidence and is **not conclusively root-caused**. The device was successfully recovered with attended RAM-only boot on November 11, and guarded short HBPP probes independently re-verified the full touch power/reset/clock baseline. In a later *single* supervised experiment, 1040-byte NOP-prefixed device calibration **succeeded via five SPI transfers within one message**, receiving the real expected **ACK_DATA=0x4bc1** on the first poll. Read the [dated hardware report](docs/N71_CALIBRATION_ACK_DATA_LIVE_SUCCESS_2026_11_11.md). The private calibration blob, firmware, test binary and unique device identifiers are **not** published. Firmware startup and EVDEV registration subsequently passed on a RAM-only boot, but actual touchscreen contact delivery and production-driver compatibility remain unverified; see the [firmware-start / IRQ gate report](docs/N71_Z2_FIRMWARE_START_EVDEV_IRQ_GATE_2026_11_11.md).

## Reproducible engineering workflow

The repository now distinguishes **OFFLINE** protocol/logic tests, **BUILD** cross-compilation checks, and **HARDWARE** evidence requiring a real iPhone. See [CI and source pinning](docs/CI_REPRODUCIBILITY.md), the [machine-readable S8000/S8003 test matrix](manifests/test-matrix.json), [sanitized hardware results](results/), the [minimum EVDEV touch acceptance milestone](docs/TOUCH_EVDEV_ACCEPTANCE.md), and the [mandatory Telnet-to-SSH security gate](docs/REMOTE_SHELL_HARDENING.md).

```sh
# Public-source-only checks; do not require an iPhone or firmware:
make test
python3 scripts/validate_project.py
# Requires the AArch64 cross-compiler and independent BlueZ API headers:
make all BLUEZ_HEADERS=/path/to/isolated/bluez-include
```

The GitHub Actions workflow is versioned at [ci/verify.yml](ci/verify.yml), but **is not yet activated on GitHub**: the currently authorized GitHub connection lacks workflow-write permission. Local tests and builds are already operational. See [the activation gate](docs/CI_REPRODUCIBILITY.md).

**CI cannot mark a physical peripheral as working**. Only manually reviewed, foundry-specific evidence can change hardware status. S8003/N71m has **no qualified hardware results** yet. Do not confuse a buildable kernel driver or a detected SPI controller with a working touch panel.

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

For a dated, reproducible engineering check (six ARM64 RFC patches compiled and RAM payload reproduced bit-for-bit), read the [11 November 2026 offline/build validation](docs/N71_OFFLINE_BUILD_AND_RAM_REPRODUCIBILITY_2026_11_11.md). No new touchscreen activation is implied.

**November 11 recovery check:** [attended RAM-only Linux reboot and repeated strict hardware HBPP test](docs/N71_POST_USB_LOSS_RAM_RECOVERY_AND_HBPP_2026_11_11.md) passed, including watchdog restoration and 12/12 USB-link ICMP replies. **The later segmented calibration trial passed; EVDEV input remains blocked.**

## Community

We welcome testers, kernel engineers, Apple device-tree contributors, Broadcom wireless contributors, postmarketOS developers and reverse engineers.

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting logs or patches.
- Report observed hardware state precisely: N71 **S8000** (Samsung) versus N71m **S8003** (TSMC), kernel commit, firmware version/source, and reproducible steps.
- Never upload device serials, MACs, private NVRAM, calibration blobs, Apple firmware or account credentials.
- Use pull requests for source changes; open focused issues for missing drivers.
- Please link upstream work instead of claiming ownership of HoolockLinux, Asahi Linux, PongoOS or checkm8.

## License and credits

Original userspace toolkit material is MIT licensed; original experimental kernel-driver/diagnostic sources carry their own SPDX identifiers (including **GPL-2.0-only**) and must retain those terms. External kernel and bootloader projects retain **their own licenses**. Please see [LICENSE](LICENSE), individual source SPDX headers and [firmware policy](docs/FIRMWARE_POLICY.md).

Credits to HoolockLinux, Asahi Linux, Linux kernel contributors, checkra1n/PongoOS contributors and the broader open-source iPhone Linux community.
