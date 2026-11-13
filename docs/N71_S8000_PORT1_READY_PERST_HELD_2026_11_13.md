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


## Stage 12: selected-stream TLB invalidation physically accepted

At uptime 885 s, a fresh preflight again confirmed the board/kernel, monitored battery window, all seven PCIe domains OFF and exclusive GPIO/module ownership. The selected-stream sequence temporarily zeroed only SID0's four TTBR words, enabled TCR byte0 (packed value 0x80), and wrote exactly 0x102 to DART command offset 0x00: SID0 select bit8 plus invalidate bit1. The busy bit3 cleared on the second poll (`rc=0 command=00000102 polls=2`), within the 100-iteration, one-microsecond-delay bound. This follows the local S5L8960X driver command layout and its requirement to enable translation during invalidation. PERST remained physically LOW throughout the test.

The command selector intentionally changes from 0xF to 0x1. The old 0xF02 command is NOT rewritten: that would issue an all-stream invalidation. Outer comparisons allow only selector bits 11:8 to differ; the invalidate helper separately requires exact completion value 0x102. Other command bits, the fault register, the other three TCR bytes and all twelve protected TTBR words must remain unchanged. TCR returned to zero before the four saved roots were restored. If TCR does not disable, the sequence keeps those four roots invalid and reports failure instead of reinstalling valid roots with translation enabled.

Hardware output: `zero_pass=1 restore_pass=1 rc=0`, `COMPLETE rc=0 stage=12`, module and overlay removed, all seven PMGR domains OFF, Bluetooth UP/RUNNING with zero RX/TX errors, USB and touch present. Battery: Charging, 57%, +77 mA, 4.024 V, 30.6 C, remaining charge 723 mAh. Actual module artifact SHA256: `a07ca259c1f18b8cb62e0d584d9649f9ba73d1cbbf1b55c31863eb2a5707266c`.

The additional seven fake-MMIO cases execute the actual invalidation helper inside the outer TTBR sequence: successful busy-to-idle completion, rejected enable, busy timeout, wrong selected stream, changed fault, rejected disable and lost PERST. Alongside the earlier ten cases, all seventeen pass. On hardware, the host runner additionally requires the exact successful SID0 invalidation marker before accepting stage 12.

This qualifies a bounded SID0 invalidation command under endpoint reset. It does not establish physical BCM4350 requester routing or demonstrate a blocked DMA transaction. The next work is to qualify owned empty translation tables, physical requester routing and containment before releasing PERST and training the endpoint link. No native Wi-Fi enumeration is claimed.


## Stage 13: owned empty root tables, physical acceptance

A first attempt rejected the initial 4 KiB kernel-page guard with EPERM before allocating or writing DART state. The running batt2 kernel uses `CONFIG_ARM64_16K_PAGES=y`; DART's 4 KiB table granule is independent of the kernel allocation granule. The accepted implementation allocates four kernel pages (64 KiB total), using the first 4 KiB of each as an empty DART root. Before explicit zeroing it rejects any overlap, anywhere in each allocation, with any retained TTBR page from all four streams. It validates the original 36-bit TTBR encoding and unique page addresses. The Linux streaming DMA API maps/synchronizes each whole allocation; the DMA address must equal its physical address, rejecting a bounce buffer or IOVA. The synthetic device has no iommus property. No table address is logged.

Under PERST LOW, stage 13 replaces SID0's four roots with these owned roots, enables only packed TCR byte0, invalidates only SID0, disables TCR, clears the temporary roots and restores all sixteen sampled TTBR words through the outer transaction. Other streams' twelve TTBR words are never written. All four allocations are checked still zero, unmapped and freed only after successful restored-state checks and an idle command. Incomplete rollback instead retains the allocations, mapping device reference and module reference, preventing normal rmmod and a new test. No hardware failure injection was performed.

Accepted at uptime 1438 s: `DART1_OWNED_EMPTY_ROOTS rc=0 command=00000102 polls=2`; `OWNED_ROOTS_RELEASED after_restore=1 zero_unchanged=1`; `zero_pass=1 restore_pass=1 rc=0`; COMPLETE stage13 rc0. Module/overlay absent, all seven PCIe domains OFF, Bluetooth UP/RUNNING with zero RX/TX errors, USB and touch present. Battery: Charging, 58%, +50 mA, 4.043 V, 31.1 C, remaining charge 738 mAh. Module SHA256: `449597f8999b7a046f7241d06967621b97689b10b62c573615325a830b3f1d3a`.

