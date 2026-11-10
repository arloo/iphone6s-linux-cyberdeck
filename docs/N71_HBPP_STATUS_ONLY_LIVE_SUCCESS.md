# N71/S8000 — checksum-validated HBPP controller identification on native Linux

**Hardware test:** 2026-11-10
**Target:** Samsung Apple A9 iPhone 6s N71/S8000, aftermarket replacement display previously confirmed fully functional under iOS.
**Kernel:** RAM-booted Linux 7.3.0-rc1-g68aadac820d0-dirty, build #5.
**Result:** LIVE PASS: two independently checksum-validated HBPP register reads. Full firmware startup, calibration and multitouch remain NOT PASSED.

## Experiment design

We built an original GPL-2.0-only single-use diagnostic, [n71_hbpp_once.c](../tools/touch/n71-hbpp-once/n71_hbpp_once.c), against the exact kernel ABI and verified all 50 unresolved module references against exported kernel symbols. The ELF module was delivered to the phone in volatile RAM over the private USB gadget, with identical SHA-256 on host and target.

Unlike previous probes, this module controls all the power resources together and performs strict read validation:

- Confirm the N71 device tree, disabled production Z2 child, empty SPI bus, PMGR clock baseline, asserted output reset GPIO 75, core PMU baseline and Chestnut baseline.
- Create an isolated temporary SPI device, distinct from the Linux Apple Z2 firmware driver. Configure SPI mode 3, requested 1 MHz, 8-bit transfers, 5 microseconds CS setup and 10 microseconds hold. No independent waveform timing measurement was made.
- Enable only Chestnut touch analog bit 4 (other LCD bits preserved), then enable the previously verified touch_ref output clock through the common clock framework.
- Clock a 16-byte ATN/NOP packet while reset is asserted, release reset, wait 15 ms, then perform two bounded HBPP status checks and one short ATN command.
- Read two register addresses using HBPP MEM_READ. Reject responses unless the status is exactly READ_DATA=0x4c39 and the returned checksum matches the sum of the four data bytes. Require a nonzero, non-0xffffffff controller version.
- No firmware, calibration blob, HBPP REG_WRITE/EXECUTE opcode, Apple NAND or baseband write.
- Arm a 1500 ms independent delayed-work watchdog before the first power write. The one-owner cleanup ensures that reset is reasserted, clock disabled and analog bit restored. Its post-check verifies an exact original baseline and transient kernel SPI/clock/GPIO/I2C resources are released.
- The module runs only once; the installed kernel does not support module unloading, so its inert code remains in RAM. It is not used for repeated automatic attempts.

## Live readback evidence

| Phase | Actual measured or logged value |
| --- | --- |
| Preflight clock | 0x800002ee |
| Preflight reset GPIO75 | 0x00072202 (asserted output) |
| Preflight core PMU319 | 0x01 |
| Preflight Chestnut 0x05 | 0x0f |
| SPI setup | Success at requested mode 3 / 1 MHz |
| Analog enable | 0x1f |
| Clock enable | PMGR 0x000802dc |
| Initial SPI clock-prime in reset | Success |
| Reset release | 15 ms startup delay |
| HBPP check 0 | 0x1f01 (REQ_CAL), 0x4879 (IDLE) |
| HBPP check 1 | 0x1f01 (REQ_CAL), 0x4879 (IDLE) |
| ATN reply | 0x4879 (IDLE) |
| MEM_READ 0x10008ffc | READ_DATA 0x4c39; checksum returned 0x0166, calculated 0x0166 |
| **Controller version register** | **0x434d15c1** (matches an older N71 test) |
| MEM_READ 0x10003800 | READ_DATA 0x4c39; checksum returned 0x0000, calculated 0x0000 |
| Auxiliary register value | 0x00000000 |
| Direct cleanup | Reset asserted, clock off, Chestnut returned to 0x0f |
| Independent watchdog | WATCHDOG_AUDIT_PASS |
| Final power/reset baseline | FINAL_BOARD_BASELINE_PASS |
| Reported one-shot protocol result | 0 (success) |

The actual terminal success was **PASS: HBPP_STATUS_AND_BOTH_STRICT_READS_VALID**.

Controller version 0x434d15c1 is only a **raw controller register value**, not proof of the aftermarket panel vendor or compatibility of its calibration with the private firmware extracted from the device.

## Independent cleanup and connectivity validation

A separate no-write kernel module again sampled power, PMGR, reset and GPIO configurations twice, spaced by 150 ms. It confirmed PMGR clock 0x800002ee, core PMU 0x01, Chestnut 0x0f and reset GPIO 75 0x00072202 in both snapshots.

After SPI transfers, the low data bit of the SPI-related GPIO register values for pins 41 and 43 was different from the older idle snapshot (their pin configurations were unchanged); this is not represented as byte-for-byte identity of all SPI pins. The reset, supplies, clock, and SPI2 domain all returned to their required states.

The host reached the phone over USB with **100/100** ICMP packets, 0% packet loss and mean round-trip 2.370 ms after the test. The phone still enumerated as USB 05ac:4142 and maintained the native Linux shell. No panic, Oops, bad clock rollback or recovery failure was found in filtered kernel logs.

## What this proves and what it does not

**Proven:** the current Linux SPI2 controller can communicate with the actual installed touch controller using a complete guarded board power/reset sequence; genuine READ_DATA status and 16-bit checksums were validated for two register replies.

**Not proven:** physical clock waveform frequency, calibration DATA acknowledgment ACK_DATA=0x4bc1, firmware compatibility with the installed replacement digitizer, touchscreen event reporting, or usable 750-by-1334 multitouch. This was intentionally a status-only test.

Earlier private calibration experiments transmitted a 1038-byte DATA frame, obtaining REQ_CAL=0x1f01 on the first poll or IDLE=0x4879 during the polling window, not ACK_DATA. The new bounded pending-REQ_CAL driver patch has not yet been validated on a complete real-device firmware calibration attempt.

**Next experiment:** use the same power/reset/clock/watchdog guard to test one privately held device-specific calibration-frame hypothesis at a time, never counting REQ_CAL/IDLE as success and never exposing proprietary firmware/calibration bytes in the public repository.

The published artifacts contain no personal email, private firmware, per-device calibration, serial number, private MAC address, credentials or raw provisioning information.
