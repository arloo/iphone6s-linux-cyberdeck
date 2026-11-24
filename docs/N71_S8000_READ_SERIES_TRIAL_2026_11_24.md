# N71/S8000 fixed four-Read repeatability trial — 2026-11-24

## Scope

The first physical 4096-byte LBA0 Read is already accepted. This new default-off candidate tests a different question: two LBAs read twice through distinct descriptors and buffers, with private byte-for-byte comparison and checks for changes in earlier completed buffers.

The exact ARM64-built and host-tested candidate has now **physically passed one fresh-boot four-Read sequence**, including both private same-LBA bytewise equalities and the bounded buffer observation. The physical result below supersedes the pre-boot preparation status. It does not register a block device or expose arbitrary LBA/length controls, a write opcode, a filesystem or raw payload/hash export.

| Fixed index | LBA | FlatDMA tag | I/O CID/head | Fresh SQ/CQ slot | Bytes |
|---|---|---|---|---|---|
|0 |0 |1 |1 |0 |4096 |
|1 |1 |2 |2 |1 |4096 |
|2 |0 |3 |3 |2 |4096 |
|3 |1 |4 |4 |3 |4096 |

These are four single-sector NVM Read commands, 16 KiB total, not one multi-sector command. The 16-entry I/O ring does not wrap; no command/CQ slot, tag, data buffer or SGL is reused.

## Explicit mode and pre-epoch ownership

ans_read_series_once=1 and ans_read_series_flags=32 require the accepted Identify/queue setup and Delete SQ/CQ opt-in, with queue flags 0. The single-LBA0 mode is mutually exclusive and stays disabled, with its separate flag unselected. Invalid combinations fail before board or PMGR work.

Before BME, eight new independent 16 KiB DMA frames hold four data/SGL pairs. Four additional unmapped CPU-only 16 KiB frames hold snapshots. All 12 frames are validated against inherited and existing owned resources before zeroing; direct DMA mapping, 36-bit reachability and distinct physical identities are required. Snapshot frames are never DMA mapped or referenced by a device descriptor.

The shadow TCB/SGL stage validates all four zero preimages and all frame exclusions before mutation. It prepares only tags 1..4. Tag 0 and every other TCB slot remain byte-identical; each page count is published last. The already qualified pre-BME NVMMU invalidation retains its precise roots/SART/HMB/CC/BME/epoch checks and permits only 0/busy-bit16 during that phase. No live root replacement occurs.

Every allocation is retained through the boot, including on partial allocation/staging failure. Only CPU-only staging shadows are freed. No DMA mapping/page or original GPIO/power/table owner is retired or reused.

## Four sequential commands and independent data evidence

Each command uses fixed NVM opcode 2, NSID 1, NLB0 and the accepted flags 32 profile on I/O QID 1. The whole 64-byte command must match the fixed step before copying. Only the corresponding fresh SQ/CQ slots may be touched, and a monotonic issued count is latched before each doorbell. At most one Read is outstanding.

The exact phase/status 0001, observed/copy consistency, CID 1..4, SQID 1 and expected head are checked before acknowledgement. CQ and data progress remain separate: every 512-word sector witness must change with its 12 KiB guard intact before the data is copied into that step's private CPU snapshot. No second command follows any completion, data or ownership failure.

After each completed command, the current and all earlier DMA data frames are reread and compared with their immutable snapshots; guards are checked again. Later snapshots 0/2 must match byte-for-byte for LBA0, and snapshots 1/3 for LBA1. Equality is reported only as booleans; no bytes, hashes or witness seeds leave the module.

Delete SQ/CQ is permitted only after all four Reads, snapshots, private equalities and stability checks pass. Controller shutdown/disable/BME-off and whole-pilot quarantine remain separate evidence.

## Retained RAM observation

After the existing admin/controller core returns, five RAM-only checks at 50 ms intervals compare completed frames with their snapshots again. The observer issues no hardware command, root/reset write, memory release or retry. It latches any detected change.

Unchanged samples establish only the observed bounded window (roughly 200 ms). They **never** establish DMA quiescence or permission to free/reuse backing. Repeated long-duration reads, ring wrap, descriptor reuse, error recovery and a usable read-only block interface remain unqualified.

## Acceptance and validation

Acceptance requires all four exact I/O completions and guarded data arrivals, four private snapshots, equality for both same-LBA pairs, unchanged prior buffers and unchanged retained-window samples. Validated Delete SQ/CQ and successful normal shutdown/disable/BME-off must be recorded separately. Partial successes must not be flattened into a full-series PASS.

