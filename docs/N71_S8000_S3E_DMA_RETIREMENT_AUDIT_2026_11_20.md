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

## 2026-11-23 clean-boot and NVMMU allocation-error guard

After an owner-attended PongoOS reboot, USB gadget and authenticated direct-USB SSH confirmed the expected N71/S8000 RAM kernel. The S3E module was **not loaded**. The SN2400 input-limit pilot was active at 300 mA, but the fuel gauge indicated **24%** at first preflight (temperature approximately 33.5 °C). A positive instantaneous battery current and a 300 mA USB input limit do **not** imply sufficient energy reserve or stable net charging. Accordingly, no new S3E/NVMe/DMA experiment was attempted on this boot.

An offline source audit identified a separate unwind path at `n71_storage_nvmmu_owned_trial()::alloc_fail`, which originally called all three `*_free()` helpers unconditionally. These allocation-failure branches precede the current invocation's NVMMU and endpoint activation, so ordinary pre-epoch unwind remains valid. However, the monotonic `n71_admin_dma_epoch_latched` flag can never be ignored, including at this label. The corrected path now **refuses every free after a latched DMA epoch**, holds `n71_unreleased=true` to retain the module/hardware associations, logs a sanitized quarantine event and returns `-3`. Before any latched epoch, the original early allocation cleanup remains unchanged.

The existing retirement policy for admin queue memory, 8 MiB HMB, NVMMU roots, and DART roots remains **fail closed** until independent evidence of hardware DMA quiescence. Additional offline regression tests assert the allocation-failure branch ordering, refusal-before-free, monotonically latched guard, and original no-epoch cleanup. The isolated ARM64 module build passed; **the rebuilt module has not been transferred to or loaded on the iPhone**. All locally held build outputs remain outside the public repository.

## 2026-11-23 CQE validation-before-doorbell guard (offline candidate)

An S3E source-level lifetime audit found that the one-shot `Identify NS1` path advanced CQ head doorbell `0x1004` before rejecting an invalid completion status, command ID, submission queue ID, or SQ head. The corrected implementation first requires the earlier phase-status read to match the copied CQE status, then performs a strict, pure in-memory comparison of the four CPU-synchronized CQE fields: status exactly `1` (phase 1 and zero error bits), CID `1`, SQID `0`, SQ head `1`. A malformed or foreign CQE is now rejected **without a CQ-head MMIO write**. A valid CQE retains the original single doorbell and data-path behavior; the separate DMA-retirement boundary is unchanged and never releases memory merely because a CQE is valid.

The new pure C helper has a host-compiled exhaustive synthetic test of 262,144 field values plus static ordering/side-effect checks. The project regression suite and matching isolated N71 ARM64 kernel-module build must pass before publication. This is an **offline driver correction**: no new NVMe/PCIe experiment, NAND modification, or hardware DMA-quiescence claim follows from it. On the current boot, the battery gauge was at 24%, so a new S3E trial remains deferred pending sufficient reserve and an authorized transfer method.

## 2026-11-23 expanded post-stop RAM witness — complete 16 KiB backing pages

The offline review found an observational blind spot: the original late DMA witness hashed only the first **4 KiB** of each 16 KiB Linux-owned CQ and Identify data backing page, despite synchronizing the **entire `PAGE_SIZE`** for noncoherent CPU/device access. A DMA write outside the expected 4 KiB command window could therefore remain undetected. The corrected observer now fingerprints both entire **16 KiB pages**, within the already allocated and mapped backing. It issues **no additional NVMe commands, hardware register writes, DMA map/unmap, page releases, or reset operations**.

The diagnostic still samples the same two pages 12 times with a nominal 50 ms interval, but now separates (1) samples differing from the initial fingerprint, (2) **transitions** between consecutive samples, and (3) the first **1-based sample index** departing from baseline. This makes a single persistent change distinct from multiple changes or a transient return-to-baseline. The log prints only counts and sample indices—never hashes, raw CQ/data bytes, addresses, identifiers, or protected firmware. Existing `cq_changes`/`data_changes` fields retain their legacy *non-baseline sample count* meaning; new `cq_transitions`/`data_transitions` are true adjacent-sample change counts.

Host-only C tests mutate bytes near the end of the 16 KiB CQ/data pages (outside the former 4 KiB observation window) and check stable samples, persistent changes, independent buffer transitions, first-deviation positions, return-to-baseline and sticky alerts. The owner-driver candidate is compiled for the exact N71 ARM64 kernel. **No physical late-write attribution, DMA quiescence or safe resource retirement is claimed.** The candidate has not been loaded on the currently running iPhone.

