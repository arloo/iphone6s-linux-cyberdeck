# iPhone 6s Linux Cyberdeck — A9 Bring-up Lab

**Community-driven, hardware-first Linux bring-up for the Apple iPhone 6s.** Active experimental target: **N71 / S8000 (Samsung A9)**. **N71m / S8003 (TSMC A9) experiments are deferred until compatible hardware becomes available**; all its hardware statuses remain NOT TESTED.

We are making a real iPhone 6s into a usable Linux cyberdeck. **Touchscreen, Wi-Fi and Bluetooth are the top priorities**. Native Linux now displays the CYBERDECK / A9 framebuffer UI and automatically initializes a real two-finger touchscreen on the physical iPhone 6s. Wi-Fi is still missing; Bluetooth has separate partial BLE evidence, and the current RAM-only boot is not a persistent OS installation.

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
| Hardware buttons | gpio-keys driver observed; evdev numbering may vary by boot and is not a current buttons acceptance test | Detected, not retested |
| Touchscreen | N71 firmware + calibration ACK, automatic Type-1 Z2 initialization and genuine single/two-finger EVDEV tracking; 138 dual-contact SYN frames in auto-init test; four GUI edge targets and physical optical LCD photographed | **LIVE PASS** (edge precision, latency, durability pending) |
| Wi-Fi | No wireless interface; `CONFIG_WLAN` disabled | **Priority 1 — missing** |
| Bluetooth | Broadcom `BCM4350C5` patchram **build 0825** loaded privately; 25 BLE advertising reports received in a 12-second passive on-device scan | **BLE radio verified; pairing pending** |
| Internal storage | No block devices enumerated | Not used; avoid NAND writes |
| Power / battery | No `/sys/class/power_supply` data | Not established |

This matrix reports **observations**, not promises. A detected controller or framebuffer does not imply the entire subsystem is functional.

## Immediate goals — contributions wanted

1. **Touch:** real N71 touchscreen and simultaneous two-finger input PASS; current focus is long-run stability, pixel edge accuracy and input-to-display latency, while preserving the validated RAM-only image.
2. **Wi-Fi:** identify the WLAN transport on S8000/N71, enable the necessary kernel stack and device tree description, and validate firmware / board-specific calibration without publishing private data.
3. **Bluetooth:** private board-compatible BCM4350C5 firmware initialization and BLE scanning are now **verified**. Next validate pairing, bonding, reconnection and power management. No Apple firmware is distributed here.
4. **Security gate:** replace plain Telnet with authenticated USB-bound SSH before connecting Linux to additional networks. A RAM-only source-based packaging process is available offline; boot remains separately hardware-qualified.

See [hardware findings](docs/HARDWARE_STATUS.md), [bring-up notes](docs/BRINGUP.md), [live touchscreen test and calibration blocker](docs/TOUCH_LIVE_TEST.md), [driver worklog](docs/DRIVER_WORKLOG.md), [research leads](docs/RESEARCH_LEADS.md), [roadmap](docs/ROADMAP.md) and [firmware policy](docs/FIRMWARE_POLICY.md).

**November 11 offline next-stage:** [N71 one-shot runtime read diagnostic](docs/N71_RUNTIME_READ_ONCE_DIAGNOSTIC_RFC_2026_11_11.md) and [RFC patch 0007](patches/0007-n71-runtime-read-once-irq-diagnostics-rfc.patch) compile on ARM64 and a private RAM image is ready. It is NOT live-tested, and physical touch input remains blocked.

**N71 experimental runtime initialization:** [RFC 0008](patches/0008-n71-opt-in-z2-runtime-wake-d9-rfc.patch) and [diagnostic plan](docs/N71_RUNTIME_WAKE_D9_OPTIN_RFC_2026_11_11.md) provide explicit root-initiated wake/D9 queries based on published Z2 protocol sources. NO automatic wake, no physical test yet; real touchscreen input remains blocked.