The exact-kernel ARM64 build completes without warnings. All **1,928** host tests pass, followed by the synthetic HBPP audit and evidence validator. The new native-C tests exercise the fixed wire plan and bit mutations, all 16-bit status values for four steps, ordered callback failures, pair mismatch and late-buffer change, tag staging atomicity, physical overlap/exclusions and dirty preimages. Source checks cover mode gating, DMA-vs-CPU-only allocations, count-last publication, validation-before-ack, completed series before Delete, privacy and a command-free retained observer.

The private RAM candidate contains the module inert. Only its module entry and runtime hash manifest differ from the physically accepted first-Read image. All other rootfs bytes, charger, bootloader, bootargs, both DTBs and compressed kernel remain identical. Complete hashes and gzip/CPIO roundtrip are verified; no owner credentials or image are uploaded to Git.

The currently retained epoch cannot be reused. A fresh owner-attended RAM boot, completed encrypted-backup metadata, sufficient reserve, Good health, healthy finite 300 mA/VBUS and temperature margin below the owner's 38 C ceiling are required before the bounded physical attempt.

[Candidate metadata](N71_S8000_READ_SERIES_CANDIDATE_2026_11_24.json) and [accepted first-Read evidence](N71_S8000_LBA0_READ_ACCEPTANCE_2026_11_24.json).

## Physical acceptance: four Reads with private pair equality

One owner-attended fresh RAM boot loaded the exact candidate from source commit 9cc22c4f7b7cbfee0a788b2a3e5c358640460fc5. The verified module SHA-256 is cb3b398f4ebd1f3a9227ccf411358be67a6a63fb29582f98a5a68498386189c1; RAM image SHA-256 is 1efec7542fabc129b2aaa8c8d52be68dd332eb18c2846aac8a6c10763085c18b. Direct USB ancestry, strict pinned public-key SSH, the entire runtime hash manifest, board/kernel and completed encrypted-backup metadata passed. No storage pilot was previously loaded in that boot. The single-LBA0 mode remained off; only the fixed series was explicitly armed.

Eight fresh electrical samples showed capacity 56%, Good health, 33.0 C, cell 3.947–3.967 V and VBUS 4.875 V at the guarded 300 mA input limit. Net gauge current ranged 0 to +87 mA during these samples. Immediately before insertion the temperature was 32.9 C and the unchanged finite lease had about 3,388 seconds left. Continuous positive net current is not claimed or used as a substitute for the actual reserve/voltage/thermal/VBUS guards.

| Index | LBA | Tag | CID / head | Status | Independent data / guard |
|---|---|---|---|---|---|
| 0 | 0 | 1 | 1 / 1 | 0001 | 512/512 words changed; 12 KiB intact |
| 1 | 1 | 2 | 2 / 2 | 0001 | 512/512 words changed; 12 KiB intact |
| 2 | 0 | 3 | 3 / 3 | 0001 | 512/512 words changed; 12 KiB intact |
| 3 | 1 | 4 | 4 / 4 | 0001 | 512/512 words changed; 12 KiB intact |

All four CQEs validated before acknowledgement; every command needed two CQ polls and one data poll. The series returned rc=0 with issued=4, accepted=4, snapshots=4 and stability_checks=5. Both complete 4096-byte same-LBA comparisons passed, with all earlier completed buffers unchanged. No comparison between different LBA contents was required or inferred. The five additional RAM-only samples, 50 ms apart, also remained unchanged for all four completed buffers.

Create CQ/SQ and Delete SQ/CQ each received exact validated completions with queue flags 0. Normal shutdown returned 0 with CSTS 0x9 after 958 polls; disable returned 0/CSTS 0, and BME-off readback passed. The whole pilot intentionally retained rc=-3 because the legacy post-disable qualifier remains false and independent DMA drain is unproved. The successful module loader return does not mean memory was released: the module, DMA mappings, queues, HMB, TCB/SGL pages and original power/reset/table ownership remain pinned. No forced unload, second insertion or same-boot retry occurred.

Post-trial reserve remained 56%, Good health, 32.8 C and 3.925 V, with VBUS 4.875 V and the finite 300 mA monitor active. Gauge status/current fluctuated; sustainable charging is not established. There is no internal NVMe Linux block device. No NVM Write, filesystem mount or persistent installation took place; no raw sector bytes or sector hash were exported.

This accepts exactly the four independent single-sector transfers and observed short stability window, without ring wrap, descriptor reuse or an independent DMA fence. The first Read and capacity milestones are reused rather than repeated as discovery. Further runtime work needs a new owned epoch and explicit bounded transport/lifetime rules; the current held boot must not be recycled.

[Sanitized physical acceptance](N71_S8000_READ_SERIES_ACCEPTANCE_2026_11_24.json). The earlier candidate metadata is retained as build provenance and now links this physical outcome.