## 2026-11-23 controller-stop observation separated from legacy HMB qualification

Archived real-hardware logs already show a valid one-shot Identify Namespace 1 (15,625,000 × 4,096-byte blocks = **64,000,000,000 bytes**) and a register-consistent shutdown/disable with root and endpoint BME off. The subsequent legacy `stopped=0` and `rc=-3` result is **not** evidence that Identify failed: the original post-disable `qualified()` reuses pre-start ANS HMB descriptor values that the actual controller **clears to zero during shutdown**. That behavior was verified on physical N71 hardware in November. A cleared HMB register is also **not** proof that DMA is quiescent.

To avoid confusing these distinct facts in future owner-attended tests, `n71_admin_once_core()` now *only records* a new `controller_stop_observed` boolean. It becomes true when shutdown was attempted and acknowledged at `CSTS=0x9`, disable completed at `CSTS=0`, and the bus-master-off readback succeeded. The former `post_disable_qualified`, `stopped`, `rc`, and **all hardware operations and DMA quarantine gates remain unchanged**. The admin driver prints one sanitized `ADMIN_CONTROLLER_STOP_RO` line with the separate stop, old HMB qualifier and Identify-internal success predicates, explicitly `dma_quiescence_proven=NO` and `dma_release_authorized=NO`. No new MMIO access, no queue modification, and no DMA release is introduced.

The offline host harness distinguishes a valid controller-stop observation from a **legacy HMB post-stop qualification failure** and from missing/failed shutdown, controller disable, failed BME-off, and a timeout before controller startup. The N71 ARM64 module compiles against the running kernel's exact `vermagic`. The binary is host-side only and has **not** been staged or executed on the phone.

**Next physical target remains evidence of true DMA transaction drain and DART/NVMMU lifetime safety**, not further repetitions of the already-proven 64 GB Identify response. A proof of storage-controller shutdown may be necessary but is never sufficient for teardown, exposing a block device, or NAND modification.

## 2026-11-23 candidate DART0 error-context differentiation (offline only)

