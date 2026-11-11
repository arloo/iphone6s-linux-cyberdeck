# N71/S8000 — attended RAM-boot recovery and repeated live strict HBPP read

**Date:** 2026-11-11. **Evidence:** physical hardware, supervised on one N71 Samsung A9 iPhone 6s with aftermarket display. **Outcome:** Linux boot and strict controller reads confirmed; calibration and EVDEV input still blocked.

## RAM-only recovery after 2026-11-10 USB incident

The earlier 1,040-byte calibration-NOP DATA transfer was followed by an actual USB-gadget disconnect. Root cause is UNKNOWN, not proven to be NOP, packet length, or the S5L SPI driver.

With an attending operator, the target was placed in DFU (05ac:1227). One PongoOS loading attempt stalled with USB timeouts and protocol errors. The subsequent attended DFU/Pongo flow positively enumerated PongoOS (05ac:4141), then HoolockLinux gadget (05ac:4142) after the known-good m1n1 RAM-payload handoff.

The phone reported Linux **7.3.0-rc1-g68aadac820d0-dirty** build **#5**, compatible apple,n71 and apple,s8000. USB link 172.16.42.1 returned 4/4 ICMP replies. RAM payload **11,751,897 bytes** matched SHA-256 **0e4d6aca08d40f49233a3180fcd4ee0229ba042038759fa1e4342fccbc456687**.

No iOS NAND flash, recovery restore, firmware upload, calibration DATA transmission or private data export occurred.

## Strictly read-only hardware baseline

The version-matched GPL N71 baseline probe was transferred across the direct USB gadget link after a SHA-256 comparison. Its init deliberately returns -ECANCELED after unloading its temporary state; the BusyBox loader ran the **read-only** snapshots twice. Across four snapshots:

| Hardware | Readback |
| --- | --- |
| Touch clock PMGR | 0x800002ee |
| Adjacent clock word | 0x00000000 |
| Touch PMU register 0x219 | 0x00 |
| Touch PMU register 0x319 | 0x01 |
| Chestnut analog register 0x05 | 0x0f |
| GPIO75 reset | 0x00072202 |
| Snapshot stability | SNAPSHOTS_MATCH (twice) |
| Known baseline signature | KNOWN_BASELINE_SIGNATURE_MATCH (twice) |

Only the gpio-keys input device, event0, was registered. No Z2 input node existed.

## One bounded SPI2 strict HBPP test

The previously audited, version-matched GPL one-shot status probe was staged with the correct SHA-256. It instantiated an isolated SPI2 child and used **1 MHz, mode 3, transfers of 16 bytes or less**. It enabled Chestnut and touch reference clock briefly, deasserted reset to read the controller, and then restored the baseline under an independent 1500 ms watchdog. The production driver was not bound; the module did not send firmware or calibration.

| Check | Real observed response |
| --- | --- |
| First status | 0x1f01 REQ_CAL then 0x4879 IDLE |
| Second status | 0x1f01 REQ_CAL then 0x4879 IDLE |
| ATN status | 0x4879 |
| READ_DATA at 0x10008ffc | Opcode 0x4c39, matching checksum 0x0166 |
| Controller version | 0x434d15c1 (matches prior N71 read) |
| READ_DATA at 0x10003800 | Opcode 0x4c39, matching checksum 0x0000 |
| Protocol | PASS: HBPP_STATUS_AND_BOTH_STRICT_READS_VALID |
| Direct restoration | Analog 0x0f, reset asserted, clock restored |
| Watchdog | WATCHDOG_AUDIT_PASS |
| Final restoration | FINAL_BOARD_BASELINE_PASS |
| Module result | protocol_result=0 |
| Temporary SPI, clock, GPIO, I2C resources | Released |

After the experiment the Linux USB gadget remained on 05ac:4142; **12/12 host-to-phone ICMP packets** returned without loss. The temporary USB-local HTTP transfer server was stopped. The one-shot module remains resident but inert because this test kernel has no module-unload support.

**No ACK_DATA=0x4bc1 was observed; no calibration was attempted; there is no working touchscreen EVDEV input.** This is a safe repeat of a previously successful short controller probe, not a solution to the earlier USB crash.

## Next release gate

Remain at the known reset, analog and clock baseline. Investigate the prior failed large DATA transfer and proposed 256-byte SPI segmentation offline; defer further live calibration writes until a physical recovery/independent diagnostic path is available. A functional touch release requires accepted calibration, correct controller firmware, real tracked EVDEV coordinates for 750 x 1334, then two-finger gestures and idle stability.

S8003/N71m stays hardware NOT TESTED until a compatible device is available. Unauthenticated Telnet is strictly bench-only and requires replacement with key-authenticated USB-bound SSH before deployment.
