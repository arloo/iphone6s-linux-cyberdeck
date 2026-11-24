# N71/S8000 first physical 4 KiB NVM Read — 2026-11-24

## Accepted result

The real iPhone 6s N71/Samsung S8000 completed exactly one NVM Read of namespace 1, LBA0, one 4096-byte logical block. The I/O queue 1 completion validated phase/status 0001, CID 1, SQID 1 and SQ head 1. Independently, all 512 sector word witnesses changed and all 12 KiB of the surrounding owned-frame guard remained intact. No raw sector bytes, sector hash or witness seed were exported.

This is **namespace block-data access**, extending the already accepted admin Identify/64 GB metadata result. It is not another capacity milestone, the earlier Dell-backed NBD image, or host-only simulation.

Source commit: c1cc52efcf6ceca87a83e45da7657142c1b539fd. Tested module SHA-256: 7b8c8bbee6d64f6d051918ab431b4c048c9d7e7fbc805e2a3e6a4af203cdbef4. The exact prepared RAM payload and module/runtime hashes were verified over authenticated, strictly pinned direct-USB SSH in a fresh, S3E-clean boot. Completed encrypted iOS backup metadata and eight fresh electrical samples were checked before the one insertion.

## Physical sequence

| Stage | Observed result |
|---|---|
| Owned I/O queues and tag 1 preparation | Published before BME with CC/CSTS off; tag 0 unchanged |
| Identify setup | Valid current 64 GB/4 KiB namespace metadata |
| Create CQ / SQ | Both exact Admin completions valid, CID 2/3 |
| NVM Read | Opcode 2, NSID 1, SLBA0, NLB0, I/O QID 1, CID 1, flags 32, disjoint FlatDMA tag 1 |
| Read CQE | Status 0001; exact CID/SQID/head validated; CQ head acknowledgement issued |
| Independent data arrival | 512/512 64-bit sector witnesses changed; 12 KiB guard intact; one data poll |
| Delete SQ / CQ | Both exact Admin completions valid, CID 4/5, after completed Read/data |
| Normal shutdown | rc 0, CSTS 0x9 after 1495 polls |
| Controller disable | rc 0, CSTS 0 after 2 polls |
| Bus mastering | Both PCI functions readback-verified off |
| Resource lifetime | Every I/O/admin/HMB/DART/NVMMU allocation and original owner remains retained |

The accepted command summary was:

    LBA0_READ_ONCE rc=0 submitted=1 cqe_seen=1 cqe_valid=1 cq_acked=1 data_arrived=1 guard_ok=1 changed_words=512 expected_words=512 status=0001 cq_polls=2 data_polls=1 nsid=1 slba=0 blocks=1 bytes=4096 io_qid=1 command_flags=32 tag=1

The raw device log remains owner-private. The whole-pilot rc=-3 does not negate the independently accepted Read, data transfer or successful controller stop. It reflects unchanged quarantine/legacy post-disable qualification; shutdown or a completion does not independently authorize freeing DMA backing.

## Transport interpretation

Queue commands used the physically accepted direct-DART flag 0. The Read used separately selected flag 32 and tag 1, following the successful Identify's device-to-host FlatDMA convention. The current original-source gate establishes the 8 MiB tag stride and isolated 128-byte descriptor; the new physical result qualifies this **specific Linux Read configuration** for one sector.

It does not record the original live iOS dynamic provider, predicate or request-pool flag policy. Those source investigations must not be silently marked complete. Neither are the raw vendor FIFO/DART status words treated as transaction-drain proof.

## Power, limits and continuation

The preflight remained at 56% and 32.3 C with Good health and configured USB. Cell voltage was 3.898–3.954 V; VBUS 4.875–4.900 V; the existing finite 300 mA input lease remained healthy with its kernel safeguards unchanged. Mean net current over the sampled window was +30.125 mA, with short negative samples. This is bounded trial power evidence, not a permanent net-charging guarantee.

Exactly one Read and one controller lifecycle are accepted. No NVM Write, Linux block device, filesystem mount or persistent Linux installation occurred. Repeated reads, additional LBAs, longer transfers, error recovery, independent DMA retirement and an operator-usable read-only block interface remain separate work.

Reuse this first-access evidence. A later LBA0 read must answer an explicit repeatability or transport question; do not rerun a standalone Identify or claim this milestone again. Do not force-unload the held driver or retry in the current boot.

The next qualification is bounded repeatable reads and read-only block transport before filesystem access. NAND writes, partition changes, formatting and internal installation remain outside this read-only result.

[Sanitized machine-readable acceptance](N71_S8000_LBA0_READ_ACCEPTANCE_2026_11_24.json) and [implemented trial and its guards](N71_S8000_LBA0_READ_TRIAL_2026_11_24.md).
