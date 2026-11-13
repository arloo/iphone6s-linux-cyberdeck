# N71/S8000 port1 controller READY with endpoint PERST held low

Observed on the owner N71 Samsung A9 in RAM Linux, 13 November 2026.
Source: [bounded module](../experimental/port1/pcie-apple-s8000-port1-perst-held.c).
This is controller readiness; native BCM4350 PCIe enumeration and Wi-Fi remain unverified.

The original N71 Apple root vslot1768 initializes COMMON: lane-cfg=1,
root+0x4=0x11, wait for root+0x2c bit0, then root+0x38=1.
Without this step, ID3 power plus the original ID2 bit0 enable timed out
at ID5=0 after 250ms. With COMMON initialized, ID5 became 1 without timeout.

| Observation | Actual readback |
|---|---|
| COMMON status | 0x10 -> 0x11 |
| Port1 ID2 after enable and internal reset control | 0x01000001 |
| Port1 ID3 | 0x00000101 |
| Port1 ID4 | 0x00000001 |
| Port1 ID5 | 0x00000001 |
| AP PERST161, held OUTPUT LOW throughout | 0x00072202 |
| Controller READY dwell | 25 samples over at least 250ms, two completed cycles |
| DART1 packed TCR, single read at original offset 0xC | 0x00000000; four byte lanes 00 |
| Bluetooth HCI after the tests | UP/RUNNING, err_rx=0, err_tx=0 |

PMIC GPIO10 was exclusively owned through GPIOLIB, high during the lease,
then low and released. CLKREQ165's input data changed high -> low -> high;
its mux/configuration was not modified. PERST returned exactly to its original
input register 0x00072200 after WLAN shutdown and PMGR teardown.

COMMON lane/done controls and port1 ID4/ID2/ID3 were restored in reverse order.
COMMON READY bit0 remained latched across the observed PMGR OFF cycle, so
the next preflight accepts only the observed shared status values 0x10/0x11;
this is not a complete reset of every internal controller state.
The 12 sampled control/status registers of protected ports 0,2,3 stayed unchanged.
All seven PCIe PMGR domains returned OFF. Storage link0, baseband link2,
and link3 active_time remained zero. USB and Z2 touch remained present.
No module, overlay or GPIO10/PERST consumer remained after cleanup.

Stage0 is PERST only; 1 adds WLAN; 2 adds PMGR and snapshots; 3/4 are
negative ID3/ID2 controls; 5 initializes COMMON only; 6 reaches port1 READY;
7 holds ID2/ID4 and samples READY for 250ms; 8 additionally reads DART1 TCR
once. Default armed=false performs no GPIO request, MMIO or power operation.
Through stage 9 no mode writes DART/TTBR. Later register-write stages are documented below. No mode releases endpoint PERST or scans PCI.
GPIO readbacks do not constitute an external analog voltage measurement.

Use [the single-syscall loader](../tools/n71-module-once.c) for qualified
experiments. BusyBox insmod retried a rejected finit_module via init_module
and repeated the initial GPIO lease; the new loader never makes that retry.
Its regression tests intercept the syscall and do not load a real module.

Next: qualify DART1 fault containment and physical requester routing, then
separately qualify PERST release, link training and manual PCI configuration
identity. TCR=0 alone proves neither requester routing nor DMA fault isolation.
No firmware, calibration, device identifiers or original Apple payloads are included.

## Follow-up: strict DART1 state gate, incomplete postflight

The module now rejects any nonzero packed TCR, including unknown bits,
with EBUSY and rollback while endpoint PERST remains asserted.
The matching ARM64 build succeeded. On-device stage8 again reached READY
for 250ms, read TCR=0, passed the new gate, restored controls and GPIO,
logged COMPLETE rc=0 and returned RMMOD_RC=0.
The USB shell then stopped before the postflight marker; USB 05ac:4142
was absent and two pings failed. Cause is not established. This cycle is
INCOMPLETE, not a full acceptance pass. Current phone health and final
PMGR states require renewed live verification after USB recovery.
No PERST release or DART write was introduced.

## Next staged step: stage 9 DART1 selected-register snapshot

Stage 9 extends the existing PERST-held sequence by reading the 16 TTBR words (four tables per each of four streams, contiguous 32-bit registers starting at offset 0x40), command register 0x00 and fault register 0x10. It reports only TTBR nonzero/valid bitmasks, not physical table addresses. The existing packed-TCR zero-state check and low-PERST validation remain mandatory. No DART write, TLB command, TTBR programming, reset release or PCI scan is added.

The real ARM64 module compiled against the current `n71-batt1` kernel. Physical execution is PENDING: the owner-host USB address disappeared before the runner could bind its USB-only transfer server. A subsequent read-only host check showed no Apple USB device and no USB network address. Therefore this stage sent no module to the phone and performed no new phone register access. The last confirmed live check before that interruption showed battery Charging at 57%, about +103 mA, and Bluetooth UP/RUNNING with zero errors. Current phone state requires reconnection and revalidation.

This snapshot prepares the next decision about isolated DART configuration; it is not a claim of working DMA isolation or native Wi-Fi enumeration.


## batt2 physical acceptance: stages 9, 10 and 11

These follow-ups ran on the physically booted `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty` kernel with monitored charging and Bluetooth active.

* Stage 9: TCR=0, TTBR nonzero mask=ffff and valid mask=ffff, command=00000f02, fault=00000100. All sixteen retained TTBR words were valid despite disabled translation; an empty DART cannot be assumed. No raw table addresses were exported.
* Stage 10: only stream0's four TTBR words were temporarily zeroed, read back, held 25 ms and restored. Other twelve words, packed TCR, command and fault were compared unchanged. `zero_pass=1 restore_pass=1 rc=0`.
* Stage 11: with those four TTBR words still zero and PERST LOW, packed TCR was pulsed from 0 to 0x80 for 25 ms and restored to 0 before the saved TTBR words were restored. `DART1_TCR0_PULSE rc=0` and `zero_pass=1 restore_pass=1 rc=0`.

The stage-10 artifact SHA256 was `7ca25ed2887e7905fe15441eae5203660abe702671d125a8db7286d51f165f8f`; stage 11 was `516e1cbcce0c35814e80c72cf1384ce189353434ec393d7f6409fd7a998ae6f4`. These are private module artifacts, not distributed firmware.

Both write trials completed rollback with PERST restored to 00072200, WLAN low/released, synthetic node/module absent, all seven PCIe domains OFF, USB and touch present, and Bluetooth RX/TX error counters zero. Stage 11 ran at uptime 659 s; battery was Charging, 57%, +44 mA, 4.026 V and 30.3 C. The source defaults to unarmed and the host runner checks board, matching kernel, battery window, exclusive ownership and idle PCIe before loading it once.

`tests/test_n71_dart_disabled_ttbr.py` compiles the actual sequence header against fake MMIO and exercises ten cases, including active TCR, busy command, fault flag, failed zero/restore readbacks, protected-bank mutation, lost PERST and rejected TCR enable.

This establishes register control and observed rollback only. Stage 11 issues no TLB invalidation, submits no DMA and does not prove physical requester SID routing or fault containment. Stale translations have not been excluded. Keep the Broadcom endpoint reset until selected-stream invalidation and DMA containment are qualified; native Wi-Fi is still unproven.