The eleven new fake-MMIO cases execute actual owned-root encoding and the nested install/invalidate/clear/restore sequence. They cover physical-address bounds/alignment, success, rejected TCR enable/disable, busy timeout, wrong stream selection, fault changes, lost PERST, rejected root write/clear, duplicate roots and reserved bits. The prior seventeen cases also pass. This tests sequence behavior, not hardware DMA, allocator failure injection or cache coherency under device traffic.

The protected-port log now reports an independent comparison result: an unrelated earlier failure no longer prints a false protected-control mismatch. No PERST release, endpoint configuration access, DMA submission or native Wi-Fi enumeration happened. Next: bounded dwell with owned empty roots, followed by requester/link-training qualification.


## Stage 14: active empty-root dwell physically accepted

Stage 14 extends the owned-root sequence with 25 samples separated by 10 ms sleeps while packed TCR=0x80 and command=0x102, after the selected-stream invalidate completes and before disabling translation. Every sample checks PERST161 LOW, the four owned TTBR words, exact packed TCR and command, no DART fault flag, port1 ID5=1 and COMMON status bits0/4=1. No endpoint reset release or DMA is introduced. A failed dwell returns an error through the existing inner result and still executes the disabled-TCR/TTBR rollback path.

On the phone, active dwell ran from approximately uptime 1610.224 to 1610.501 s (at least 250 ms), with `DART1_OWNED_ROOTS_ACTIVE_STABLE samples=25 TCR=00000080 command=00000102 PERST_LOW`. Invalidation took two polls; all backing pages remained zero, were unmapped/freed after restoration, and both outer zero/restore checks passed. COMPLETE stage14 rc0, module/overlay absent, all seven PCIe domains OFF, protected port controls unchanged, Bluetooth UP/RUNNING with zero RX/TX errors, USB and touch present. Battery: Charging, 59%, +48 mA, 4.044 V, 31.2 C, remaining charge 743 mAh.

Actual stage14 module SHA256: `ae530aa48b3921df0561dc6af161b95930bf0bb80e5293ad7b1c6973aee02304`. The fake-MMIO suite now has thirty scenarios across three compiled-C tests, including accepted and rejected active-dwell callbacks. These synthetic callback cases check propagation and rollback; the native sampling loop was exercised on the physical phone.

The result establishes bounded register stability with owned empty roots under reset. It does not prove that a BCM4350 DMA request reaches SID0, that the hardware table walker interprets the empty entries as expected, or that a real fault is contained. Link training, physical requester qualification and enumeration remain outstanding; native Wi-Fi is not yet active. The current RAM boot stays available for the next supervised hardware stage.


## Stage 15: original-source local port mapping and control accepted

The actual port-instance initializer selects root resource `1+2*port` through root vslot1864, maps that resource, stores the map object at +200 and virtual base at +208. Port1 therefore uses resource3 (0x602000000/0x4000), confirmed against the original constructed vtables and live iOS resource list. An earlier report had incorrectly connected a different class's initializer to the port. The new original-source gate corrects that inference and also qualifies port control 0x80 bit0 and status 0x88 bit0 through the actual port accessors.

Stage15 maps only this port1 aperture, sets control0x80 from 0 to 1 under PERST LOW and active empty SID0 roots, samples status0x88 25 times, then restores control0x80 to 0 before DART teardown. At uptime2093 s: `rc=0 status88=00000004 samples=25 restored=1 PERST_LOW`. No endpoint reset release, PCI config access or DMA submission. Full TTBR/control/GPIO restoration, all seven PMGR domains OFF, module/overlay absent, USB/touch/HCI preserved with zero Bluetooth errors. Battery Charging, 60%, +63 mA, 4.052 V, 31.5 C. Module SHA256 `2ed20ca532571b97e3b6f4d3c71d19bad5cfcdbd08c5000d427c78a047c628dd`.

The actual C transaction passes eleven fake-I/O cases including control write/restore failure, changed DART guard, unexpected PERST, and modeled release/reassert paths. Those release paths have not yet run physically at this checkpoint. Status bit0 stayed clear under endpoint reset; no working link is inferred.
