# N71/S8000: simultaneous two-finger Linux multitouch PASS

**Date:** 2026-11-11. **Physical device:** iPhone 6s Samsung A9, N71/S8000. **Kernel:** RFC #10 RAM-only build #5. **Outcome:** two simultaneous Linux EVDEV contacts observed on the real touchscreen. This does not establish perfect touch accuracy, GUI gesture handling or prolonged stability.

## Test conditions

The phone remained running Linux #5 after the successful first-contact test and its manual Type-1 Z2 initialization: one EE wake, two E3/D9, one E7/D9 Type-1, one 9D/BF setup and one AF enable. No additional controller setup, firmware upload, GPIO change or reboot occurred.

A bounded userspace capture read native 24-byte input_event records from /dev/input/event0. The operator released all contacts, pressed and moved two fingers simultaneously, and released them separately. The capture decoder followed ABS_MT_SLOT (47) and ABS_MT_TRACKING_ID (57) by slot and counted active tracking IDs at each SYN_REPORT boundary. This proves actual concurrency rather than sequential touch IDs.

## Measured outcome

| Signal | Observation |
|---|---:|
| EVDEV input events decoded | 2,973 |
| SYN_REPORT frames | 391 |
| Maximum simultaneous tracking IDs per frame | **2** |
| SYN_REPORT frames with at least two active touches | **273** |
| Tracking ID starts | 6 |
| Tracking ID releases | 6 |
| Two-finger concurrent tracking | **PASS** |

The observed pixel coordinates were in range for the 750 x 1334 screen but the test did not cover every edge or corner. After the user finished, USB Linux networking remained responsive (3/3 ping). The GPIO142 IRQ count was unchanged during a later four-second observation without deliberate contact. No new driver error, Oops or panic was found. This is a short-term health check, not a prolonged stability certificate.

## Scope and future acceptance

Native Linux now recognizes and tracks a single finger and two simultaneously active fingers with explicit release events. Work remains on edge/corner accuracy, swipe and gesture reliability, latency and frame cadence, long-lived stability, and reliable initialization on every cold boot. Wi-Fi, Bluetooth, display and the cyberdeck UI are separate project goals.

All raw trajectory logs, unique per-device sensor boundaries, calibration, firmware and identifying data remain private. Only aggregate, non-identifying acceptance results are published. Ten source RFC patches remain independently replayable and previously booted RAM images remain recovery options.
