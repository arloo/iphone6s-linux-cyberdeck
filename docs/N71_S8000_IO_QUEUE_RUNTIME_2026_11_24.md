# N71/S8000 one-shot I/O queue runtime — 2026-11-24

## Scope and acceptance

This change connects the previously host-only DMA allocator and queue encoders to an explicitly armed kernel path. Its new physical question is whether the S8000 controller accepts **Admin Create I/O CQ followed by Admin Create I/O SQ**, QID 1, depth 16, polling only. Identify Namespace1 is required setup within this new experiment; the already accepted 64 GB geometry is not a new milestone.

At this checkpoint the candidate has been ARM64-compiled and host-tested; **physical queue acceptance has not yet been established**. Neither NVM Read nor NVM Write is reachable through this mode. No block device, filesystem, NAND persistence or DMA-drain claim follows from this implementation.

## Explicit selection and ownership

`ans_io_queue_once=1` requires `ans_identify_once=1`, no queue-retirement or late-DMA probe, and explicit `ans_io_queue_flags=0` or `32`. Disabled mode requires the flag to remain unselected. The first proposed queue-only hypothesis is byte1=0, using direct owned DART queue IOVAs. This is an experimental selection, not a source-qualified live Apple Read policy. There is no automatic alternative-flag retry.

Before BME, four independent 16 KiB Linux DMA pages are allocated for I/O SQ/CQ and future data/SGL. The latter two remain unused. Four CPU-only shadow L2 views are validated before publishing owned queue leaves 18/19 on all four DART0 streams. Admin leaves 16/17 remain unchanged. Controller CC/CSTS and both PCI command master bits must remain off during publication. A bounded DART invalidation follows; any uncertainty retains backing.

The controller gate requires the observed NVMe 1.0.1 version, at least 16 entries, 4 KiB minimum controller pages, NVM command-set support and a four-byte doorbell stride. Current Identify must independently validate the accepted 15,625,000 by 4096-byte geometry before queue submission.

Only canonical 64-byte Admin commands are permitted: Create CQ opcode 5/CID 2, then Create SQ opcode 1/CID 3. Opcode1 here belongs to Admin QID 0; no NVM Write path exists. Foreign/nonzero SQ or CQ slots are refused rather than erased. Each completion requires phase/status 1, matching copied status, exact CID, SQID 0 and expected SQ head before CQ acknowledgement. Polling is bounded and stops on unexpected controller state. SQ creation never follows an unsuccessful CQ result.

After allocation, all I/O pages and existing admin/HMB/DART/NVMMU ownership remain pinned through this RAM boot, including after successful shutdown/disable/BME-off. No queue deletion, table unmapping, backing release or forced module unload is authorized by this experiment. The whole-pilot `rc=-3` is compatible with deliberate quarantine; it cannot establish or refute individual queue acceptance.

## Validation

- ARM64 module builds against the running N71 batt2 kernel without compiler warnings.
- All 1,916 host tests pass, followed by the synthetic HBPP audit and project/evidence validator.
- The new native-C harness checks capability/mode gates, exact command domain/order/bytes, denied and failure branches, 131,072 completion-status cases and 2,048 command mutations.
- Source-order checks cover ownership before publication, validation before CQ-head acknowledgement, bounded polling, one-attempt latching and retained resources.
- The module SHA-256, exact vermagic and complete port0/port1 C/header source snapshot are recorded privately. No original firmware, binary module, DMA address or device/backup identifier is published.

## Physical procedure and success evidence

Use the already completed encrypted iOS backup and a fresh S3E-clean RAM boot. Recheck at least 50% reserve, health Good, temperature below 37.5 C with margin to the owner's 38 C ceiling, healthy finite 300 mA charger lease, configured USB and matching kernel/module/source hashes. Record eight fresh electrical samples before the attempt. Copy only the candidate module to phone RAM over authenticated, strictly pinned USB SSH.

Load exactly once with the existing port0/DART/NVMMU/HMB Identify guards plus `ans_io_queue_once=1 ans_io_queue_flags=0`. Do not retry within this boot. Save raw kernel output privately.

Queue acceptance requires `IO_QUEUE_ONCE rc=0 cq_posted=1 cq_valid=1 sq_posted=1 sq_valid=1`, supported by both matching Admin completion records. A syscall-loader success, accepted Identify, prepared mapping or controller Ready alone is insufficient. Failure stops this hypothesis; it does not authorize alternate flags or any NVM Read. The later LBA0 step still needs separate transport/FlatDMA qualification and its own concrete review.
