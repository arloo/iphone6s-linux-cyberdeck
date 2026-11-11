# N71/S8000 hardware milestone — real calibration ACK_DATA after segmented SPI

**Date:** 2026-11-11. **Evidence:** supervised physical iPhone 6s N71/Samsung S8000 with aftermarket screen. **Outcome:** real HBPP calibration acknowledgment **0x4bc1** after one segmented upload. Firmware start and Linux EVDEV input are NOT yet functional.

## Prior incident and exact recovery state

A previous 2026-11-10 calibration-NOP attempt sent 1,040 bytes as **one** SPI transfer and was followed by Linux USB gadget disappearance without a module completion log. The cause remains **unknown**. Earlier 1,038-byte unprefixed DATA trials did not obtain ACK_DATA.

The device was subsequently recovered through supervised DFU, PongoOS and m1n1 to the previously verified RAM-only kernel **7.3.0-rc1-g68aadac820d0-dirty build #5**. Read-only clock, GPIO75 reset, PMU and Chestnut baselines were revalidated; real short SPI status and two strict checksum-valid READ_DATA messages again returned controller version **0x434d15c1**.

## Stage 1 — new firmware-free guarded segmentation trial

The original public status-only GPL probe was extended into an independent **n71_hbpp_segprobe** variant (public source in tools/touch/n71-hbpp-segprobe). At 1 MHz, SPI mode 3, 8-bit words it sent **1,040 bytes of NOP 0x18e1** while reset was *asserted* as one SPI message segmented into:

| Transfer | Bytes |
| --- | ---: |
| 0 | 256 |
| 1 | 256 |
| 2 | 256 |
| 3 | 256 |
| 4 | 16 |
| **Total** | **1,040** |

The SPI core reported **actual_length=1040**, the module emitted **PASS: SEGMENTED_1040_NOP_HELD_CS**, and Linux USB was not lost. The source keeps all chunks in one SPI message without requesting CS changes; a physically continuous CS waveform has not been logic-analyzer measured.

**Important negative observation:** immediately after this large NOP message during reset, the first HBPP status after releasing reset returned **0x0000 / 0x0000** instead of a known status. The test stopped with protocol error **-71**, then **WATCHDOG_AUDIT_PASS** and **FINAL_BOARD_BASELINE_PASS**. USB stayed operational, 10/10 ICMP replies.

A separate fresh copy of the known-good *short status-only* module was then executed: it again returned **REQ_CAL 0x1f01**, **IDLE 0x4879**, two strict **READ_DATA 0x4c39** replies, matching checksums, **version 0x434d15c1**, watchdog and final baseline PASS. Thus the all-zero response was transient, but its cause is not established.

## Stage 2 — private segmented per-device calibration trial: PASS

One private, version-matched, non-replayable GPL module was compiled for **exactly kernel #5**. The existing device-specific **1,024-byte calibration** remained in the Dell's private workspace and was never published.

The 1,040-byte controller-RAM packet was:

- Two-byte NOP prefix.
- Ten-byte HBPP DATA header, volatile target address **0x10009000**.
- 1,024 private, word-ordered calibration bytes.
- Four-byte HBPP checksum.

Its SPI transport used a *single* message with five transfers of **256+256+256+256+16** bytes, 1 MHz and mode 3. Before sending, two status checks and two strict checksum-validated controller reads established the expected live controller and powered state.

| Live gate | Observation |
| --- | --- |
| Strict controller identity | 0x434d15c1 |
| Status before upload | REQ_CAL 0x1f01 then IDLE 0x4879 |
| Frame transfer | **CAL_SEG_SPI_ALL_1040_BYTES_TRANSMITTED** |
| **First ACK poll** | **CAL_ACK poll=0 status=4bc1** |
| **ACK acceptance** | **PASS: EXACT_ACK_DATA_4BC1_RECEIVED poll=0** |
| Protocol outcome | **PASS: HBPP_READS_AND_SEGMENTED_CAL_ACK_DATA** |
| Independent watchdog | WATCHDOG_AUDIT_PASS |
| Reset, clock and analog restoration | FINAL_BOARD_BASELINE_PASS |
| Final module status | protocol_result=0 |
| Sensitive module calibration memory | Explicitly zeroized after experiment |
| Temporary phone-side binary | Deleted from volatile filesystem |
| USB-local transfer server | Stopped |
| After-test network | **40/40 ICMP replies**, zero loss |

**This is the first real, positive S8000 calibration ACK_DATA result for the tested controller and the tested guarded procedure.** The experiment used exactly one calibration upload: no automatic retransmissions, no firmware loading, no NAND operations and no baseband access.

## What this does not establish

- The originally observed USB disconnect has **not** been root-caused; segmentation is a successful mitigation in the tested sequence, not proof of sole causality.
- The production Z2 driver has **not** completed this exact hardware sequence. The private, guarded one-shot module is not a production input driver.
- The controller is returned to RESET, power and clock baseline at the end of the successful experiment. It is **not running with calibration retained**.
- There is **no Linux touchscreen EVDEV node**: only the physical-button device (gpio-keys, event0) was registered.
- There is **no S8003** physical evidence; its entire hardware matrix remains NOT TESTED.

## Next vertical release gate

Implement and qualify a *single bounded, supervised* S8000 initialization sequence that keeps the verified power/reset/clock and **segmented calibration upload**, then loads the authorized matching touch firmware privately and starts the controller. Verify a real Linux input device, in-bounds tracked coordinates across 750x1334, simultaneous two-finger contacts and stable release. This requires offline audits of firmware instruction lengths, segmented SPI state, cleanup paths and input IRQs before further hardware writes. The private firmware and calibration will never be pushed to Git.

Keep the Linux USB root Telnet service bench-only. Replace it with key-authenticated USB-local SSH before real-world deployment.
