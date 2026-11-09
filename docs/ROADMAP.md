# Hardware-first roadmap

The goal is **touchscreen + Wi-Fi + Bluetooth** on an iPhone 6s (N71/S8000). Graphics, UI, apps, wireless security tooling, battery optimization and standalone deployment follow hardware bring-up.

## Milestone T — touch input

- **T0** (verified): display framebuffer works; only `gpio-keys` appears in input.
- **T1** (hardware characterized, pending runtime): Apple N71 multitouch on SPI2, reset GPIO75 and IRQ GPIO142; 84,092-byte vendor touch firmware and 1,024-byte unique calibration recovered *privately*.
- **T2** (offline build passed): A9 S5L SPI, Apple Z2 touch, reference clock and PMU regulator support compiled in a **separate test kernel**, applying upstream touch and touch-next patch series. The running, known-good kernel is unchanged.
- **T3**: provide correct N71-specific Device Tree bindings; demonstrate successful probe and firmware initialization.
- **T4**: demonstrate at least two simultaneous contact points with correct coordinates.
- **T5**: establish reliability across screen blank/unblank and repeated RAM-only boots.

## Milestone W — Wi-Fi

- **W0** (verified): no Wi-Fi interface, `CONFIG_WLAN` disabled; no PCI device enumerated at runtime.
- **W1** (research mapped): Broadcom BCM4350 Wi-Fi behind S8000 Apple PCIe port 1. **Our kernel does not enumerate this PCIe endpoint** and has no S8000-specific PCIe host DT binding; PCIe bring-up is the critical next step.
- **W2**: enable the required bus and wireless Kconfig options; add board-specific Device Tree resources.
- **W3**: load correctly licensed and hardware-matched firmware and *private* calibration from a local path.
- **W4**: network interface appears, scan enumerates APs.
- **W5**: associate to an owned test WLAN, obtain IP, demonstrate stable bidirectional traffic.
- **W6**: assess suspend/resume, thermal state and repeated boots.

## Milestone B — Bluetooth

- **B0** (verified): BCM4350C5 HCI UART registers and responds, initial kernel reports missing HCD patch.
- **B1** (verified): compatible USI/N71 Apple HCD patch extracted locally from an official restore image; **never distributed**.
- **B2** (verified): firmware loaded through a scoped HCI UART reprobe; controller reports **build 0825** and comes UP without HCI command errors.
- **B3** (radio verified, discovery UI pending): a passive on-device scan received **25 BLE advertising reports in 12 seconds**, with no device identifiers logged. Next verify controlled discovery with an owned/consenting peripheral.
- **B4**: pairing, reconnect and stable data transfer.
- **B5**: test coexistence with Wi-Fi and radio power behavior.

## Later milestones

- **S**: replace root Telnet with secure authenticated USB access.
- **P**: battery/power sensing, charging limits and safe suspend.
- **U**: a native on-device UI/terminal with working touch and software keyboard.
- **R**: reproducible, signed build instructions and optional removable/volatile boot workflows.

## Baseline / versions

Observed iPhone 6s N71 Samsung `apple,s8000`, HoolockLinux Linux `7.3.0-rc1-g6831bc701a6c`, tested kernel source commit prefix `154668a0c30e`. User-specific serials and firmware blobs are deliberately excluded. Revalidate all findings for N71m/S8003.
