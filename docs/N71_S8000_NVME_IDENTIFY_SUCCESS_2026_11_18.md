# S8000 physical NVMe Identify Namespace success — 2026-11-18

## Verified result

On a real iPhone 6s N71 with Samsung S8000, RAM-booted ARM64 Linux
`7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`, the guarded, one-shot
Identify Namespace 1 command successfully completed through the Apple
ANS NVMe controller.

The pilot used an independently owned, physically contiguous 8 MiB HMB;
owned DART0 page tables and NVMMU descriptors; and bounded PCIe
configuration, power, reset and interrupt steps. Its non-leaf DART
descriptors used **PA|3**, derived from the original S5L8960x implementation.
The earlier PA|1 candidate had failed with a DART0 NO_PMD error
(`0x80000102`) at the SQ IOVA.

Physical completion and separately received data were both proven:

```text
IDENTIFY_NS1_COMPLETION present=1 status=0001 polls=2 csts=00000001
IDENTIFY_NAMESPACE_REAL nsid=1 nsze=15625000 ncap=15625000 nuse=15625000
  lba_bytes=4096 capacity_bytes=64000000000 data_tail_arrived=1
```

Here `status=0001` includes the NVMe completion phase bit; the pilot
separately validated the completion status-code bits, command ID, SQ ID,
and SQ head before accepting the result. The Identify payload arrived
on its own DMA data path. No personal namespace identifiers were logged.

**Proven:** hardware NVMe admin-queue DMA, valid namespace geometry,
capacity **64,000,000,000 bytes** (64 GB decimal), logical LBA size
**4096 bytes**, and **15,625,000** namespace blocks.

**Not proven:** Linux block device creation, a namespace driver,
partition discovery, safe data reads, a persistent Linux filesystem, a
writable volume, OS boot from NAND, or iOS storage coexistence.
No NAND block I/O or filesystem operations were attempted.

## Shutdown quarantine and retained state

After the successful Identify, the pilot's strict controller shutdown
gate refused to mark the transaction fully stopped:

```text
ADMIN_IDENTIFY_ONCE rc=-3 master_seen=1 controller_started=1 ready=1
  submitted=1 completed=1 data_arrived=1 stopped=0 master_off=1
  enable_polls=1197 shutdown_polls=957 disable_polls=2 last_csts=00000000
ADMIN_STAGE rc=-3 prepare_stage=5 dart_fault=00000500 nvmmu_fifo=00000301
```

Both PCI command words were verified back to 2 (**bus mastering off**);
`CC=0` and `CSTS=0` after disable. The strict requested shutdown-completion
proof was not satisfied. The remaining exact failure mode (timeout versus
fatal status during SHN) cannot be disambiguated from the original log
because the shutdown-phase CSTS and return code were overwritten by
the subsequent disable observations.

Because complete release was not qualified, the test **retained and
pinned its DMA-owned HMB, queue pages, DART root tables, NVMMU resources
and port0 power**, with the NAND reset GPIO held low. Do not unload
the pinned module, reclaim these pages or rearm the same transaction.

Independent, read-only DART0 fault snapshot while the quarantine remained
in place:

```text
SNAPSHOT error=00000500 stream=0 code=00 iova=00011000
  cmd=00000f02 packed_tcr=80808080 NVMMU_ctrl=00000001
  NVMMU_invalidate=00000000 SART_ctrl=00000001
  PERST_LOW=YES power_held=YES no_writes=YES
```

The earlier `NO_PMD` low error code `02` was absent, but do not
interpret that fact alone as proof of a fully clean teardown.

## Battery and connectivity guard

During this single hardware test, the existing bounded SN2400 input
profile was verified at **120 mA** with automatic rollback, live VBUS
around 5 V, battery approximately 82%, and safe temperature and voltage.
This is **partial USB power support, not net charging**: the battery
still discharged under load. Native Wi-Fi carrier, USB gadget and SSH
remained available.

## Next safe engineering gate

1. Preserve this immutable physical log and SHA-pinned candidate.
2. Instrument shutdown telemetry to retain the SHN wait return code and
   its final `CSTS` **before** disabling the controller.
3. Validate the instrumentation with offline tests; retain exactly the
   same strict quarantine logic and original single-Identify limit.
4. On a fresh, owner-attended boot only, re-qualify backup, charging,
   USB recovery and SHA-pinned module before any next bounded trial.
5. Qualify controller stop and DMA cleanup independently **before**
   considering namespace read-only block I/O. Never write NAND as
   part of this sequence.

The host-side **shutdown telemetry only** candidate was compiled for the same
running ARM64 kernel. It preserves the existing guarded one-shot transaction,
identical BME shutdown sequence and strict quarantine decision, while logging
SHN-phase `CSTS`, result code and disable-phase state independently.
Host-compiled candidate SHA-256: `4f85323317e94d0aee1dfa64fdd6f40bb876d99638f114a695ba1a6c7708dc23`.
**Not loaded or tested on hardware**; the current pilot remains quarantined.

This is a reproducible hardware milestone, not a persistent-storage
success claim.
