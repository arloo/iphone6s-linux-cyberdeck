# N71/S8000 temporary read-only Linux block bridge — 2026-11-24

## Current status and scope

The preceding physical sequence 0,1,0,1 is accepted and reused as the transport baseline. This new candidate is ARM64-built and host-tested but **has physically passed one fresh-boot kernel block-bridge trial**. It tests a new integration boundary: four real Linux bios must cause the four hardware Reads and receive data only after the existing exact-CQE, independent data and guard checks. It does not serve a RAM-backed imitation of NAND or a Dell NBD disk.

This is a temporary, kernel-client-only qualification bridge, not a usable userspace disk. A gendisk named n71nand_ro advertises the Identify-derived 64,000,000,000 bytes with 4096-byte logical blocks, but its request policy admits only four trusted preallocated bios in the fixed sequence 0,1,0,1. The registration is removed after the trial. Whole-drive arbitrary access, mounting and persistent installation remain unqualified.

## Admission, data and lifetime

The separate default-off ans_ro_block_once mode requires explicit flags32 plus Identify, Create and Delete opt-ins with queue flags0. Single-Read and standalone-series modes must stay disabled, with their flags unselected. Invalid combinations fail before the board/PMGR gate.

Before BME, the previously accepted four-tag transport prepares eight independent DMA data/SGL frames and four unmapped snapshots. The bridge additionally allocates four distinct CPU-only bio targets, checks each against inherited/base-I/O/admin/series owners and earlier targets before zeroing, and never maps these targets for DMA or publishes them in a TCB/SGL. Four separate bio objects each reference one target.

The kernel client calls submit_bio_wait from a separate thread while the module init thread retains the valid hardware owner/context and performs MMIO. The submit_bio callback only validates and queues one trusted bio under a spinlock; it neither sleeps nor performs hardware access. It verifies READ, exact 4096-byte length, 512-byte-sector offset 0 or8 in sequence, one segment at offset0, expected bio identity and expected target-page identity. Duplicate, concurrent, malformed, foreign, exhausted, closed or non-Read requests fail without consuming a hardware slot. Each expected request has an eight-second arrival bound.

The init thread then executes the existing fixed command through its fresh tag/CID/head/SQ/CQ slot. It checks exact completion before ACK, independent data and the 12 KiB guard, creates the private snapshot and checks completed buffers for change. Only then is that snapshot copied into the trusted CPU target and the bio completed. The client checks target guards and privately compares both same-LBA pairs. No sector bytes or hashes are logged or exported.

On exit, admission closes under the same lock; any pending bio receives an error before the client is joined. Only then are software bios/gendisk/major objects released. All DMA, snapshots, CPU targets and original hardware owners remain retained. Successful kernel bio completion is not an independent DMA-drain proof. A client/bridge failure prevents successful-series acceptance and queue deletion; the usual conservative controller stop/quarantine still applies.

The disk is read-only, has GENHD_FL_NO_PART and denies every open, including read opens, so no automounter, partition tool or user process can consume the trial budget. The independent callback rejects every non-Read operation even if a read-only flag were changed. The client and its target frames are distinct from the device-visible buffers; no filesystem, Write, discard, flush or passthrough command is submitted.

The implementation uses the exact installed kernel interfaces in include/linux/bio.h, include/linux/blkdev.h, block/bio.c, block/genhd.c and block/blk-settings.c. This 16 KiB-page kernel rejects max_hw_sectors below PAGE_SECTORS, so that hardware limit meets the kernel minimum while max_dev_sectors and the independent request policy enforce 4 KiB transfers. No API is inferred from a different kernel version.

## Acceptance and preparation

Physical acceptance requires all of the following in one fresh, owner-attended epoch:

- One RO_BLOCK_REGISTERED event with correct geometry, read-only/no-partition/private-open policy.
- Exactly four RO_BLOCK_DELIVERED events and all four existing exact Read CQEs, independent 512-word arrivals, intact guards and private snapshot equalities.
- RO_BLOCK_ONCE rc0, registered1, removed1, bios_admitted4, bios_delivered4, client_completed4, client_rc0, private_pair_equality1 and rejected0.
- Five unchanged retained-RAM checks for all four completed buffers, exact Delete SQ/CQ, normal shutdown, disable and readback-verified BME-off. Quarantine at whole-pilot rc-3 remains expected and is not DMA-release authority.

The exact-kernel ARM64 build is warning-free. Five new tests compile the real portable admission policy and exercise mode combinations, malformed/foreign/non-Read requests, large sector values, duplicate requests, exhaustion, terminal failures and rejection atomicity. Source checks cover early mode gating, CPU-only pre-epoch targets, validation/stability before bio completion, no MMIO in the callback, join-before-software-release and hard write/open/partition restrictions. The full 1,933-test suite, HBPP audit and manifest/evidence validator are required before handoff.

The private RAM image changes only the inert S3E module and its runtime hash entry from the accepted four-Read image. All other rootfs records, bootloader, bootargs, both DTBs, compressed kernel and finite guarded charger remain byte-identical. All ten runtime manifest entries and the gzip/CPIO roundtrip are verified. The image and credentials remain owner-private; storage is never auto-inserted.

