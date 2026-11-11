# Hardware-first roadmap — S8000 active, S8003 deferred

**Target for current experiments: N71 / Samsung A9 / S8000 only.** The N71m/TSMC A9/S8003 variant is expressly **out of active experimental scope** until a compatible physical device is available. Its test matrix remains entirely `not_tested`. Upstream source compatibility and references may remain in the build manifest; this is not authorization to run S8003-specific hardware tests or claim working peripherals.

**Recovery resolved and calibration milestone, 2026-11-11:** The N71/S8000 was physically recovered to known-good RAM-only Linux #5, with hardware baselines and strict HBPP register reads verified. The previous 1040-byte **single-transfer** calibration USB-loss incident has **no proven root cause**. The new **single-message segmented 256+256+256+256+16** private calibration upload obtained genuine **ACK_DATA=0x4bc1 on poll 0**, while the USB gadget remained healthy (40/40 ICMP). See [live calibrated ACK report](N71_CALIBRATION_ACK_DATA_LIVE_SUCCESS_2026_11_11.md). This is a controller-acknowledgment milestone, **not** touch firmware boot or working EVDEV input.

## Milestone T — first complete Linux touch contact

- **T0 — LIVE PASS:** S8000 framebuffer and SPI2 host, reference clock and Chestnut analog rail independently verified with exact rollback.
- **T1 — LIVE PASS:** Integrated touch power/reset/clock, strict HBPP READ_DATA/checksum validation and version 0x434d15c1 reproduced on the physical S8000.
- **T2a — LIVE PASS (2026-11-11):** Single supervised NOP-prefixed 1040-byte *private* calibration upload, five SPI transfers under one message, received **ACK_DATA=0x4bc1** on the first poll. Independent watchdog and rollback PASS. This is not proof that the production driver can repeat the full boot sequence.
- **T2b — NEXT / BLOCKED:** After accepted calibration, load the privately supplied matching Z2 firmware through bounded SPI transfers, program the controller startup sequence and register real Linux touchscreen input. Preserve independent recovery, bounded watchdog and private firmware segregation. **No EVDEV touchscreen has been observed.**
- **T3 — FIRST VERTICAL RELEASE GATE:** Independently capture one real 750×1334 touch contact with bounded X/Y coordinates, SYN_REPORT, and tracking ID release. No synthetic input counts.
- **T4:** Stable two-finger simultaneous contacts, tracked drag, edge/corner accuracy, and no stuck touches.
- **T5:** Stability across repeated RAM-only boots, idle and blank/unblank cycles.

See [touch acceptance criteria](TOUCH_EVDEV_ACCEPTANCE.md) and [sanitized live HBPP result](N71_HBPP_STATUS_ONLY_LIVE_SUCCESS.md).

## Milestone W — connected S8000 Wi-Fi

- Existing BCM4350 Wi-Fi device remains blocked by absent S8000-specific Apple PCIe host enumeration and a working Wi-Fi driver stack.
- Bring up **only PCIe port 1** for Wi-Fi; never experiment with the storage or baseband ports.
- Confirm the actual WLAN interface and bounded scan; then join an owned test network, obtain a valid IP address and sustain traffic. Firmware and calibration stay private.

## Milestone B — usable Bluetooth

- Passive BLE RF reception and vendor firmware loading were observed in earlier S8000 experiments (25 advertising reports in 12 seconds); they do **not** prove pairing on the current kernel.
- Bring up board-matched PMIC GPIO/UART and then demonstrate controlled discovery, pairing, reconnection and stable transfer with an authorized peripheral.

## Security gate — before use outside the lab

- Replace unauthenticated root Telnet with a USB-bound, key-authenticated SSH service. Demonstrate password refusal and TCP/23 closure before exposing or bridging new network interfaces. See [remote shell hardening](REMOTE_SHELL_HARDENING.md).

## Reproducibility and CI

- Keep pinned source manifests, local RAM-only image packaging, offline protocol regression, cross-compiled ARM64 modules, and **human-reviewed** hardware evidence separate.
- GitHub Actions [workflow template](../ci/verify.yml) is published but not activated remotely until GitHub grants workflow-write permission; do not label local tests as completed cloud CI runs.
- Current S8000 live kernel is RAM-booted `7.3.0-rc1-g68aadac820d0-dirty` build #5. No iOS NAND writes. The touch firmware and per-device calibration never enter Git.

**S8003 resumption trigger:** an actual compatible S8003/N71m device becomes available. At that point begin with read-only identification and separate supervised RAM-boot gates; never transfer S8000 test results to S8003.
