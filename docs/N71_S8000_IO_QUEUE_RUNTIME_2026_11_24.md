# N71/S8000 one-shot I/O queue runtime — 2026-11-24

## Scope and acceptance

This change connects the previously host-only DMA allocator and queue encoders to an explicitly armed kernel path. Its new physical question is whether the S8000 controller accepts **Admin Create I/O CQ followed by Admin Create I/O SQ**, QID 1, depth 16, polling only. Identify Namespace1 is required setup within this new experiment; the already accepted 64 GB geometry is not a new milestone.

One physical module insertion reached the new owned mappings, then the initial live gate refused before either Create command. That first candidate did not establish queue acceptance. The corrected candidate subsequently received valid Create CQ and Create SQ completions, followed by a shutdown fault; see the latest physical section below. Neither NVM Read nor NVM Write is reachable through this mode. No block device, filesystem, NAND persistence or DMA-drain claim follows from this implementation.

## Explicit selection and ownership

`ans_io_queue_once=1` requires `ans_identify_once=1`, no queue-retirement or late-DMA probe, and explicit `ans_io_queue_flags=0` or `32`. Disabled mode requires the flag to remain unselected. The first proposed queue-only hypothesis is byte1=0, using direct owned DART queue IOVAs. This is an experimental selection, not a source-qualified live Apple Read policy. There is no automatic alternative-flag retry.

Before BME, four independent 16 KiB Linux DMA pages are allocated for I/O SQ/CQ and future data/SGL. The latter two remain unused. Four CPU-only shadow L2 views are validated before publishing owned queue leaves 18/19 on all four DART0 streams. Admin leaves 16/17 remain unchanged. Controller CC/CSTS and both PCI command master bits must remain off during publication. A bounded DART invalidation follows; any uncertainty retains backing.

The controller gate requires the observed NVMe 1.0.1 version, at least 16 entries, 4 KiB minimum controller pages, NVM command-set support and a four-byte doorbell stride. Current Identify must independently validate the accepted 15,625,000 by 4096-byte geometry before queue submission.

Only canonical 64-byte Admin commands are permitted: Create CQ opcode 5/CID 2, then Create SQ opcode 1/CID 3. Opcode1 here belongs to Admin QID 0; no NVM Write path exists. Foreign/nonzero SQ or CQ slots are refused rather than erased. Each completion requires phase/status 1, matching copied status, exact CID, SQID 0 and expected SQ head before CQ acknowledgement. Polling is bounded and stops on unexpected controller state. SQ creation never follows an unsuccessful CQ result.

After allocation, all I/O pages and existing admin/HMB/DART/NVMMU ownership remain pinned through this RAM boot, including after successful shutdown/disable/BME-off. No queue deletion, table unmapping, backing release or forced module unload is authorized by this experiment. The whole-pilot `rc=-3` is compatible with deliberate quarantine; it cannot establish or refute individual queue acceptance.

## Validation

- ARM64 module builds against the running N71 batt2 kernel without compiler warnings.
- The original integration passed 1,916 host tests; the live-phase correction passes all 1,917 tests, followed by the synthetic HBPP audit and project/evidence validator.
- The new native-C harness checks capability/mode gates, exact command domain/order/bytes, denied and failure branches, 131,072 completion-status cases and 2,048 command mutations.
- Source-order checks cover ownership before publication, validation before CQ-head acknowledgement, bounded polling, one-attempt latching and retained resources.
- The module SHA-256, exact vermagic and complete port0/port1 C/header source snapshot are recorded privately. No original firmware, binary module, DMA address or device/backup identifier is published.

## Physical procedure and success evidence

Use the already completed encrypted iOS backup and a fresh S3E-clean RAM boot. Recheck at least 50% reserve, health Good, temperature below 37.5 C with margin to the owner's 38 C ceiling, healthy finite 300 mA charger lease, configured USB and matching kernel/module/source hashes. Record eight fresh electrical samples before the attempt. Copy only the candidate module to phone RAM over authenticated, strictly pinned USB SSH.

