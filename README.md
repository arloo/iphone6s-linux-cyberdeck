# iPhone 6s Linux Cyberdeck — A9 Bring-up Lab

**16 November 2026: touchscreen, native Wi-Fi and encrypted Bluetooth data transport have passed physical tests on iPhone 6s N71 / Samsung S8000.** This is a RAM-only Linux research system. Automatic restoration after reboot and peripheral-specific Bluetooth profiles are still being qualified.

## Current physical status

| Component | Observed result | Remaining qualification |
|---|---|---|
| Boot and display | checkm8 → PongoOS → m1n1 → Linux; 750 × 1334 framebuffer UI | Standalone persistent installation is outside the current RAM-only scope |
| Touch | Automatic Z2 initialization; real single-contact and simultaneous two-finger EVDEV input | Long-duration stability, edge accuracy and latency |
| Native Wi-Fi | BCM4350C5 PCIe on brcmfmac; WPA2, DHCP, default route, DNS, Internet and SHA-256-verified 1 MiB WLAN transfer | New-boot restoration, 5 GHz association, suspend/resume, endurance |
| Bluetooth | LE discovery (12 devices), classic Dell discovery, pairing and bonding; 65,536-byte encrypted L2CAP echo | HID keyboard/mouse, A2DP audio, suspend/resume and new-boot restoration |
| Charging | Guarded 300 mA USB input lease; charging observed with battery telemetry | Full-charge durability and autonomous long-term power management |
| Remote shell | USB recovery shell operational | Authenticated SSH replacement remains open; do not expose unauthenticated Telnet |
| S8003 / N71m | No compatible test device available | All hardware results remain NOT TESTED |

The Dell is the controlled Bluetooth peer. A keyboard or mouse is currently unavailable; HID testing is explicitly deferred until one is available. Bonded state has been observed in the current RAM filesystem, not proven persistent across a reboot.

See the [current engineering assessment](docs/PROJECT_STATE_2026_11_16.md), [hardware status](docs/HARDWARE_STATUS.md), [roadmap](docs/ROADMAP.md) and [machine-readable test matrix](manifests/test-matrix.json).

## Evidence and implementation

- [Native Wi-Fi physical result](docs/N71_NATIVE_WIFI_PHYSICAL_PASS_2026_11_16.json): actual phone radio traffic, not Dell USB Internet forwarding.
- [Bluetooth physical result](docs/N71_BLUETOOTH_PHYSICAL_PASS_2026_11_16.json) and [runtime notes](docs/N71_BLUETOOTH_RUNTIME_2026_11_16.md): controlled pairing and encrypted L2CAP transport with Wi-Fi active.
- [Automatic touchscreen multitouch evidence](docs/N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md) and [framebuffer UI](docs/N71_LIVE_FBDEV_CYBERDECK_POC_2026_11_11.md).
- [Native runtime builder](tools/build_n71_native_iommu_runtime.py), [managed runtime cleanup](scripts/n71_native_wlan_runtime_stop.sh), [Wi-Fi userspace](experimental/wifi-userspace/), [Bluetooth echo client](tools/n71-bt-l2cap-echo.c).
- [Driver worklog](docs/DRIVER_WORKLOG.md), [firmware policy](docs/FIRMWARE_POLICY.md), [source/CI reproducibility](docs/CI_REPRODUCIBILITY.md).

Native Wi-Fi uses translated SID0 DART mappings and the Linux MSI hierarchy (message 8 / AIC 264). Controlled unbind/unload was verified to restore all seven PCIe power domains while preserving USB, touch and Bluetooth. The active managed runtime remains running until explicitly stopped.

The optional [connectivity startup candidate](scripts/n71_connectivity_autostart.sh) is source preparation only: no automatic boot claim, no new physical boot, and no implicit integration into the known-good image. It requires a privately assembled, hash-pinned runtime and is not a standalone installation script.

## Build and verification

```sh
# Offline public-source checks; no phone or proprietary firmware required.
make test
python3 scripts/validate_project.py

# AArch64 tools; use isolated BlueZ headers to avoid host libc header mixing.
make all BLUEZ_HEADERS=/path/to/isolated/bluez-include
make build/n71-bt-l2cap-echo-aarch64 BLUEZ_HEADERS=/path/to/isolated/bluez-include
```

The latest completed verification before this documentation refresh passed 1,581 offline tests, the HBPP audit and the project manifest/evidence check. Local checks are distinct from hardware evidence. The [GitHub Actions template](ci/verify.yml) remains prepared but is not activated remotely; no completed cloud CI run is claimed.

## Scope and privacy

Active hardware target: **N71 / S8000 (Samsung A9)** only. No S8003 result may be inferred from it. Current kernel: `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`.

Experiments are RAM-only and avoid internal NAND writes. Original Apple firmware, device calibration, NVRAM, controller addresses, network credentials, pairing keys and raw device logs stay private. Public evidence contains aggregate results and source/build provenance. The privacy hook checks Git identity/history before pushes.

See [contribution guidance](CONTRIBUTING.md), [remote-shell hardening](docs/REMOTE_SHELL_HARDENING.md) and the [historical README snapshot](docs/history/README_BEFORE_2026_11_16_REFRESH.md). Historical dated reports are retained as evidence of earlier stages; their old blockers do not override the current status matrix.

## License and credits

Original userspace toolkit material is MIT licensed. Experimental kernel sources retain their own SPDX terms, including GPL-2.0-only; external projects retain their respective licenses. See [LICENSE](LICENSE) and source headers.

Credits to HoolockLinux, Asahi Linux, Linux kernel contributors, checkra1n/PongoOS contributors and the open-source iPhone Linux community. The project builds on their work; it does not claim ownership of those upstream projects.
