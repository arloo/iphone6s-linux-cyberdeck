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
No mode releases endpoint PERST, scans PCI, writes DART/TTBR, or enables DMA.
GPIO readbacks do not constitute an external analog voltage measurement.

Use [the single-syscall loader](../tools/n71-module-once.c) for qualified
experiments. BusyBox insmod retried a rejected finit_module via init_module
and repeated the initial GPIO lease; the new loader never makes that retry.
Its regression tests intercept the syscall and do not load a real module.

Next: qualify DART1 fault containment and physical requester routing, then
separately qualify PERST release, link training and manual PCI configuration
identity. TCR=0 alone proves neither requester routing nor DMA fault isolation.
No firmware, calibration, device identifiers or original Apple payloads are included.
