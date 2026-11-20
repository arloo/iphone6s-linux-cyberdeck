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
| Optional queue-register pilot | Active admin queue AQA/ASQ/ACQ zeroing after a protocol-consistent reset | Additional DMA-epoch guard refuses queue writes; protocol predicate remains diagnostic |
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

## Same-day offline hardening candidate (not phone-tested)

A separate **private, host-only / cross-compiled kernel candidate** now adds a monotonic `n71_admin_dma_epoch_latched` flag. It is set **before the first root or endpoint BME-enabling PCI command write** and is never cleared during the module lifetime. All three retirement gates conservatively check `ans_identify_once || READ_ONCE(n71_admin_dma_epoch_latched)`; the original read-only opt-in remains a redundant denial guard.

The candidate compiled for the exact AArch64 test kernel, the existing retirement-boundary host test passed, and static comparison confirmed exactly three changed gate expressions, one latch set, no latch reset, and no unrelated removed source statements. **This patch was not booted, installed, or physically tested on the phone.** It does not create a new release path or establish hardware DMA quiescence. Further fault-injection and independent retirement proof remain required.

## Public-source fail-closed alignment (same day; offline only)

The public `experimental/port0` driver previously lagged behind the private physical-test candidate and lacked the three administrative DMA-retirement guards. This change brings the **guard itself** and its monotonic BME-before-write latch into public source, without importing private trace logs, firmware, device identifiers, binaries, or hardware-specific private diagnostic extensions.

- A kernel-agnostic retirement-boundary header denies release for every active admin epoch, even if shutdown is consistent or a putative independent-proof flag is supplied. No positive DMA quiescence proof is implemented.
- The public admin callback latches `n71_admin_dma_epoch_latched` before the root and endpoint BME-capable writes. Both the read-only opt-in and this latch independently force the three cleanup paths to refuse release.
- An offline host-C fault-injection harness checks **112 simulated fault/qualification/shutdown/proof combinations**, including faults between BME writes and every subsequent stage, across admin-unprepare, NVMMU, DART and queue-register boundaries.
- Five automated tests additionally check latch ordering, latch immutability, all four gate locations and non-authority of hardware shutdown status. The public AArch64 kernel module source compiled against the qualified N71 test kernel in an isolated build directory.

**Scope:** the fault-injection harness models software transitions; it cannot inject failures into real S8000 hardware and is not a proof of safe DMA teardown. The publicly aligned driver **has not been executed on the phone**. The currently quarantined physical module must never be replaced or removed in that running boot.

## Separate protocol-accounting evidence (2026-11-20; offline only)

The latest public source tracks distinct software milestones for the one allowed admin Identify: SQ doorbell issued, CQ phase observed, completion status/command identity validated, CQ head doorbell issued, data-tail arrival, Identify namespace geometry validated, shutdown completion, controller disable, BME-off, queue/DART ownership still retained, and latched DMA epoch. It publishes an additional **read-only diagnostic** (`ADMIN_PROTOCOL_ACCOUNTING_RO`) only after the existing one-shot admin shutdown path.

- A valid CQ phase bit alone is classified **incomplete**, not validated completion. A CQ-head doorbell is explicitly a software write, not an independent device acknowledgement.
- Only a fully consistent 12-indicator snapshot is classified `ACCOUNTED_DMA_UNPROVEN`. This still does **not** establish DMA quiescence: unobserved vendor-initiated DMA, posted PCIe transactions, NVMMU/SART accesses and stale translations remain out of scope.
- An exhaustive C host test classified **4,096 synthetic boolean combinations**, including all-positive and single/multiple-missing prerequisites; `dma_release_allowed` returned **false for every case**. Four Python unittest contracts additionally verify source ordering, completion identity and no hardware writes in the classifier.
- The integrated observer compiled for the exact N71 ARM64 test kernel. The resulting binary was retained privately and **was not loaded on the phone**. This is a new candidate, not a physical acceptance result.