Load exactly once with the existing port0/DART/NVMMU/HMB Identify guards plus `ans_io_queue_once=1 ans_io_queue_flags=0`. Do not retry within this boot. Save raw kernel output privately.

Queue acceptance requires `IO_QUEUE_ONCE rc=0 cq_posted=1 cq_valid=1 sq_posted=1 sq_valid=1`, supported by both matching Admin completion records. A syscall-loader success, accepted Identify, prepared mapping or controller Ready alone is insufficient. Failure stops this hypothesis; it does not authorize alternate flags or any NVM Read. The later LBA0 step still needs separate transport/FlatDMA qualification and its own concrete review.

## Physical outcome: stopped before Create CQ; phase-contract correction

Exactly one physical insertion of source commit `0c28195713a96472e6de6a3b62a26fb8d14e285a`, module SHA-256 `25f95c2c77c4af188023fa00b80e26d798ef566458eeefe3813b551e552b0cba`, was performed. Earlier telemetry-only preflights did not insert any storage module. The completed encrypted backup metadata and exact kernel/module/source snapshot were checked before insertion.

The qualified eight-sample power window remained at 58% and 32.9 C with VBUS 4.875 V throughout; mean net current was +23.5 mA, median +30.5 mA and the minimum was -37 mA. Instantaneous fuel-gauge labels varied. Two immediate nonnegative-current observations preceded insertion; the final one was +85 mA. This is bounded trial power evidence, not proof of permanently sustainable charging. No kernel charger or thermal/voltage limit was weakened.

| New observation | Physical result |
|---|---|
| Four new owned I/O pages and four-stream DART queue mappings | Prepared with controller and BME off, flags hypothesis 0 |
| Current Identify setup | Valid CQE and 64 GB/4096-byte geometry, reused as setup |
| Initial live queue gate | Refused, inner rc=-1 |
| Create CQ / Create SQ | Neither attempted nor posted; no hardware flag acceptance result |
| Shutdown and disable | Shutdown rc 0/CSTS 9; disable rc 0/CSTS 0; master off |
| Resource lifetime | All DMA mappings/backing and original owner retained; whole-pilot rc=-3 |
| NVM Read / Write and internal block device | No command submitted; no block device |

The integration error is deterministic from source: `n71_io_queue_qualified` called `n71_admin_qualified`, which calls the disabled-phase HMB owner predicate. That original predicate explicitly requires both PCI command words 2 and CC/CSTS 0. Queue submission instead correctly requires both commands 6, CC 0x460001 and CSTS 1. Consequently, both phase contracts could never pass together. The physical rc=-1 before cq_attempted corroborates the stopped path; it does **not** demonstrate that byte1=0, Create CQ, Create SQ or their addresses were rejected by hardware.

The correction leaves the existing disabled preparation/default Identify checks unchanged. A separate live owner check validates retained kernel mappings, active endpoint/DART ownership, the exact owned NVMMU roots and SART/HMB backing. Only after that owner check may the live snapshot read the active controller registers. A portable live-phase gate retains the required CC/RDY/PCI command state, original HMB descriptor, exact geometry and all protocol/ownership checks. Named rejection bits report any failed group before a queue post. This avoids the incompatible disabled-only reader without granting DMA release.

The regression harness now exercises the valid active snapshot, all 81 root/endpoint/CC/CSTS phase combinations, and individual mode/capability/epoch/backing/Identify/owner/interrupt/HMB failures. A source regression check forbids calling the disabled HMB predicate or reader from the live path. The corrected ARM64 module has SHA-256 `50d863dc62abbd7a721524fe2703289c6f395b9262ef37966dc138d48209999b` and has **not** been inserted. All live HMB assumptions still need observation; a later refusal must be investigated from its explicit gate bits.

