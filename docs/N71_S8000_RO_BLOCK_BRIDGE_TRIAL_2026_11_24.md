# N71/S8000 temporary read-only Linux block bridge — 2026-11-24

## Current status and scope

The preceding physical sequence 0,1,0,1 is accepted and reused as the transport baseline. This new candidate is ARM64-built and host-tested but **has not been booted or inserted**. It tests a new integration boundary: four real Linux bios must cause the four hardware Reads and receive data only after the existing exact-CQE, independent data and guard checks. It does not serve a RAM-backed imitation of NAND or a Dell NBD disk.

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

The current successful-series boot is retained and cannot run this candidate. A fresh attended RAM boot, strict USB/SSH verification, completed encrypted-backup metadata, adequate reserve, Good health, finite guarded 300 mA input/VBUS and temperature margin below the owner's 38 C ceiling are required before the single attempt.

[Candidate metadata](N71_S8000_RO_BLOCK_BRIDGE_CANDIDATE_2026_11_24.json), [accepted underlying four-Read evidence](N71_S8000_READ_SERIES_ACCEPTANCE_2026_11_24.json) and [canonical storage ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).
