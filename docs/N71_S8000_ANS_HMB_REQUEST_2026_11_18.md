# N71/S8000: real ANS HMB request, 2026-11-18

The physical 106b:2002 controller requests **8,388,608 bytes (8 MiB)** of host memory. Two reads of ANS register 0x1808 agreed. HMB base and configured size were zero. This is a prerequisite for controller startup, not a namespace or persistent storage milestone.

The original N71 IONVMeFamily image independently references request register 0x1808 and HMB programming registers 0x1810 and 0x1818. The public protocol comparison is [OrchardLinux/orchard at 8ea3182](https://github.com/OrchardLinux/orchard/tree/8ea3182ac02f1c4da22dce8c082eb0df5f7083d3), notably its read-only apcie NVMe patch. That patch targets S8003/T8010; it is not evidence of S8000 board support. Our S8000 root controls and NVMMU allocation layout remain independently verified against the original Apple driver.

## Physical observation

The opt-in ans_hmb_ro observer ran inside all four owned empty DART0 guards and the owned NVMMU TCB/aux transaction. It read request/base-low/base-high/configured-size/request, with root and endpoint command words exactly 2, CC=0 and CSTS=0 throughout its guard checks. No vendor/NVMe register was written, bus mastering stayed off, and no admin command, namespace read or NAND host write occurred.

The original ADT names GPIO141 as function-boot_from_host. Its value was 0x00072202 before and after: output low, unchanged. The original ADT has no asserted ibec-boot marker. Port-local 0x22c is the NVMMU invalidation FIFO status; it is not this boot strap.

| Observation | Result |
| --- | --- |
| HMB requested | 8 MiB, nonzero, 4 KiB aligned, stable |
| HMB configured | 0; base absent |
| NVMe | 1.0.1; CC/CSTS both zero |
| BAR0 / PCI commands | Restored; BAR reservation released |
| NVMMU | Owned/restore invalidations each completed in one poll; both owned buffers still zero and freed |
| DART0 | All roots restored; backing pages zero and safely freed |
| Reset/power | PERST reasserted, port0 off, exact GPIO160 input restored |
| Wi-Fi | Native WLAN carrier remained up; authenticated postflight ping succeeded |
| Module | Normal unload succeeded; no quarantine or forced unload |

ARM64 pilot SHA-256: 456ee246b211cc7e0e36cfb2d476484362e15a2cec90a417e182d691be6ddbe4. Built for the running 16 KiB-page kernel; inert load/unload passed before the single armed physical observation. The 45 S3E host regressions passed; they cover transaction/failure handling and do not establish hardware DMA isolation.

## Power qualification

This boot used a bounded **120 mA input support** profile in the SN2400 research pilot. The source allows this profile explicitly; default remains 300 mA. Existing 3.3–4.2 V cell, temperature, VBUS, droop and lease-stop limits remain in place. The module restores its original input register on stop.

At the physical HMB observation the gauge showed 85%, about 33.2 C, and negative net battery current: external input provided partial support, not net charging. Eight preflight samples stayed within 3.6–4.2 V, 10–39 C, at least 35% capacity and no more than 500 mA net discharge. A fresh kernel monitor event confirmed the requested input lease before arming.

## Next hardware gate

An exclusively owned, physically contiguous 8 MiB HMB must be mapped through the verified S8000 NVMMU SART path. Submission/completion queues require independent DART mappings. Identify payloads use Apple FlatDMA TCBs, not an ordinary DART data mapping. Bus mastering and CC.EN remain disabled until those ownership and rollback paths are complete. No APFS modification, formatting or iOS partition change is included.
