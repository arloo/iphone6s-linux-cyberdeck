# N71/S8000 touch calibration: experiment gates

**2026-11-10** — Current production baseline: iPhone 6s Samsung A9, HoolockLinux ARM64 `7.3.0-rc1-g6831bc701a6c`, USB gadget accessible. Full-resolution touchscreen remains **not working**. See the [read-only live baseline](N71_LIVE_BASELINE_2026-11-10.md): the kernel reports SPI2 power domain `off-0`, and no touch input node or SPI module is loaded. Analog rail and 32 kHz reference clock were **not** independently read back on this boot.

## Concrete evidence

- The physical controller previously answered documented HBPP status/bootloader probes over SPI2 at 1 MHz, 8-bit words, mode 3, CS setup/hold 5/10 microseconds.
- Private calibration is 1,024 bytes. The existing DATA packet is 1,038 bytes: 10-byte header, 1,024-byte payload, 4-byte checksum. The target is `0x10009000`; data ACK `0x4bc1` was not received. The bounded 50-poll attempt ended in `0x4879` (IDLE).
- On Nov 10, a **local-only, offline** parser checked the two Apple-sourced, preconstructed N71 firmware DATA packets (no payload printed/shared). Both are structurally valid and both have a preceding `NOP (0x18e1)` word. Their DATA frames are 65,458 and 18,598 bytes, respectively, before the 2-byte NOP prefix. The calibration DATA frame is generated independently by the driver without NOP.
- The difference creates a **framing hypothesis**, not proof that calibration needs a NOP. Different firmware commands may legitimately use different framing. No Apple firmware bytes, device calibration or private memory images are distributed.

## Prepared private modules — **none loaded on device**

| Candidate | Change relative to existing live module | Built offline |
| --- | --- | --- |
| `apple_z2_calnop.ko` | Optional single documented `NOP` prefix on calibration DATA; 1,040 instead of 1,038 wire bytes; default **off**, fixed N71 length/address guard | Exact kernel, LLVM 21 |
| `apple_z2_bpwdiag.ko` | Optional 16-bit SPI words for *only* calibration, with host-byte-pair adaptation; default remains 8-bit | Exact kernel, LLVM 21 |
| `tspis_trace.ko` | Bounded, sanitized metadata for a 1,038-byte calibration PIO transfer: elapsed microseconds, FIFO words/counts, return status, low-level status bits. **No data bytes** | Exact kernel, LLVM 21 |

These are local GPL-derived private diagnostics, not deployed Linux drivers or verified hardware fixes. The 16-bit transport hypothesis differs from the NOP framing hypothesis: **never combine changes in the same comparison**.

**Installed-display qualification:** The actual screen is a user-confirmed **aftermarket replacement**. Exact controller revision and firmware/calibration compatibility are unknown. Prior N71 HBPP responses still prove the installed assembly answered some documented commands, but the failed DATA acknowledgment cannot yet be attributed to a particular cause. Add the [aftermarket panel compatibility gate](N71_AFTERMARKET_DISPLAY_COMPATIBILITY.md) before staging a full firmware/calibration attempt; do not assume original Apple display provenance.

## Required sequence before any on-device experiment

1. Confirm host USB `05ac:4142`, isolated gadget network `172.16.42.1`, and root shell. Take a read-only snapshot of the running input devices, loaded modules, clock state, SPI bindings and original Chestnut analog register.
2. Verify runtime Device Tree GPIO and power-domain phandles against the live DT; yesterday's values **must not** be copied blindly. Preserve the known-good RAM boot bundle and avoid persistent iOS storage.
3. Check that the SPI2 power helper does not orphan an untracked power-domain reference. An older test helper attaches a synthetic device and deliberately holds the domain. Do not load it blindly as a reversible probe.
4. Confirm exact PMGR touch clock baseline (previously `0x800002ee`, disabled) and Chestnut analog rail (previously `0x0f`). If either differs, **stop** and investigate; never overwrite unknown state.
5. Stage the *already verified*, board-matched Z2 firmware and per-device calibration only on the iPhone's **volatile RAM filesystem**, never in GitHub. Preserve hash checks without logging private bytes.
6. First run only the original 8-bit transport with bounded **status-only** instrumentation, if a fully reviewed setup/teardown path is available. Any failure to read back expected power/clock/reset state blocks further tests.
7. Compare the optional NOP variant separately, only if the baseline trace supports a framing hypothesis. Restore and verify original state between variants.
8. Compare the 16-bit-only candidate separately if needed; do not make undocumented vendor commands or try unbounded firmware uploads. Stop on USB disconnect, unexpected IRQ, error, power mismatch or unrecognized ACK.
9. After every attempt verify analog rail restore (`0x1f -> 0x0f` **only if current value exactly matches**), reference clock restored to its captured original value, touch reset state, USB shell, and Bluetooth health. A module returning `-ECANCELED` does not itself establish a successful rollback: **readback is mandatory**.

**Go/no-go:** This experiment is currently **NO-GO for live SPI transfer**, pending a safe, end-to-end teardown review. The old dynamic SPI overlay persists within a Linux boot and may not be cleanly removed; the mere existence of a module is not a rollback plan. A blocked remote hardware command is not retried or bypassed.

## Acceptance thresholds

A valid data ACK is only the first gate. Functional touch requires controller firmware running, an evdev input endpoint that persists after probe, calibrated per-finger X/Y over 750×1334 (including corners and drags), correct release events, simultaneous two-finger tracking, and repeatable behavior after reboot. Upstream has publicly reported only coarse/quadrant touch; **do not label it working high-resolution multitouch**.

## Reproducible offline checks

`make test` runs synthetic HBPP framing tests without accessing firmware or a device. The test includes both the 1,038-byte existing DATA frame and the 1,040-byte NOP-prefixed *hypothesis*. The private Apple-firmware structural comparison is run only on the developer's local machine, without printing proprietary data.