The current boot keeps the original storage pilot pinned. Do not unload or replace it, retry the experiment or infer DMA drain from shutdown. A fresh owner-attended RAM Linux boot is required before testing the corrected candidate. No reboot was triggered by this experiment.

Sanitized machine-readable evidence: [physical queue-only result](N71_S8000_IO_QUEUE_PHYSICAL_2026_11_24.json).

The corrected candidate passes all **1,917** host tests, the synthetic HBPP audit, manifest/evidence validation and the exact-kernel ARM64 build. These are host-side validations, not physical queue acceptance.

## Owner-attended RAM payload prepared

A new private RAM image packages the corrected storage module at `/usr/lib/cyberdeck/n71-s3e-io-queue-live-phase.ko` without loading it automatically. Its SHA-256 is `1921795d5c31e84fc5a6e7f41c8d2a8395e8fb928d08b95d87ef300ad1e142fa` (27949306 bytes). The charger module is updated from the older binary to the already physically observed phase-diagnostic binary `b559145fd3c1c30ba3aea008544ffb2fcf7aa737b69773f53f1512b1d197eec7`; the finite 300 mA startup profile and guards are preserved. The complete runtime hash manifest, gzip/CPIO roundtrip, module ABI, and byte-identical remaining rootfs entries are verified. Bootloader, bootargs, DTBs and compressed kernel are byte-identical to the reference.

The attended launcher validates image hash/size, preserves a still-running Linux session, and otherwise uses the existing owner-assisted DFU/Pongo workflow. The image remains private because it contains owner credentials and device assets. It has not yet been physically booted; no new hardware command was sent during packaging.

## Corrected candidate: first physical CQ/SQ acceptance, shutdown fault

The owner booted the verified private RAM image and a new directly attached N71/S8000 session was verified over authenticated, strictly pinned USB SSH. Both embedded module hashes and the complete runtime hash manifest matched the prepared payload. Exactly one corrected storage-module insertion was performed in this boot.

The controller accepted Admin Create CQ (opcode 5/CID 2) and Create SQ (opcode 1/CID 3), QID 1/depth 16/byte1=0. Each completion had phase/status 0001, SQID 0 and the expected SQ head. The wire-level validator accepted both snapshots and the create-only summary returned rc 0. **This establishes physical volatile queue creation acceptance**, not namespace NVM block-data transfer.

The subsequent normal-shutdown attempt failed: the first shutdown poll observed CSTS 0x7 (CFS set), shutdown rc=-2; controller disable timed out after 2,000 polls with CSTS still 0x7. Both PCI bus-master bits were readback-verified off, and the whole pilot retained all DMA mappings/pages and original ownership with rc=-3. No module unload, in-boot retry, NVM Read/Write or internal block device followed. The core branch proves CFS was clear in its pre-shutdown status sample; the exact onset and cause are not established. Do not reinterpret the two successful Create completions as a stable controller lifecycle.

The tested kernel's native `drivers/nvme/host/pci.c` uses `nvme_delete_io_queues` before `nvme_disable_ctrl`; the helper completes Delete SQ before issuing Delete CQ. The current create-only pilot does not perform these volatile deletion commands. A separate, explicitly armed empty-queue deletion trial is therefore the next concrete hypothesis. This source comparison does not prove that the omitted deletion caused the S8000 CFS, nor qualify a data Read. Even accepted queue deletion must not release any DMA backing.

Sanitized physical evidence: [first corrected queue acceptance](N71_S8000_IO_QUEUE_ACCEPTANCE_2026_11_24.json).

The subsequent default-off empty-SQ/CQ deletion candidate is now ARM64-built, passes all 1,919 host tests and is packaged in a verified inert RAM image. It has not been physically tested. See [deletion trial and acceptance criteria](N71_S8000_IO_QUEUE_DELETE_TRIAL_2026_11_24.md).
