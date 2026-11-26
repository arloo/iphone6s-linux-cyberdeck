# N71/S8000 complete primary GPT array accepted — 26 November 2026

## Physical result

The exact `020f31bd1f1cd312f84fb0f72ec2f05663735fdd` private RAM candidate booted in a new owner-attended epoch. Direct USB topology/configuration500mA, strict key-only SSH, board/kernel, image/module/helper/native/startup/profile hashes and all twelve runtime hashes passed. No S3E owner, prior attempt marker or probe node was present. Completed encrypted-backup metadata was checked privately. The new SSH key was pinned only after direct USB and exact runtime identity checks.

Exactly five actual4096-byte NAND Reads completed through five trusted Linux bios and the root-only ARM64 character helper: **1,2,3,4,5**. Tags/CIDs/SQ/CQ heads1..5, QID1, status0001,512-word data arrivals and12KiB guards all passed. Five immutable snapshots and five user copies passed, with six core stability checks. Loader/helper returned0; no ring wrap, buffer reuse, alternate command or NAND Write occurred. This qualifies the new fifth tag/slot in this bounded plan.

## Complete table and precise boundary

The same-epoch primary GPT header passed native4KiB signature, header CRC and bounded namespace geometry. All four declared entry-array pages were read: **128 entries of128 bytes,16KiB total**. The complete array CRC matched the live header on the kernel snapshots, copied CPU bio targets and userspace buffers. All128 entries were examined; one is used, with the standard Apple APFS partition type. Its range is valid and all-entry/cross-page overlap checks pass. There are zero unseen declared primary entries.

This plan contains five distinct sectors. Pair-equality fields remain0 and are explicitly marked untested; integrity comes from the header/full-array CRC checks plus independent arrival/guard/snapshot lifetime witnesses. Per-device ranges remain only in private evidence and a private next-sector selection. No raw sector bytes, CRC values, sector hashes, unique GUIDs, names, keys or user files were exported or published.

**Complete primary GPT layout is accepted.** Backup GPT, APFS container superblock/checkpoints/object maps, encryption access, filesystem mounting and persistent Linux are not yet accepted. The APFS partition type alone establishes none of those filesystem properties.

## Closure and retained lifetime

All five bios/user copies completed with client_rc0 and no rejected bio. Character registration/private0600 /dev node and the temporary software disk were removed. Exact Delete SQ/CQ passed. Normal shutdown returned0 with CSTS0x9 after1835 polls; disable returned0 with CSTS0x0 and BME off. Five later RAM-only samples50ms apart stayed unchanged.

The whole pilot retains conservative rc-3; independent DMA drain/retirement remains unproven. Every original DMA/HMB/DART/NVMMU, data/SGL, snapshot and target owner stays held. Postflight confirms the same boot, one ref1 Live `n71_s3e_gpt_full_once` owner, exact full-GPT-only modes, five Read commands, the attempt marker and no surviving NAND block/probe node or character registration. No retry, forced unload, owner/backing release or filesystem operation was performed.

## Power and validation

The predeclared source-backed15%/150000uAh observer gate passed without lowering electrical/thermal guards. Eight fresh samples measured20–21% reported,19.953–20.031% RC/FCC, all positive with mean+256mA, nondecreasing RC,33.1C and VBUS4.775V; more than6957 seconds remained on the native500mA/7200s finite lease. A fresh immediate positive-current/identity sample passed before the single insertion.

Final postflight measured21%, Good/Charging,+185mA,33.2C, cell3.892V, VBUS4.775V and RC260000/FCC1283000uAh. The exact new two-hour native profile is physically active and positively charging. **Physical two-hour expiry is still untested**; no lease renewal or charging-module replacement occurred in this epoch.

The exact source/header/image hashes remain pinned to the source commit. The warning-free exact-kernel builds/static ARM64 helper,1,974 host tests, HBPP and manifest/evidence audits passed before the attempt. This checkpoint adds measured evidence/documentation, without another hardware test or code change.

[Sanitized measured acceptance](N71_S8000_GPT_FULL_ARRAY_ACCEPTANCE_2026_11_26.json), [trial/source-backed power contract](N71_S8000_GPT_FULL_ARRAY_TRIAL_2026_11_26.md), [candidate hashes](N71_S8000_GPT_FULL_ARRAY_CANDIDATE_2026_11_26.json), [charging qualification](N71_S8000_TWO_HOUR_CHARGE_PROFILE_2026_11_26.md) and [canonical storage ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).

## Next storage question

A private bounded pair has been selected inside the validated APFS partition for container-header/superblock validation. No such Read has been submitted and no next RAM image is claimed ready. It requires a fresh attended storage epoch. General request service, ring/buffer/error lifetime, independent DMA retirement and filesystem support still gate mounting and persistence.
