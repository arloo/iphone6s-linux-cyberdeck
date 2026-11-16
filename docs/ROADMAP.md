# Hardware-first roadmap — reviewed 2026-11-16

Active target: **N71 / Samsung S8000**. N71m / S8003 remains deferred until compatible hardware is available.

## Achieved on physical N71

- RAM boot, framebuffer UI and USB recovery access.
- Automatic Z2 touchscreen initialization, genuine single-contact and simultaneous two-finger EVDEV input.
- Native BCM4350C5 Wi-Fi: PCIe, translated DART DMA, Linux MSI, brcmfmac, WPA2, DHCP, DNS, Internet and checked 1 MiB transfer.
- Managed Wi-Fi runtime with verified load/unbind/unload and complete power-domain cleanup.
- Bluetooth LE/classic discovery, controlled Dell pairing/bonding and 65,536-byte encrypted L2CAP transfer with Wi-Fi active.
- Battery telemetry and monitored charging with a finite guarded USB input lease.

## Next: make the verified session reproducible after boot

1. Assemble an owner-private RAM candidate containing the pinned Wi-Fi runtime, BlueZ/D-Bus, credentials and existing pairing state. Preserve the known-good recovery image and USB access.
2. Validate startup idempotence and service recovery in the current session, then inspect the offline image/component differences.
3. Qualify a supervised new RAM boot: touch, USB, charging, automatic Wi-Fi association/DHCP and restored Bluetooth controller/bond state. Startup source alone does not satisfy this gate.
4. Repeat the encrypted Dell transfer after service restart and after a new boot, with native Wi-Fi traffic in parallel.

The Dell is the currently available controlled Bluetooth peer. Keyboard/mouse HID tests are deferred until a real peripheral is available. A successful Dell L2CAP test must not be relabeled as a HID or audio result.

## Remaining qualification

- Authenticated USB-bound SSH and closure of unauthenticated Telnet before broader use: [hardening plan](REMOTE_SHELL_HARDENING.md).
- Touch edge accuracy, latency, stuck-contact checks and repeated-boot endurance.
- Longer concurrent Wi-Fi/Bluetooth traffic, 5 GHz association, reconnect/recovery and idle behavior.
- Power management: suspend/resume and sustained charging/full-charge behavior. The current charging lease expires after one hour.
- HID input, A2DP playback and LE application profiles when appropriate devices are available.
- GitHub Actions activation remains separate from local tests; the template is prepared, no remote CI success claimed.

See [current state](PROJECT_STATE_2026_11_16.md), [hardware matrix](HARDWARE_STATUS.md), [machine-readable results](../manifests/test-matrix.json) and the [historical roadmap](history/ROADMAP_BEFORE_2026_11_16_REFRESH.md).

## Product delivery beyond hardware bring-up

The target remains the handheld cyberdeck described in [product architecture](CYBERDECK_VISION_AND_ARCHITECTURE.md). Successful radios and touch are prerequisites, not the whole product.

| Workstream | Entry point | First acceptance result |
|---|---|---|
| Integrated boot | [#4](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/4) | Reproduce the verified session after a fresh RAM boot |
| Recovery security | [#7](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/7) | Key-only USB SSH and tested Telnet cutover |
| Touch console | [#6](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/6) | On-screen keyboard, terminal and job stop/results using touch only |
| Targeted Kali | [#5](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/5) | Signed ARM64 subset, controlled TCP assessment and bounded capture on the phone |
| Power/endurance | [#8](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/8) | Measured thermal/charging/idle policy and agreed endurance window |

The Kali environment retains the tested N71 kernel. Package installation, monitor mode, injection, USB host accessories and HID gadget capability have distinct prerequisites and must never be inferred from each other. See [Kali gates](KALI_ARM64_INTEGRATION.md) and [proposed package profiles](../manifests/kali-tool-profiles.json).

The original touch/Wi-Fi/Bluetooth issues [#1–#3](ISSUE_STATUS_2026_11_16.md) now track remaining qualification, with completed bring-up explicitly checked. Optional projects/notes/briefing integrations remain later companion/UI work after the local console is usable.
