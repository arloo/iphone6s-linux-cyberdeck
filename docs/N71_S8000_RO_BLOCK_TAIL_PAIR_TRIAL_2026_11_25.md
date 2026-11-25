# N71/S8000 last-two-LBA Linux block qualification candidate

The preceding four Linux bios over LBA0/1 remain accepted. This candidate tests a new addressing boundary: the final two 4096-byte blocks of the Identify-derived 64,000,000,000-byte namespace. It is built, host-tested and physically accepted for this bounded tail-pair trial.

The default-off ans_ro_block_tail_once=1 requires block-only opt-in, flags32, Identify and exact queue Create/Delete setup. Single and standalone series modes remain disabled. Selection without block mode is rejected before the board/PMGR gate. The fixed sequence is **15624998,15624999,15624998,15624999**. Only base0 and base15624998 are admitted; arbitrary pair bases fail before mutation or publication. Existing base0 wrappers preserve the earlier protocol.

Command generation and exact validation, bio sector admission and each request log use the same selected base. RO_BLOCK_PAIR records the absolute base and selection. Legacy lba0_equal/lba1_equal summary names denote equality of pair positions; the per-request logs identify actual LBAs.

Four fresh tags, CIDs and SQ/CQ slots, independent DMA data/SGL pairs, CPU snapshots and trusted bio targets remain unchanged. Data and guard validation precede Linux completion. No ring wrap, data/descriptor reuse, userspace opens, partition scan, Write, mount or persistence is introduced. All hardware backing/owners remain quarantined; shutdown/BME-off is not independent DMA-drain authority.

The exact installed ARM64 kernel build is warning-free. Four new tests run the full command corruption/failure matrix and bio admission/exhaustion/rejection matrix against the tail pair, verify invalid-base atomic rejection and early mode gating. All **1,937 tests**, HBPP audit and manifest/evidence validation pass.

The private RAM image changes only the inert S3E module and its runtime manifest hash. Boot prefix, both DTBs, compressed kernel and every other CPIO entry remain identical. All ten runtime hashes and gzip/CPIO roundtrip pass. Storage does not auto-load. Charging guards are unchanged.

One fresh owner-attended boot and strict direct USB/SSH verification are required. Exact image/module/source, board/kernel, finished encrypted-backup metadata, unused epoch, consistent adequate reserve, finite healthy charger/VBUS and thermal margin must pass before one insertion. The held preceding epoch must never be reused or forcibly unloaded.

Acceptance requires four exact CQEs and independent arrivals with intact guards, unchanged earlier buffers, private same-LBA equality, four actual Linux bio completions, temporary disk removal and exact queue deletion with conservative shutdown/quarantine. No sector bytes or sector hashes are exported. Any failure ends the attempt without retry or owner release. Future acceptance qualifies two additional addresses, not full-drive reliability or a usable filesystem. Broader admission, ring lifetime/reuse, error recovery and independent DMA retirement remain open.

## Physical acceptance: last-two-LBA Linux bios

The exact c62020af8ea8026d9303ddb908c9d8bbcce75a77 candidate ran once in a fresh authenticated owner-attended boot. Source/module/image, kernel/board, direct USB host key and finished encrypted-backup metadata passed. Eight power samples showed reported52%, RC/FCC51.27–51.35%, 30.3 C, VBUS4.900 V and a healthy native finite300mA lease. Six current samples were positive and two were zero/Not charging; none discharged and RC was nondecreasing. The initial all-positive observer refused without hardware action; qualification records those zero samples rather than claiming uninterrupted net charging. The immediate pre-insertion sample was positively charging with consistent reserve and fresh native telemetry.

All four bios over LBAs15624998,15624999,15624998,15624999 completed with exact status0001, distinct tag/CID/head1..4, SQID1, two CQ polls and one data poll. Each independent512-word witness changed and its12KiB guard stayed intact. Both private same-LBA comparisons passed in snapshots and returned CPU bio targets. The bridge recorded rc0, admitted/delivered/client_completed4, client_rc0, pair_equality1 and rejected0. The temporary software disk was removed.

Five core stability checks plus five retained-RAM-only samples at50ms were unchanged. Exact Delete SQ/CQ passed. Normal shutdown returned0/CSTS9 after580 polls; disable returned0/CSTS0 and BME-off passed. Whole-pilot rc-3 intentionally retains quarantine: the legacy post-disable qualification is false and independent DMA drain remains unproved. All hardware backing and original owners remain retained. One pinned S3E module, one trial and no surviving NAND block node were confirmed; no retry, forced unload, Write, mount or persistence followed.

Postflight remained Good at52%, RC/FCC51.51%, 30.4C and cell3.892V. That gauge sample showed zero current/Not charging while the fresh native monitor continued VBUS4.875–4.900V at300mA. The source was present; the instantaneous gauge is not reported as positive charging. This extends the initial-LBA physical proof to the final two namespace addresses, not to every intervening LBA or a generally usable disk.

[Sanitized physical acceptance](N71_S8000_RO_BLOCK_TAIL_PAIR_ACCEPTANCE_2026_11_25.json).