The upstream Linux `nvme/host/apple.c` driver separately freezes, quiesces and drains request queues around disable, illustrating why a controller shutdown register alone does not account for software-owned requests. That upstream implementation targets **different Apple ANS generations** and cannot be copied to S8000 without an independently demonstrated hardware mapping. [Linux source](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/apple.c); [NVMe CC field and reset semantics](https://learn.microsoft.com/en-us/windows/win32/api/nvme/ns-nvme-nvme_controller_configuration).

**Next unblocker:** identify a hardware-supported fence or authoritative reset/transaction-drain contract for this S8000 DART/NVMMU/PCIe combination. No existing CQ, SHST, CC, BME, PERST or local FIFO sample is yet qualified as that proof. Keep all page mappings pinned until then; no persistent NAND work is authorized.

## Post-stop late-RAM-change witness — offline candidate only (2026-11-20)

A separately opt-in **falsification** diagnostic (`ans_late_dma_probe_ro=1`) was added to the public pilot. It refuses simultaneous SQ timestamp tracing or queue-register retirement trials and requires a single validated admin Identify, real DMA-epoch latch, owned CQ/data mappings, successful NVMe shutdown and disable, BME-off, and retained DART queues. It performs no additional NVMe command, PCIe command, GPIO/reset change, DART/NVMMU invalidation, DMA unmap, or page release.

After the normal controller shutdown, it uses the existing noncoherent streaming-DMA CPU/device synchronization pattern to compute **12 local fingerprints** of the first 4 KiB each of the owned CQ and Identify data pages, spaced by nominal **50 ms**. Logs include only sample/change counters and a clear `release_allowed=NO` warning; no fingerprints, raw data, physical addresses or personal identifiers are printed. A host C harness checked unchanged buffers, changes to non-leading bytes, separate CQ/data alerts, and sticky change detection; additional static tests check the opt-in/exclusivity/guard ordering and forbid new MMIO or teardown operations. The integrated N71 ARM64 kernel module compiled successfully but **has not been installed or run on the phone**.

**Interpretation:** an observed change after shutdown is a useful reason to investigate possible late device writes, but does not independently attribute the change to DMA (cache/coherency or software effects remain possible). **No observed change is not proof of quiescence**: unchanged data cannot exclude unseen requests, posted PCIe writes, future controller activity, stale translations, or accesses to other pages. The observer never grants a teardown authority.

Relevant independent implementation references: [Corellium DART TLB busy/flush polling](https://github.com/corellium/linux-m1/blob/master/drivers/iommu/apple-dart-iommu.c) and [Linux Apple NVMe quiesce/shutdown/late-CQ handling](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/apple.c). These sources inform our safety distinctions; their hardware generations and register maps **are not assumed interchangeable with N71/S8000**.

**Next physical step:** if a new owner-supervised RAM boot is arranged, perform a new power/USB/battery/S3E-clean preflight before **one** explicitly armed Identify + late-content-observer run. Never load the candidate into the currently quarantined boot; never force `rmmod` or reclaim DMA pages.

## Fresh RAM boot checkpoint — 2026-11-20

The owner-assisted DFU -> PongoOS -> Linux RAM handoff succeeded. The expected N71 AArch64 test kernel was observed from an authenticated USB SSH session after new-boot host-key rotation. Preflight found S3E **not loaded**, USB gadget configured, the SN2400 300 mA **input limit** active under its time-bounded lease, battery approximately **54%** and temperature about **33.9 °C**. Instantaneous battery current still oscillated; USB input limit must never be described as net charging current.

The new post-stop RAM-change candidate remains **host-built only**. Remote transfer was denied by the authorized remote-access safety controls; the module was confirmed absent from the device's RAM transfer destination, and S3E remained clean. No new S3E run or RAM witness sample was collected on this boot. Do not represent the offline build or a successful Linux boot as a hardware DMA quiescence result. The existing restore and DMA-quarantine requirements remain unchanged.

## Archived real-hardware post-stop comparison (2026-11-20)

Eight selected archived N71/S8000 diagnostic files were **reanalyzed offline** using `tools/storage/analyze_n71_s3e_poststop.py`. The analyzer processes private dmesg input locally but prints **only aggregate status counts**, never filenames, identifying metadata, kernel addresses, raw messages or timestamps. Its deduplication uses boot-relative event signatures and **cannot establish independent hardware boots**. In this particular selection it found eight snapshots and eight distinct event signatures; the number of independently demonstrated boots is **unknown**.

| Raw post-stop register snapshot | Value | Count among the 8 selected signatures |
| --- | --- | ---: |
| DART status/fault | `0x00000500` | 8 |
| NVMMU Port0 FIFO/status | `0x00000201` | 4 |
| NVMMU Port0 FIFO/status | `0x00000301` | 1 |
| NVMMU Port0 FIFO/status | `0x00000401` | 1 |
| NVMMU Port0 FIFO/status | `0x00000601` | 1 |
| NVMMU Port0 FIFO/status | `0x00000701` | 1 |

All eight explicitly logged `shutdown_rc=0`, `disable_rc=0`, `inner_rc=0`, BME-off, HMB descriptor zero, original admin queue values still installed, DART queue translations retained, `rc=-3` and no DMA release. **This is not a proof that the register readings are transaction counts, or that the DART state proves a DMA-free bus.** The varying NVMMU-local upper register bits despite a matching shutdown outcome defeat a simplistic single-value signature for quiescence.

The corresponding synthetic unit tests require fail-closed interpretation when log sections are missing, prevent duplicated saved captures from inflating counts, reject malformed register statuses, and confirm the output excludes raw log content/identifiers. Run the analyzer with locally selected trusted dmesg files; do not add private logs to public Git. The analyzer does not access the phone or its storage.

**Next decision criterion:** obtain independent architectural evidence for a requester drain/fence, PCIe outstanding-transaction completion, and DART/NVMMU translation ownership before considering safe teardown. A stable checksum, FIFO or DART register is not that evidence.

## Power, recovery and publication boundaries

The SN2400 pilot configured a **300 mA USB input limit** with a bounded one-hour rollback lease. That setting is **not measured battery charge current**: real battery samples alternated between positive and negative, while USB VBUS remained around 4.9 V. Preflight checks reduce but do not eliminate hardware or data-loss risk. Never force-unload the quarantined storage module; subsequent experiments require a separate fresh supervised RAM boot.

Only sanitized aggregate data and gate outcomes are public. Private kernel logs, binaries, calibration/firmware, credentials, device identifiers, networking identifiers, DMA physical addresses and recovery artifacts remain outside Git.
