# N71/S8000 first real Linux touchscreen contacts

Date: 2026-11-11. Physical test: confirmed on supervised iPhone 6s Samsung A9 S8000/N71, RAM-only kernel #5. Milestone: **first real Linux EVDEV single-finger contacts**. Simultaneous two-finger operation, all edges and prolonged stability are NOT yet accepted.

## Reproduced hardware path

The physical phone booted ARM64 HoolockLinux RAM kernel #5 from PongoOS and USB presented 05ac:4142. Firmware, controller calibration and both private firmware segments were acknowledged; /dev/input/event0 appeared. Manual runtime bring-up steps on the live N71:

1. One EE wake: SPI rc0, response EA (meaning uncertain).
2. Two E3/D9 metadata requests: the second reply E3, advertised descriptor length 16, checksum agreement.
3. One E7/D9 Type-1 descriptor fetch: rc0, E7 reply, checksum agreement; sensor spans approximately 5.8k by 10.4k and reversed Y axis; aspect within 0.1% of 750x1334.
4. One Type-1 9D/BF report-setup request series with E1 commits: SPI rc0 and last reply E1.
5. One AF report enable with E1 commit: SPI rc0, reply E1 and response checksum agreement.

**Physical touches then produced genuine Linux input_event packets** from the /dev/input/event0 kernel character device, not simulated values. A bounded capture of 64 successive 24-byte EVDEV records included ABS_MT_TRACKING_ID start and -1 release, ABS_MT_POSITION_X/Y changes between frames, BTN_TOUCH 1 and 0, and SYN_REPORT. The Apple GPIO142 IRQ counter climbed from 1 to 25 during the capture; a later health check showed 1058 accumulated IRQs with stable USB (3/3 pings). No additional kernel Z2/Oops warnings appeared after the original boot-time short-packet message. Later accumulated IRQ rates need characterization under true idle conditions.

## Scope and required next tests

| Hardware acceptance | Outcome |
|---|---|
| Private firmware and calibration ACK, live Linux USB | PASS |
| Surface D9 Type-1 SPI, reversed Y, geometry | PASS |
| Type-1 9D/BF/AF command sequence | PASS (SPI transport and reply) |
| Linux IRQ delivery under touches | PASS |
| EVDEV single-finger tracking, motion, release | PASS |
| Two fingers active simultaneously in different MT slots | NOT YET VERIFIED |
| Touch accuracy at all edges / persistent GUI input | NOT YET VERIFIED |
| Wi-Fi, Bluetooth, display and cyberdeck UI | OUTSIDE THIS TOUCH TEST |

Two sequential tracking IDs are not evidence of simultaneous multitouch. The next live acceptance is an attended dual-finger capture with slot/ID reconstruction, followed by edge and idle-interrupt tests.

## Public privacy

The public report omits personal/serial identifiers, exact device-unique sensor boundaries, private calibration, private firmware, device logs and raw input trace. The public RFC 0001-0010 source sequence is independent of private boot payloads.