The prior 8 selected post-stop diagnostic captures all reported DART0 register **offset `0x10` = `0x00000500`**, while the separate NVMMU-local status varied. The available first-generation DART v0 driver source labels `0x10` an **error status** register, with adjacent `0x14` / `0x18` AXI request words and `0x1c` an error-address register: [Corellium DART v0 register map](https://github.com/corellium/linux-m1/blob/master/drivers/iommu/apple-dart-iommu.c). This is a *family-level hint*, **not proof** that the identical detailed register semantics apply to the N71/S8000 silicon or that bits `8`/`10` have known meanings. The status `0x500` must never be interpreted as the number of outstanding transactions or proof that requests have drained.

A new **opt-in read-only S3E observer** under the already existing `ans_phase_trace_ro` diagnostic is now prepared for a *separate*, later, owner-attended boot. It runs only inside the existing post-disable+BME-off diagnostic branch when the newly separated `controller_stop_observed` field, DART mapping ownership and a nonzero error status all qualify. It reads the three **candidate v0** offsets once and reports only whether each request/address field is nonzero and whether error bits 8/10 are set. **Raw request words, possible fault addresses and device identifiers are never logged**. The candidate does not clear W1C status bits, write DART/NVMMU/PCIe/NVMe registers, trigger transfers, unmap resources or change the strict DMA quarantine. An unchanged or zeroed error context is *not* evidence of DMA quiescence.

Before relying on interpretation of these registers, cross-check their offsets and semantics against the original S8000 IODART/AppleS5L8960XDART implementation; no attribution to a specific requester is yet permitted. Tests check opt-in guards, after-BME-off ordering, redacted-only output and absence of MMIO writes/resource release. The candidate is compiled offline for the exact N71 ARM64 kernel. **It has not been staged on or tested with the iPhone**, and no NAND storage operation is authorized by this change.

## 2026-11-23 original S8000 DART0 error-register source verification

**Source audit completed, without a new phone experiment.** The owner-held original Apple N71/S8000 kernelcache is verified through the existing authenticated prelinked-module provenance gate. The `AppleS5L8960XDART` original register access sequence uses the DART MMIO base stored by the S5L object, reads the status at offset **`0x10`**, tests **bit 31** of that value to select its fault-handling branch, then accesses the context words at offsets **`0x1c`, `0x14` and `0x18`**. The original code has a sibling DART instance with the same status/context offsets and bit-31 predicate. This corroborates the first-generation reference register layout *against actual S8000 original software* rather than assuming it from a newer Apple SoC. The external open-source DART v0 reference uses the same offset names, but the exact semantics and side effects on physical N71 remain a separate validation question.

The new source gate `tools/n71_original_s5l_dart0_error_context_gate.py` matches 13 selected original ARM64 instruction identities in the real, private kernelcache, **without reproducing binary payloads or publishing physical addresses**. Its synthetic tests mutate each pinned instruction and confirm that the gate rejects every alteration. The genuine kernelcache check passed; no original Apple binary or ADT data was committed.

**Interpretation correction:** the recurring post-stop `DART0 +0x10 = 0x00000500` has **bit 31 clear**. The verified Apple code therefore does not support classifying this value alone as a currently asserted fault on the bit-31-gated interrupt path. Bits 8 and 10 remain unexplained on S8000; an unacknowledged historical condition, diagnostic status, other fault mechanism or register-lifetime behavior are still possible. It is also **not a DMA pending-count or a drain fence**. A separate true-hardware transaction-drain/translation-retirement proof is still required before allowing unmap, module unload, block-device creation or NAND writes.

The optional context witness added earlier remains conservative and opt-in after observed shutdown/BME-off; it has **not been transferred to the iPhone**. The source evidence upgrades confidence in which registers it reads, not in any DMA cleanup authorization.

## 2026-11-23 guard DART0 post-stop context by original Apple bit-31 predicate

The owner-private original N71 kernelcache source gate proved that AppleS5L8960XDART reads status at offset `0x10` and tests its **bit 31** before branching to context at `0x14`, `0x18`, `0x1c`. The previous diagnostic candidate used merely `dart_fault != 0`, which would cause unnecessary context reads when the recorded status is `0x00000500`. That recurring value has **bit 31 clear**; neither the meaning of bits 8/10 nor absence of independent DMA transactions has been proven.

The corrected opt-in observer now requires **`dart_fault & BIT(31)`**, in addition to already verified controller stop, bus-master-off, and owned DART mappings. It therefore refuses additional context-register reads for all prior `0x500` status snapshots. If the original bit-31 predicate is present, the observer prints only boolean presence markers, with raw AXI request words / possible addresses redacted. These reads remain diagnostic-only; the existing conservative DMA quarantine is unchanged. Host synthetic tests cover status values `0`, `0x100`, `0x400`, `0x500`, `0x80000000`, and `0x80000500`. The isolated driver builds against the existing N71 ARM64 kernel. **No physical S3E trial or new NAND operations were performed.**

The live phone was below the hardware-experiment battery gate: at the beginning of this offline work, 23% state of charge, 294 mAh remaining and approximately -211 mA net cell current were observed via USB SSH, with the previous 300 mA charge lease already expired. The next physical DMA experiment remains blocked pending safe charging / power reserve, regardless of the successful code checks.

## 2026-11-23 original S8000 DART0 bit-31 replay of eight physical archives

The owner-held original `AppleS5L8960XDART` kernelcache demonstrated a **bit-31-gated error-context path** for DART0 status register `+0x10`. The host-only archive replay tool now makes this predicate explicit without treating it as a hardware DMA drain. It counts, from strictly parsed 8-hex-digit status fields, the number of snapshots with that branch predicate set or clear, and the number of invalid/missing status fields. Neither an unset bit 31 nor any other register value authorizes unmapping, DMA resource retirement, or an inference of a fault-free system. The tool continues to redact private log paths, identifiers and raw device details.

Replay of the **same eight previously selected real N71 S3E log files** found eight post-stop snapshots/eight distinct event signatures, **eight bit-31-clear DART0 statuses, zero bit-31-set statuses**, zero unparsable status fields, eight register-consistent shutdown snapshots and eight explicit DMA quarantines. These event signatures are not proof of eight independent boots. This narrows the reading of their recurring `0x00000500` to *not asserting the source-verified S5L bit-31 error-context branch*, while leaving bits 8/10, outstanding posted requests, and any independent DMA transaction drain **unresolved**.

Automated adversarial tests cover 0x100, 0x400, 0x500, 0x80000500, malformed fields and all-ones status; every case still denies DMA release. This is analysis of existing captures, **not a new physical storage experiment**, and does not justify NAND writes or mounting internal storage.

## 2026-11-23 read-only NS1 I/O command preparation: actual kernel-compiled code, no NAND access

The N71 device has already returned `Identify NSID=1` geometry: **15,625,000 × 4,096-byte LBAs = 64,000,000,000 bytes**. The current prototype's **only executed NVMe command remains the admin Identify**; there is still **no I/O SQ/CQ, no Linux block device and no NAND read/write**.

The next implementation artifact is the inert, portable real-driver header `experimental/port0/n71_s3e_read_only_io_plan.h`. It encodes **three standard NVMe 64-byte command candidates**: admin `Create I/O CQ` (`0x05`, CID 2), admin `Create I/O SQ` (`0x01`, CID 3), and one-sector NVM `Read` (`0x02`, CID 1 on QID 1). Admin Create SQ opcode `0x01` **is not an NVM WRITE**: the opcode namespace is determined by the submission queue. The candidates use a 16-entry queue, one 4096-byte sector, no interrupt, and only NSID 1, with strict 64-bit SLBA limits and 4 KiB-aligned, distinct, below-36-bit candidate IOVAs. On any invalid argument the encoder returns an error **without touching the output buffer**. The exact 64-byte wire format is tested with a host-compiled C harness; malformed LBA, aliased/unaligned/out-of-range IOVAs, wrong LBA geometry and bad namespace bounds are refused.

**Important S8000-specific qualification:** S8000 uses an Apple-custom ANS/NVMMU FlatDMA pointer convention: the actual successful admin Identify command used the `0x40000000` data tag and command flag `BIT(5)`. The semantics of **these flags, queue allocations, page-count TCB/SGL and I/O command PRP1** have **not** yet been proven for an NVM Read. The currently staged I/O Read encoder intentionally leaves the vendor-specific command flags at **zero/unqualified**. Therefore, its output is only a **standard-protocol candidate**, *not* an approved sequence for the physical iPhone. Do not send it to hardware until that path is source-verified, queue memory is independently allocated/pinned, and DART/NVMMU translations are authenticated.

The pilot source includes the new header and seven actual kernel NVMe struct-offset compile-time assertions (`rw.dptr`, `rw.slba`, `rw.length`, `create_cq.prp1/cqid`, `create_sq.sqid/cqid`). There is **no call site** in the live admin path: no new doorbells, DMA map/unmap, HMB writes, physical reads, resets or teardown. An isolated ARM64 build with the running kernel's exact `vermagic` passed. The module is retained **only on the Dell**; it has not been staged to the phone.

**Concrete hardware path to the first 4096-byte NAND read (still pending):**

1. Verify with the original N71 `IONVMeFamily` driver that the I/O SQ/CQ creation commands, Apple command flags, I/O PRP1/FlatDMA descriptor and queue-doorbell layout match this controller. A generic NVMe driver for ANS2 is not authoritative for S8000.
2. Allocate dedicated Linux-owned **I/O SQ, I/O CQ and data backing**, distinct from the existing eight admin/DART pages and 8 MiB HMB; verify DART0 mappings across all SIDs and the exact NVMMU TCB/SGL data path. Never overwrite inherited or unowned mappings.
3. Admit a **single read-only** LBA0 command only after a real completed admin queue creation/acknowledgment and ownership verification, with a pinned DMA epoch and no automatic release. Never issue I/O `WRITE`, Format, Sanitize, DSM or namespace management.
4. Validate the I/O CQ's phase, SQID, CID, success status and separate data-plane completion. Treat a read's bytes as private and do not publish raw LBA0/iOS metadata. Independent DMA drain still requires evidence before releasing pages or unloading the module.
5. Only after physical single-sector reads and a safe DMA lifetime are established, implement a read-only `gendisk` with `set_disk_ro`/`BLKROSET`, integrity checks and an explicit no-automount policy. Persistent filesystem writes require a separate recovery-capable backup and owner approval.

**State:** This work closes the *command layout / software bounds* portion of the future read path. It does **not** close the ANS-specific command ABI, I/O queue hardware, NVMMU mappings or DMA quiescence. Storage remains unavailable to Linux, and the battery on this RAM boot has not yet met the 50% physical test target.

## 2026-11-23 N71 DART0 I/O queue mapping — host-side four-stream staging

The existing physical admin-Identify pilot mapped **0x80010000 → DART0 L2[16] (Admin SQ)** and **0x80011000 → L2[17] (Admin CQ)**, repeating the two entries on all **four DART0 streams** and two owned L1 windows. This is the only DART queue mapping *previously exercised* by the live controller. A dedicated pure-C transactional staging helper, `experimental/port0/n71_s3e_ro_io_dart_map.h`, now prepares **0x80012000 → L2[18] (I/O QID1 SQ)** and **0x80013000 → L2[19] (I/O QID1 CQ)** while preserving both existing admin entries and all other entries. The new helper is **included in the real admin driver and compiled for the exact N71 ARM64 kernel**, but deliberately has **no call site or physical hardware side effects**.

The helper requires four distinct CPU-owned 4096-byte L2 table views, matching original admin entries, *empty* I/O slots on every stream, five different physically owned **16 KiB-aligned** and under-36-bit frames (admin SQ/CQ, I/O SQ/CQ, and data), and optional explicitly listed inherited/foreign physical exclusions. Every stream and every frame is validated **before writing a single page-table byte**, so unexpected stale I/O leaves, foreign ownership, aliasing, misalignment or overlap aborts the entire staging request, leaving all four original views unchanged. Only CPU staging memory is modified; the caller must independently qualify a pre-BME configuration, noncoherent cache synchronization, DART L1 root ownership, TLB invalidation and their resource lifetime before ever installing a device-visible mapping. A zeroed or staged CPU table **does not** prove a working physical translation.

**Data-path separation:** the new read-data 16 KiB physical frame is not represented by DART L2[18/19]. The successful Apple ANS admin Identify used a FlatDMA tagged address **0x40000000**, a separately mapped TCB and SGL and Apple command flag `BIT(5)`. The former read-data tag **0x40001000 was incorrectly treated as a second tag**: the authentic S8000 NVMMU code shifts the tag index by 23 bits, so that address is only a 4 KiB offset *within tag 0*. The corrected **tag 1 base is 0x40800000**, validated against the original Apple S8000 kernelcache and ADT. Distinct TCB addressing is proven, but its use with an NVM Read in `IONVMeFamily` is still not qualified. The read-only command encoder now rejects reuse of the live Identify data tag, preserving its exact 4096-byte read size and NS1 LBA bounds. No unverified NVMMU TCB extension or I/O data transfer has been executed.

Executed host-native C tests stage and inspect all four real-format 4 KiB L2 views, check every unchanged byte outside the two new entries, ensure the data physical frame is **not** a DART queue mapping, verify all four streams' transactional refusal on any occupied/mismatched slot, and exercise physical ownership/inherited range, alignment and address boundary rejection. The N71 ARM64 cross-build includes compile-time invariants for index 16/17/18/19 and 16 KiB host frames. The revised module remains on the Dell only. **No device-visible mappings, NVMe command, NAND read/write, module load/unload or reset occurred** in this mapping-development step.

**Next concrete gate:** add and qualify Linux-owned physical I/O SQ/CQ/data allocations with explicit post-BME lifetime retention, then validate the **S8000-specific NVMMU FlatDMA I/O read descriptor against original Apple executable code**. Only after a safe powered physical preflight can an attended read-only command be considered. The existing BME-epoch monotonic quarantine remains non-negotiable; no block device or filesystem access has yet been established.

## 2026-11-23 real-kernel pre-BME I/O DMA frame allocator (inert on phone)

The former four-stream DART0 queue-leaf staging is now accompanied by an actual N71 ARM64 Linux DMA API implementation in `experimental/port0/n71_s3e_ro_io_dma_alloc.h`, included by the existing admin driver **without any caller**. When separately enabled in a future qualified pre-BME path, it can acquire and identity-DMA-map **four distinct 16 KiB Linux pages** for future I/O SQ, I/O CQ, the initial read-data buffer and its separate SGL. It rejects DMA-coherent devices, wrong page size, wrong N71 PCI commands, any running controller/BME epoch, partially owned admin pages, mismatched DMA addresses or physical addresses outside the 36-bit aperture. On a later qualified invocation, new memory is checked **before zeroing** against all inherited NVMMU and DART structures, inherited and Linux-owned HMB, owned NVMMU TCB/aux, owned DART root pages, all eight admin pages and all previously allocated new pages. Admin SQ/CQ are first-class already-owned frames, not foreign conflicts in the final six-frame plan. The implementation is built against the exact running N71 kernel `vermagic`, and test contracts verify all important barriers and no call sites in the current execution flow.

Before the **first** bus-master epoch, allocation failures unmap/free only resources acquired by this allocator. After the monotonic `n71_admin_dma_epoch_latched` becomes true, the release helper immediately refuses release, retains all pages and signals the existing storage quarantine; code does **not** invent a DMA-drain condition based on CC/CSTS or BME alone. These are candidate physical frame allocations and are **not yet a device-visible DART L2 update**. In particular, the data frame remains unreferenced by an authenticated S8000 NVMMU TCB/SGL entry. No I/O queue creation, read opcode, device DMA test, module transfer to phone, NAND read or NAND write occurred at this stage. The hardware-access preflight stays blocked by an indicated battery below the previously chosen 50% gate, despite an independently running finite 300 mA charging lease.

Next hardware milestone: independently verify the original S8000 I/O FlatDMA descriptor encoding and retention protocol, wire these allocations into an **explicit pre-BME and owner-attended** controlled path, then validate the four DART queue mappings and the data TCB transaction without releasing resources after BME. Only then is a read-only one-sector attempt justified.

## 2026-11-23 original Apple NVMMU tag stride and isolated TCB1/SGL staging

**Important correction of a risky address alias:** The first guessed `0x40001000` for a read-data pointer would **not** select a distinct NVMMU TCB on S8000. A provenance-checked source gate now analyzes the owner's original `AppleS800xPCIe` executable from the N71 kernelcache and the authenticated ADT. The real code fetches a 16-bit tag, computes **`tag_index << 23`**, combines it with the configured **`0x40000000` NVMMU virtual-base**, and uses a **128-byte TCB slot stride**; the ADT specifies **128 tags**. The source gate passes on the genuine original inputs and rejects mutation of any of nine pinned instructions. It exposes only booleans and tag geometry, never original Apple binaries or private identifiers.

Correct logical separation: **tag 0 / Identify = `0x40000000`**, **tag 1 candidate / Read = `0x40800000`**, with 8 MiB of virtual address space per tag. A 4 KiB offset (`0x40001000`, `0x40801000`) is explicitly rejected for our one-sector tag-base-only command, as are unallocated tag2 addresses. The host-native NVMe encoder and four-stream DART L2 staging were updated to require this exact tag1 address. **This does not verify the Apple IONVMeFamily `Read` command flags, timing, queue creation, payload completion or DMA drain**.

The real Linux DMA allocator now has **four dedicated 16 KiB pages**, rather than three: I/O SQ, I/O CQ, one read-data page and one separate read SGL page. These join the two previously owned admin SQ/CQ pages in a **six-frame physical ownership / non-overlap check**. No SGL is shared with `Identify` and no read-data page is written into the DART queue leaves. A new pure C tag1 staging helper validates tag0's existing one-page Identify TCB, requires the second **128-byte TCB** and its independent SGL page to be entirely empty, then stages the candidate device-to-host, one-page TCB at offset128 and a single SGL PFN entry. It preserves all existing TCB bytes outside the tag1 slot and fails atomically on partial/foreign data or aliases. The candidate fields are patterned on the **real, successful Identify DMA**, *not yet source-qualified for NVM READ*.

Both helpers are included in the actual N71 ARM64 pilot module and its exact kernel ABI assertions; **there are zero execution call sites**, no new DART/MMIO writes or NVMMU publication, no SQ doorbells and no physical S3E test. Host-native C fixtures exercise the real 128-byte/16-KiB layouts, all four DART0 streams, accidental tag0 overlaps, occupied tag1 and SGL rejection, and six-frame physical exclusion. The existing monotonic post-BME quarantine is unchanged. The low-SOC iPhone boot remains separate from this entirely offline storage change.

**Next hardware prerequisite:** verify the NVM Read's vendor-specific command flags and FlatDMA TCB direction/data-layout against the N71 `IONVMeFamily` code, then qualify a dedicated owner-attended pre-BME activation path and independent DMA retirement. The NAND stays read/write untouched.

## Power, recovery and publication boundaries

The SN2400 pilot configured a **300 mA USB input limit** with a bounded one-hour rollback lease. That setting is **not measured battery charge current**: real battery samples alternated between positive and negative, while USB VBUS remained around 4.9 V. Preflight checks reduce but do not eliminate hardware or data-loss risk. Never force-unload the quarantined storage module; subsequent experiments require a separate fresh supervised RAM boot.

Only sanitized aggregate data and gate outcomes are public. Private kernel logs, binaries, calibration/firmware, credentials, device identifiers, networking identifiers, DMA physical addresses and recovery artifacts remain outside Git.
