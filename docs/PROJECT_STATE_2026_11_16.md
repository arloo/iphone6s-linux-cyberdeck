# Engineering assessment — 2026-11-16

## Result and scope

The N71 / Samsung S8000 has reached the initial hardware connectivity milestone: genuine automatic touchscreen input, native phone Wi-Fi traffic and controlled Bluetooth pairing plus encrypted data transfer all work under the current RAM Linux session. The project is ready for boot/session integration and peripheral qualification; it is not yet a durable standalone operating system.

| Area | Evidence supporting the result | Practical limit |
|---|---|---|
| Touch | Real EVDEV single-contact and simultaneous two-finger tracking after automatic Z2 initialization | Latest presence check is not a new human-input test; edge precision, latency and endurance remain open |
| Native Wi-Fi | BCM4350C5 PCIe bound to brcmfmac; WPA_COMPLETED, DHCP, WLAN default route, DNS, Internet, SHA-256-checked 1 MiB transfer | Current managed RAM session, 2412 MHz; reboot restoration, 5 GHz and suspend/resume unqualified |
| Bluetooth | LE scan saw 12 devices; classic inquiry found Dell; Paired/Bonded; exact encrypted L2CAP echo | Controlled Dell peer, not a keyboard/mouse or audio-profile test |
| Repeat Bluetooth trial | Two initial same-session trials, then a third encrypted 65,536-byte echo after controlled service restart | Current RAM bond reload passed; no new kernel boot |
| Radio coexistence | Native Wi-Fi remained authenticated; Internet ping succeeded during Bluetooth transfer | Short trial, not an endurance or throughput benchmark |
| Charging | Most recent check: Charging, 40%, 34.2 °C, +47 mA battery current | Snapshot under load; 300 mA USB input setting is a finite guarded lease, not guaranteed net battery current |

Bluetooth level 2 requires encryption but does not prove MITM-authenticated pairing. Bonded state exists in the current private RAM filesystem; survival across boot is untested. The optional controller privacy-setting request was rejected, so address privacy is unqualified.

## What changed technically

Native Wi-Fi progressed from inert PCIe probing to a real managed brcmfmac device with translated SID0 DART DMA and the standard Linux MSI hierarchy (message 8 / AIC 264). The kernel runtime remains active instead of stopping at the end of a diagnostic lease. Controlled platform unbind followed by module unload has independently restored all seven PCIe power domains and removed the temporary objects while preserving USB, touch and Bluetooth presence.

Bluetooth uses the already working BCM4350C5 UART transport and genuine private patchram build 0825. A RAM-local BlueZ 5.85 / D-Bus 1.16.2 runtime supplies the management and pairing services. The controlled agent accepts only the intended phone/Dell peer during the test; Dell discoverability is temporary and restored afterward. The echo client requires encryption and validates every packet rather than counting a successful connection as data-transfer proof.

## Reproducibility state

Public source, bounded experiments, build inputs and sanitized results are committed. Original Apple firmware, touch calibration, WLAN tuning/NVRAM, network credentials, Bluetooth addresses, bond keys and raw captures remain private. No new NAND writes or persistent OS installation are claimed.

The Wi-Fi and Bluetooth results were saved in commits `001966d` and `570cb87`. This review updates the public entry points and machine-readable matrix, which still contained historical blockers despite newer evidence. Historical documents remain available and are labeled as snapshots. Physical evidence is separate from offline tests and cross-compilation checks.

The connectivity startup script has since been installed and qualified for idempotence and four-daemon recovery in the current RAM session. It is not integrated into the running boot image. A separately built integrated candidate is hash-verified but not transferred/booted. A private image manifest and service-restart/new-boot tests are required before claiming automatic restoration. Existing USB recovery remains available.

## Next acceptance gates

1. Assemble and hash-verify an owner-private RAM candidate with the proven runtimes and private configuration, while retaining the known-good recovery payload.
2. Exercise idempotent startup and controlled userspace recovery; then perform a supervised new boot and independently verify automatic touch/Wi-Fi/Bluetooth recovery.
3. Repeat controlled encrypted Dell transfer after the relevant recovery steps, with native Wi-Fi traffic in parallel.
4. Test genuine HID input when a keyboard or mouse is physically available. The owner currently has neither at hand; this gate is deferred, not failed.
5. Qualify authenticated remote access, longer coexistence, power management and optional Bluetooth audio separately.

N71m / S8003 remains completely untested. Local offline tests do not qualify hardware, and the prepared GitHub Actions template does not constitute an activated cloud CI run.

Evidence: [Wi-Fi result](N71_NATIVE_WIFI_PHYSICAL_PASS_2026_11_16.json), [Bluetooth result](N71_BLUETOOTH_PHYSICAL_PASS_2026_11_16.json), [Bluetooth runtime](N71_BLUETOOTH_RUNTIME_2026_11_16.md), [touch result](N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md), [machine matrix](../manifests/test-matrix.json).

## Product and issue review addendum

The hardware milestone advances the original cyberdeck objective rather than replacing it. The remaining product includes touch-operated terminal input, on-screen keyboard, bounded tool jobs/results and a curated Kali ARM64 environment. The optional companion/personal-dashboard direction remains separate future integration work.

The three original GitHub issues were reviewed with all existing comments and updated remotely to reflect physical successes and remaining acceptance. Five new workstreams now cover boot, Kali, UI, SSH and power. See [applied issue map](ISSUE_STATUS_2026_11_16.md), [detailed architecture](CYBERDECK_VISION_AND_ARCHITECTURE.md), [Kali integration](KALI_ARM64_INTEGRATION.md) and [reproducibility guide](OPERATIONS_AND_REPRODUCIBILITY.md). No new hardware pass is claimed by this documentation/issue review.

## Finalization/UI/power follow-up

[Detailed current-session follow-up](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md) records the running dashboard/local PTY/on-screen keyboard, actual native selftest, reviewed framebuffer, controlled service recovery, post-recovery radio tests, reversible display reduction and short resource measurements. No physical finger typing or new-boot pass is claimed. The integrated candidate preserves the original bootloader/DTBs/kernel and requires physical owner DFU/Pongo preparation. Kali, authenticated recovery access and endurance remain open.
