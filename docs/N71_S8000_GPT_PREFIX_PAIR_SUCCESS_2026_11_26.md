# N71/S8000 physical GPT entry-prefix acceptance — 26 November 2026

## Observed result

The exact private RAM candidate built from source `306284da0670ac9c299689e91fc496a9f73967f4` booted in a new owner-attended epoch. Direct USB topology, strict key-only SSH, board/kernel, exact image/module/helper and all eleven runtime hashes passed. Storage and helper remained inert until the single explicit attempt; completed encrypted-backup metadata was checked privately. This is a new layout-sector result, not a repeated Identify/capacity milestone.

Exactly four real 4096-byte NAND Reads completed through the guarded Linux bios and local ARM64 userspace helper: **1,2,1,2**, with independent tags/CIDs/heads1..4, QID1 and exact status0001. All CQE identity checks, 512-word data arrivals, 12 KiB per-target guards, five core stability checks, private full-sector pair equalities and four user copies passed. Loader and helper returned0; there was no ring wrap, target reuse or NAND Write.

## What the metadata establishes

The freshly read native4KiB GPT header passed signature, CRC and bounded geometry validation. It declares128 entries of128 bytes beginning at LBA2: a16KiB entry array spanning four native pages. The returned first page contains the first32 entries. One of those visible entries is used and matches the standard Apple APFS partition-type GUID. Its ordered range lies within the header's usable bounds; visible overlap checks pass.

The helper saved that entry's parsed numeric coordinates only in private device/host evidence. No raw sectors, raw CRC values, sector hashes, disk/partition unique GUIDs, names, keys or user files were exported or published. Public evidence contains only counts, standard type hints and validation flags.

**Only the first32 of128 entries are qualified.** The remaining96 entries, complete entry-array CRC and backup GPT were not read or accepted. The explicit parser result is array_complete0/array_crc_checked0/array_crc_ok0; this means unchecked, not a measured CRC mismatch. The APFS type hint does not establish a valid container superblock, readable/decrypted volume, filesystem support or mountability.

## Closure and retained ownership

All four bios and user copies completed with client_rc0 and no rejected bio. The character registration, private0600 /dev node and temporary software block disk were removed. Exact Delete SQ/CQ completed. Normal shutdown returned0 with CSTS0x9 after1822 polls; disable returned0 with CSTS0x0; BME was off. Five later RAM samples at50ms intervals remained unchanged.

The whole pilot still returns conservative rc-3. Independent DMA drain/retirement is unproven, so every original DMA/HMB/DART/NVMMU, snapshot and target owner remains retained. Postflight confirms the same boot, one held Live S3E owner, the expected pair-only parameters, four Read commands total, the attempt marker and no remaining NAND block/probe node or character registration. There was no same-epoch retry, forced unload, backing release, mount or persistent write.

## Power admission and measured reserve

Before the attempt, commit `3fe80d4e7426850e44169e8fa01b098c52e54848` documented the backed high-reserve window. Eight new samples qualified at55% reported and54.779% RC/FCC, on the unchanged finite native300mA lease. Six were positive, one zero and one -8mA; mean net current was +44.75mA and Remaining Charge did not decrease. The immediate sample was -10mA, within the documented -100mA instantaneous bound. These are not described as continuously positive charging.

Health stayed Good, temperature33.4C, cell3.970–3.987V and VBUS4.875–4.900V. The input current was not increased, the lease was not renewed and all original electrical/thermal/source and remaining-lease guards stayed in force. Final postflight measured55%, RC684000/FCC1245000uAh, Good/Charging, +52mA,33.4C, cell3.970V and VBUS4.900V.

## Validation and next boundary

The source/header hashes still match the prepared candidate; the exact image hash was rechecked. The full1,960 host tests and warning-free exact-kernel module/static ARM64 helper builds had passed before this physical attempt. This acceptance update changes documentation only. It does not promote host tests into hardware evidence.

The next layout question is the complete declared entry array, including its actual CRC, without repeating the already accepted capacity/initial/tail/user-copy milestones. A later explicitly bounded fresh-epoch plan must account for the remaining pages and preserve the no-reuse/held-owner constraints. Filesystem metadata inspection follows validated sector selection. Continuous block service, queue lifetime/error recovery, independent DMA retirement and filesystem support still gate mounting and persistent Linux.

[Sanitized measured acceptance](N71_S8000_GPT_PREFIX_PAIR_ACCEPTANCE_2026_11_26.json), [trial contract and power revision](N71_S8000_GPT_PREFIX_PAIR_TRIAL_2026_11_26.md), [exact private-image metadata](N71_S8000_GPT_PREFIX_PAIR_CANDIDATE_2026_11_26.json), [earlier userspace proof](N71_S8000_USERSPACE_PREAD_SUCCESS_2026_11_26.md) and [canonical storage ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).