The current successful-series boot is retained and cannot run this candidate. A fresh attended RAM boot, strict USB/SSH verification, completed encrypted-backup metadata, adequate reserve, Good health, finite guarded input/VBUS from a physically qualified source and temperature margin below the owner's 38 C ceiling are required before the single attempt.

[Candidate metadata](N71_S8000_RO_BLOCK_BRIDGE_CANDIDATE_2026_11_24.json), [accepted underlying four-Read evidence](N71_S8000_READ_SERIES_ACCEPTANCE_2026_11_24.json) and [canonical storage ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).

## Fresh boot power gate — 2026-11-25

The exact candidate boot is now authenticated, but reserve was only 21% and the automatic charger skipped startup below 35%. The bridge remains unattempted while a separately guarded, finite charge-only recovery restores reserve. The S3E epoch is unused. [Measured power gate and recovery](N71_S8000_RO_BLOCK_BOOT_POWER_GATE_2026_11_25.md).

## Qualified external-power continuation — 2026-11-25

The source-specific external 5 V pilot and finite 500 mA monitor are now physically qualified as documented in [external-source acceptance](N71_S8000_EXTERNAL_CHARGER_ACCEPTANCE_2026_11_25.md). This is an allowed source/profile alternative to the earlier Dell 300 mA preparation condition; it does not alter the module, any voltage/thermal guard or namespace request budget. The initial USB-attended boot remains the authenticated unused epoch. Temporary WiFi control must use the same pinned host key and exact boot identity; no password or host-key checking downgrade is permitted. A volatile percentage alone cannot open the storage gate: require stable reserve, Remaining/Full Charge consistency, fresh healthy native monitor, qualified VBUS/cell/temperature, exact unchanged binary and no prior S3E attempt.

## Physical acceptance: four Linux bios over real NVMe

On 25 November, the exact candidate from source ff02944a28d3794825504d650bde6456fdaa358f was inserted once in the authenticated, previously unused S3E epoch. Source, runtime/module/image hashes, board/kernel, encrypted-backup metadata and strict same-key/boot identity passed. The external 5 V source was qualified separately before storage. Eight fresh samples showed 51% reported reserve, RC/FCC 50.32–50.40%, 31.9 C, cell 4.017–4.025 V and VBUS 5.100–5.125 V on the finite 500 mA lease. The immediate counter ratio was 50.87%; reported percentage was not used alone.

The temporary n71nand_ro disk registered the Identify-derived 64,000,000,000 bytes with 4096-byte logical blocks, read-only mode, partition scan disabled and every userspace open denied. The private kernel client then completed exactly four bios:

| Index | LBA | Tag / CID / SQ head | Exact status | Validated data and Linux completion |
|---|---|---|---|---|
| 0 | 0 | 1 / 1 / 1 | 0001 | 512-word arrival, intact 12 KiB guard, bio delivered |
| 1 | 1 | 2 / 2 / 2 | 0001 | 512-word arrival, intact 12 KiB guard, bio delivered |
| 2 | 0 | 3 / 3 / 3 | 0001 | 512-word arrival, intact 12 KiB guard, bio delivered |
| 3 | 1 | 4 / 4 / 4 | 0001 | 512-word arrival, intact 12 KiB guard, bio delivered |

Each Read needed two CQ polls and one data poll. Both complete same-LBA comparisons passed in the private snapshots and in the kernel client's returned targets. The bridge recorded rc0, registered1, removed1, admitted4, delivered4, client_completed4, client_rc0, private_pair_equality1 and rejected0. This is actual Linux block-layer bio submission/completion over real hardware, not a RAM-backed reply or a Dell NBD disk. Identify ran only as established setup, not new capacity discovery.

All five core stability checks and five additional RAM-only samples at 50 ms intervals observed unchanged completed buffers. Exact Delete SQ/CQ passed. Normal shutdown returned 0/CSTS 9 after 940 polls; disable returned 0/CSTS 0 and BME-off passed. Whole-pilot rc-3 and legacy post-disable qualification0 remain expected quarantine: no independent DMA drain is proved. All DMA, snapshots, CPU targets and original power/reset/table owners remain retained, and the module stays pinned. Only the temporary software disk/bios/major were removed after the client joined. No forced unload, same-boot retry, Write, filesystem or persistence followed.

Postflight confirmed one retained S3E module, one bridge attempt, no n71nand/NVMe block node, block-only mode enabled and the standalone single/series modes disabled. Power remained Good/Charging at reported 52%, 32.1 C, cell 4.014 V and +176 mA, with VBUS 5.100–5.125 V. The external charger and authenticated WiFi control coexisted with the bounded storage trial.

This accepts the temporary private kernel path and its four fixed requests. It does not provide a generally openable/mountable disk, arbitrary-LBA service, ring wrap, descriptor/data-buffer reuse, long-duration/error recovery or independent DMA retirement. The current held epoch cannot be recycled for another test. Next qualify explicit broader request/lifetime and ring policy before exposing read-only userspace access.

[Sanitized physical acceptance](N71_S8000_RO_BLOCK_BRIDGE_ACCEPTANCE_2026_11_25.json).
