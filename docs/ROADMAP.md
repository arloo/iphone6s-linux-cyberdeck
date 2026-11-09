# Hardware-first roadmap

The goal is **touchscreen + Wi-Fi + Bluetooth** on an iPhone 6s (N71/S8000). Graphics, UI, apps, wireless security tooling, battery optimization and standalone deployment follow hardware bring-up.

## Milestone T — touch input

- **T0** (verified): display framebuffer works; only `gpio-keys` appears in input.
- **T1**: identify N71 touch controller, bus/clock/reset/IRQ and required firmware.
- **T2**: enable `CONFIG_INPUT_TOUCHSCREEN` and investigate existing `CONFIG_TOUCHSCREEN_APPLE_Z2`; the driver exists in current upstream-derived kernel sources but is not enabled in the tested configuration.
- **T3**: provide correct N71-specific Device Tree bindings; demonstrate successful probe and firmware initialization.
- **T4**: demonstrate at least two simultaneous contact points with correct coordinates.
- **T5**: establish reliability across screen blank/unblank and repeated RAM-only boots.

## Milestone W — Wi-Fi

- **W0** (verified): no Wi-Fi interface, `CONFIG_WLAN` disabled; no PCI device enumerated at runtime.
- **W1**: identify WLAN module and its real bus/transport from reliable board evidence.
- **W2**: enable the required bus and wireless Kconfig options; add board-specific Device Tree resources.
- **W3**: load correctly licensed and hardware-matched firmware and *private* calibration from a local path.
- **W4**: network interface appears, scan enumerates APs.
- **W5**: associate to an owned test WLAN, obtain IP, demonstrate stable bidirectional traffic.
- **W6**: assess suspend/resume, thermal state and repeated boots.

## Milestone B — Bluetooth

- **B0** (verified): `hci0` registers and responds as BCM4350C5; driver requests a missing HCD patch.
- **B1**: identify correct N71 BCM4350C5 HCD patch source and module profile without redistributing firmware.
- **B2**: verify HCD load and HCI controller ready state; separate from “hci0 exists.”
- **B3**: discover nearby *consenting* test peripheral.
- **B4**: pairing, reconnect and stable data transfer.
- **B5**: test coexistence with Wi-Fi and radio power behavior.

## Later milestones

- **S**: replace root Telnet with secure authenticated USB access.
- **P**: battery/power sensing, charging limits and safe suspend.
- **U**: a native on-device UI/terminal with working touch and software keyboard.
- **R**: reproducible, signed build instructions and optional removable/volatile boot workflows.

## Baseline / versions

Observed iPhone 6s N71 Samsung `apple,s8000`, HoolockLinux Linux `7.3.0-rc1-g6831bc701a6c`, tested kernel source commit prefix `154668a0c30e`. User-specific serials and firmware blobs are deliberately excluded. Revalidate all findings for N71m/S8003.
