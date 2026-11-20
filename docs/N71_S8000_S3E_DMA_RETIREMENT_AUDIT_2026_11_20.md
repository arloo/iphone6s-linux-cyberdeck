# N71/S8000 S3E — DMA-retirement audit and timed Identify evidence

**Reviewed:** 2026-11-20. **Evidence:** real N71/S8000 hardware with RAM-only Linux; independent host-only safety-gate tests. This is a sanitized audit, not a storage driver release.

## Verified physical outcome

- A single NVMe admin **Identify Namespace 1** completed and returned separately arrived DMA data. Geometry: 15,625,000 logical blocks × 4,096 bytes = **64,000,000,000 bytes (64 GB decimal)**.
- Normal shutdown completed (`CSTS=0x00000009`), the controller was disabled (`CSTS=0`), and the PCIe root and endpoint command words were read back as `0x0002` (bus mastering disabled).
- The pilot returned `rc=-3`, `stopped=0`, **retained all admin queue, HMB, NVMMU and DART allocations**, and pinned the S3E module in quarantine. No block device, NAND block-data I/O, mount, or persistent installation was attempted.
- These facts do **not** independently establish DMA quiescence or permission to reclaim translations and buffers.

## Timestamped SQ burst (32/32 physical samples)

A bounded diagnostic recorded `ktime_get_ns`, DART status and S8000 Port0 local register `0x22c` in memory immediately after the SQ doorbell. Logging occurred after CQ polling; MMIO observation and a nominal 1 µs sample delay still perturb timing. The timestamps below are offsets from the start of the software burst, **not device-internal execution time**.

| Software observation | Offset | Port0 FIFO/status | DART status/fault |
| --- | ---: | ---: | ---: |
| First sample | 0.292 µs | `0x101` | `0x100` |
| Last sample before FIFO transition | 19.833 µs | `0x101` | `0x100` |
| First sampled FIFO transition | 22.208 µs | `0x201` | `0x100` |
| Last sample before DART transition | 24.542 µs | `0x201` | `0x100` |
| First sampled DART transition | 26.875 µs | `0x201` | `0x500` |
| Final sample | 75.333 µs | `0x201` | `0x500` |

The observed FIFO change is bounded by **19.833–22.208 µs**; the DART change by **24.542–26.875 µs**. The FIFO change was observed first. This is **not proof of causality**, nor a proof that either register denotes pending transactions. CQ status `0x0001` was available on the first subsequent poll. Other isolated boots ended with values `0x201`, `0x401`, or `0x701`: the meaning of bits `0x100`, `0x200`, `0x400` is **unverified**.

## DMA and resource lifetime audit

| Boundary | What is protected after an admin-DMA epoch | Audit result |
| --- | --- | --- |
| Admin unprepare | AQA/ASQ/ACQ restoration, queue mapping removal and NVMMU TCB clearing | Retirement guard refuses teardown |
| NVMMU cleanup | Owned admin pages, owned HMB and NVMMU table pages | `free_safe` forced false; pages quarantined |
| DART0 cleanup | Translation roots and associated pages | `free_safe` forced false; pages quarantined |
| PCIe / power cleanup | Contexts backing the quarantined translations | Retained on uncertainty |
| Post-stop classifier | `CC/CSTS`, HMB descriptor, queue ownership and reset consistency | **Diagnostic only**; DMA release is always refused |

The host test `test_dma_boundary_host.c` compiled with `gcc -std=c11 -Wall -Wextra -Werror -O2` and passed. A separate static audit found all three gate placements and verified that `n71_poststop_dma_release_allowed` returns false. **These are not hardware quiescence tests.**

### Design issue: intent is not lifecycle state

At the three retirement call sites, `admin_epoch_started` is currently set from module parameter `ans_identify_once`. The parameter has read-only `0400` permissions in the tested build, and the guard refused the actual physical teardown. Nevertheless, the parameter denotes **configuration intent**, not a monotonic record that DMA may have started.

A production-quality fix should latch a lifecycle-owned `admin_dma_epoch_started` state before any BME-enabling operation, and preserve it through failures, completion, shutdown, attempted cleanup and error returns. Neither a clean NVMe `CSTS`, BME-off, zero HMB descriptor nor a stable FIFO/DART observation may clear this latch. The present `independent_quiescence_proven` field is **not implemented as a release authority**. Do not enable a release path based on this report.

### Required next evidence

1. A host-tested state-machine model, with fault injection at allocation, BME enable, doorbell, CQ, shutdown, translation invalidate and teardown boundaries; active epochs must never free/unmap buffers without an independent, specified quiescence proof.
2. An authoritative definition or separately validated interpretation of the S8000-local FIFO register and DART status bits. Do not label `0x100/0x200/0x400` as transaction counts.
3. Explicit queue retirement and translation invalidation ordering, including stale-DMA prevention after the device reset, without relying solely on BME readback.
4. A separate, strictly read-only, recoverable storage path only after DMA ownership is qualified. Persistent NAND modification requires a verified restore-capable backup and additional acceptance gates.

## Power, recovery and publication boundaries

The SN2400 pilot configured a **300 mA USB input limit** with a bounded one-hour rollback lease. That setting is **not measured battery charge current**: real battery samples alternated between positive and negative, while USB VBUS remained around 4.9 V. Preflight checks reduce but do not eliminate hardware or data-loss risk. Never force-unload the quarantined storage module; subsequent experiments require a separate fresh supervised RAM boot.

Only sanitized aggregate data and gate outcomes are public. Private kernel logs, binaries, calibration/firmware, credentials, device identifiers, networking identifiers, DMA physical addresses and recovery artifacts remain outside Git.
