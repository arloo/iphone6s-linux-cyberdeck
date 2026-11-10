# Vertical milestone: usable 750 × 1334 touchscreen EVDEV input

**Priority: touch first, Wi-Fi and Bluetooth next.** A controller that responds to an SPI register read is not a functioning touchscreen. The immediate release milestone is **one complete real tap that produces valid coordinates and a release event in Linux**, followed by stable full multitouch.

## Evidence ladder

| Milestone | Acceptance criterion | N71/S8000 | N71m/S8003 |
| --- | --- | --- | --- |
| T0 — power, clock, reset and HBPP status | Reversible analog and clock changes; two checksum-valid READ_DATA replies with correct readback and watchdog cleanup | **LIVE PASS**, 2026-11-10 | **NOT TESTED** |
| T1 — calibration and firmware ready | Real controller returns exact `ACK_DATA=0x4bc1`, firmware reaches operational state, Z2 evdev node registered | **BLOCKED** | **NOT TESTED** |
| **T2 — first usable coordinate** | One physically performed tap: new tracking ID, in-range X/Y (0–749, 0–1333), SYN_REPORT, and clean tracking ID release | **BLOCKED — first target** | **NOT TESTED** |
| T3 — functional two-finger touch | At least two simultaneously tracked contacts across multiple frames; each released; no out-of-range samples; verified drag ≥ 100 px and all four edges | **BLOCKED** | **NOT TESTED** |
| T4 — sustained usability | Repeated taps, drag, no stuck contacts or resets; screen-to-touch coordinate alignment; stable interaction after power/idle cycles | **NOT TESTED** | **NOT TESTED** |

The raw register value `0x434d15c1` is an authenticated **controller-version register response**, not proof of a particular aftermarket panel vendor, firmware readiness, or touch input.

## Hardware capture protocol (once Z2 creates an event node)

1. First verify the touch device by inspecting `/proc/bus/input/devices`, sysfs device ancestry and `EV_ABS` capability bits. Do **not** mistake `gpio-keys` (the currently visible `event0`) for a touchscreen.
2. Capture only the intended Type B `/dev/input/eventX` stream for a short, supervised test. The local private binary recording is made with the **24-byte AArch64 little-endian Linux `input_event` ABI**, never added to Git.
3. Physically test center tap and release, then two simultaneous contacts and releases, a slow diagonal drag, and all four screen edges.
4. Analyze that private file with `python3 tools/touch/evdev_acceptance.py --input /private/path/events.bin --require basic`. A pass means at least one actual, in-range, fully released contact as reported by the capture. For full mode use `--require full` and require at least two released contacts, simultaneous frames, drag and all four edges.
5. Publish **only reviewed aggregate metrics** in `results/`; retain the raw evidence privately. A synthetic test recording must **never** be claimed as live hardware evidence.

```bash
# Host-side only, AFTER a genuine device capture has been transferred privately:
python3 tools/touch/evdev_acceptance.py --input /private/path/events.bin --require basic
python3 tools/touch/evdev_acceptance.py --input /private/path/events.bin --require full
```

The current tooling is an analysis harness, not an on-phone capture utility. The physical sampling operation and the identity of the actual evdev node must be verified separately. It does not cryptographically authenticate a recording's hardware origin. Manual review of the session metadata is required before advancing the matrix.

## Stop conditions

Abort and restore hardware on unexpected PMGR register values, analog or core rail mismatch, missing checksum, `REQ_CAL`/IDLE polling timeout, watchdog failure, unstable USB gadget or reset not returning to its original state. Never count a detected controller or a synthetic frame as an EVDEV success. Never upload device-specific calibration or Apple firmware to this public repository.

Wi-Fi must eventually establish a genuine IP interface and sustained packets, not just identify a BCM chip; Bluetooth must ultimately demonstrate pairing and reconnection, not only a passive advertising scan. Each needs independent S8000/S8003 results.