**Latest N71 experiment:** [RFC 0009](patches/0009-n71-d9-geometry-and-optional-af-enable-rfc.patch) adds a type-selected 16-byte D9 descriptor read and guarded manual AF report enable. [Technical gate](docs/N71_D9_DESCRIPTOR_FETCH_AF_OPTIN_RFC_2026_11_11.md). This is OFFLINE work, not yet a physical touch success.\n\n**Latest N71 real finding:** A Type-1 D9 descriptor was read successfully and showed reversed Y orientation with sensor aspect matching the 750x1334 panel within 0.1%. [RFC 0010](patches/0010-n71-inverted-y-metrics-type1-report-setup-rfc.patch) corrects the signed axis check and adds supervised 9D/BF setup before AF. [Technical note](docs/N71_INVERTED_Y_TYPE1_TOUCH_REPORT_RFC_2026_11_11.md). The new patch is not yet tested on real touch events.\n\n**2026-11-11 real hardware milestone:** The N71 iPhone 6s Z2 controller now emits [real Linux single-contact EVDEV touch events](docs/N71_TYPE1_FIRST_PHYSICAL_TOUCH_SUCCESS_2026_11_11.md), including tracking ID, XY movement, release and IRQ increments. Simultaneous two-finger tracking and full edge precision remain to be validated.\n\n**Two-finger hardware milestone (2026-11-11):** Native Linux on N71 now has [two simultaneous touchscreen contacts at SYN_REPORT](docs/N71_SIMULTANEOUS_TWO_FINGER_EVDEV_PASS_2026_11_11.md), with concurrent tracking in 273 frames, 6 starts and 6 releases, and no IRQ increment in a short no-touch follow-up. Remaining: physical edges, latency, sustained operation and boot automation.\n\n**Next N71 boot experiment:** [guarded Z2 touch autoinitialization](docs/N71_Z2_AUTOINIT_RAM_BOOT_2026_11_11.md) uses [a public startup script](scripts/n71_z2_autostart.sh) embedded into a **private** ramdisk. Mock tests validate one-shot flow and failure conditions, but hardware auto-boot verification is PENDING. The previous validated kernel #5 image remains unchanged.\n\n**Automatic N71 touch physical acceptance (2026-11-11):** [USB RAM Linux boot initialized the Apple Z2 controller with no manual sysfs action and produced actual single/two-finger Linux EVDEV touch input](docs/N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md) (138 two-contact frames out of 581 SYN frames; 4,096 bounded input events). Exact edge accuracy, latency and long-run stability are pending; Linux NAND install, display, Wi-Fi and Bluetooth are not implied.\n\n**Experimental native Linux GUI:** A [static ARM64 framebuffer / EVDEV cyberdeck prototype](examples/fb-cyberdeck/README.md) is running from the phone RAM with physical framebuffer writes verified, alongside the Z2 multitouch. [Hardware display notes](docs/N71_LIVE_FBDEV_CYBERDECK_POC_2026_11_11.md). Four on-device near-edge target center pixels transitioned from amber to cyan after real touch input (4/4 framebuffer hit-test PASS); optical LCD scanout is NOW CONFIRMED by an operator photograph showing CYBERDECK / A9 and EDGES: 4/4; only pixel-accurate calibration and long-duration stability remain pending.\n\n**Wi-Fi source review:** [S8000 Broadcom BCM4350 PCIe/DART blockers](docs/N71_BCM4350_PCIE_S8000_DRIVER_GAP_2026_11_11.md) identify the need for a port-1-only PCIe/DMA integration, without modifying storage or baseband ports. This is offline analysis, not a Wi-Fi success.\n\n**Wi-Fi next engineering gate:** [Compiled N71/S8000 PCIe port isolation validator](examples/n71-pcie-port1/README.md) and [19 adversarial DTB tests](tests/test_n71_pcie_fdt_gate.py) reject storage/modem/DART activation, with all controller nodes disabled. [Technical report](docs/N71_PCIE_PORT1_OFFLINE_FDT_GATE_2026_11_11.md). Nonbootable offline-only fixture; NO PCIe or Wi-Fi hardware access yet.

**Wi-Fi hardware-resource mapping:** [S8000 PCIe/DART read-only audit](docs/N71_S8000_PCIE_DART_ADT_WINDOW_AUDIT_2026_11_11.md) now confirms WLAN port-1 and three disjoint DART windows plus a legacy S5L8960X-family DART compatible. [Public allowlist audit tool](tools/n71_s8000_adt_window_gate.py) with 19 synthetic negative tests. This is NOT live PCIe, DMA or Wi-Fi support.\n\n**S8000 PCIe kernel-source step:** [RFC 0011](patches/0011-s8000-pcie-port1-research-guard-rfc.patch) adds a default-off, deliberately inert A9 PCIe driver guard and a compiled ARM64 source gate. [Technical note](docs/N71_S8000_PCIE_KERNEL_GUARD_RFC11_2026_11_11.md). No actual PCIe, DMA or Wi-Fi is enabled.\n\n**BCM4350 IOMMU parent resolved:** [full-tree ADT validation](docs/N71_BCM4350_DART1_PARENT_RESOLUTION_2026_11_11.md) confirms that the N71 Wi-Fi endpoint references the unique DART1 mapper child, with 178 nonduplicated phandles and DART1 4-KiB page metadata. Actual A9 PCIe register operations and DMA stream isolation remain unverified; Wi-Fi is not active.

**Original A9 PCIe source-layout research:** [iOS 15.8.8 kernelcache metadata audit](docs/N71_S8000_APPLE_PCIE_PRELINK_AUDIT_2026_11_11.md) has located AppleEmbeddedPCIE, AppleS800xPCIe and AppleS8000PCIe executable bounds in the locally owned original firmware, with checksum-verified ARM64 decoding. The [public metadata-only reader](tools/n71_kernelcache_pcie_kext_map.py) and synthetic tests publish no proprietary code. Native PCIe/Wi-Fi is still blocked pending verified controller registers and DMA isolation.

**Native Wi-Fi acceptance rejects USB:** [on-device wireless-only test](docs/N71_NATIVE_WIFI_ACCEPTANCE_GATE_2026_11_11.md) requires a real phy80211, exact SSID association and routing to router and Dell over the iPhone radio. BCM4350 remains BLOCKED by the S8000 PCIe/DART bring-up; cfg80211/brcmfmac have only been built for ARM64 offline.

**A9 PCIe call routing research:** [The original Apple S8000 GOT/stub analysis](docs/N71_S8000_PCIE_GOT_CALL_ROUTING_AUDIT_2026_11_11.md) classifies all 55 immediate S8000 module calls by destination (14 S800x shared, 1 embedded, 9 local, 31 other). [Public read-only analyzer](tools/n71_kernelcache_pcie_callgate.py) and synthetic tests export no Apple executable content. PCIe/DART initialization and Wi-Fi remain unverified.\n\n**S8000 original common PCIe offsets:** A [version-pinned six-register selector audit](docs/N71_S8000_PCIE_COMMON_REGISTER_OFFSETS_2026_11_11.md) now validates A9 shared offsets 0x24/0x2c and four port1-specific offsets 0x180/0x194/0x1a4/0x1ac. The [read-only auditor](tools/n71_s8000_common_reg_audit.py) and 14 synthetic tests do not ship Apple code or authorize hardware access. Physical MMIO base, functional bitfields, safe DART DMA and Wi-Fi remain UNVERIFIED.

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
