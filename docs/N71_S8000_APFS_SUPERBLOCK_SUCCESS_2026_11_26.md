# N71/S8000 APFS container block-zero superblock accepted — 26 November 2026

## Physical result

The exact `105a3f20e7a0f877aac5977923a5baefcba19a0c` private RAM candidate booted in a fresh owner-attended epoch. Direct USB topology/configuration500mA, strict key-only SSH, N71/S8000/kernel, exact component hashes and all twelve runtime hashes passed. No S3E owner/attempt marker/probe was present. Source/image hashes and completed encrypted-backup metadata were checked privately. The new SSH key was pinned only after direct USB/exact-runtime verification.

The private range selection was bound to the complete primary GPT accepted at015c7495d8f1f3bd34ae7eb2f626802e947d9544. Exactly four4096-byte actual NAND Reads completed at partition-relative **0,1,0,1**, through four trusted Linux bios and the local ARM64 character helper. Absolute NAND coordinates remain private. All exact tags/CIDs/heads1..4, QID1/status0001,512-word independent arrivals,12KiB guards, five core stability checks, both full-sector repeated-pair comparisons and four user copies passed. Loader/helper returned0; there was no ring wrap, buffer reuse or NAND Write.

## What the APFS metadata establishes

The first sector is a valid4096-byte **NXSB container block-zero superblock**: the complete object's Fletcher64 checksum, known plain ephemeral object header, single-device v2 representation and container extent within the selected GPT partition all pass. Contiguous checkpoint descriptor/data ranges fit without overlap. A nonzero physical object-map reference is within the container.

The anchor has capacity for100 volume slots and contains **seven nonzero virtual-volume references**. Their objects have not been read or mapped; no seven-volume readability/mount claim is made. Virtual/ephemeral IDs were not misinterpreted as physical addresses. The block-zero checkpoint ring cursors are deliberately ignored, as specified for this anchor.

Parsed container/checkpoint/object-map physical geometry was saved only in private evidence for the next selection. No raw sectors/checksum values/sector hashes, UUIDs, transaction/virtual/ephemeral IDs, names, keys or user file contents were exported or published. Public evidence uses validation flags/counts and relative sector labels.

This accepts the initial container anchor. **Latest-checkpoint selection, descriptor-area scan, referenced object-map/volume/tree contents, encryption access, filesystem mounting and persistence remain unqualified.** The adjacent sector remains retained as already-read data, but this parser did not interpret it. Where useful it can be examined through a separately qualified CPU-only observation before a new hardware epoch; the descriptor area is not fully covered by this trial.

## Closure and retained lifetime

All four bios/user copies completed with client_rc0 and zero rejected bio. Character registration/private0600 /dev node and the temporary software disk were removed. Exact Delete SQ/CQ passed. Normal shutdown returned0 with CSTS0x9 after550 polls; disable returned0 with CSTS0x0 and BME off. Five later RAM samples50ms apart stayed unchanged.

The whole pilot retains conservative rc-3. Independent DMA drain/retirement is unproven, so every original DMA/HMB/DART/NVMMU, data/SGL/snapshot/CPU-target owner stays held. Postflight confirms the same boot, one ref1 Live ordinary S3E owner, exact private-pair-only modes, four Read commands, the attempt marker and no surviving NAND block/probe node or character registration. There was no same-epoch retry, forced owner unload, backing release or filesystem operation.

## Power and validation

The predeclared source-backed15%/150000uAh gate passed. Eight fresh samples measured29–30% reported and29.072–29.150% RC/FCC, all positive with mean+276.5mA,33.6C and VBUS4.750–4.775V, with more than7104 seconds left on the native500mA/7200s finite lease. An immediate positive-current/identity sample passed before insertion.

Final postflight was31%, Good/Charging,+241mA,33.6C, cell3.915V, VBUS4.775V and RC387000/FCC1283000uAh. Native guards/deadline are unchanged and no renewal or native-module replacement occurred in this epoch. Physical two-hour expiry remains untested.

The source/header/image hashes remain pinned to the source commit. Warning-free exact-kernel/static ARM64 builds, the complete1,984-test suite, strengthened focused helper-output/privacy checks, HBPP and manifest/evidence audits passed before the attempt. This checkpoint adds measured evidence/documentation without code changes or another hardware test.

[Sanitized measured acceptance](N71_S8000_APFS_SUPERBLOCK_ACCEPTANCE_2026_11_26.json), [trial and source-backed gate](N71_S8000_APFS_SUPERBLOCK_PAIR_TRIAL_2026_11_26.md), [candidate hashes](N71_S8000_APFS_SUPERBLOCK_PAIR_CANDIDATE_2026_11_26.json), [complete primary GPT proof](N71_S8000_GPT_FULL_ARRAY_SUCCESS_2026_11_26.md) and [canonical ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).
