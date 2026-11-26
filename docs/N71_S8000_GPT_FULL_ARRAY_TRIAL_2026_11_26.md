# N71/S8000 complete primary GPT entry-array trial — 26 November 2026

## Question and accepted starting point

The physically accepted prefix trial at `0f85c9d152f6949b89be3c5566df841e9324ff3a` read native LBAs1,2,1,2. It validated the primary header and first32 of128 declared entries, including one used APFS-type hint, but did not read the remaining96 entries or check the16KiB array CRC. That result and all earlier capacity/Read/userspace milestones remain accepted. This candidate asks whether the entire declared array is consistent with a primary header read in the same new epoch; it does not repeat capacity discovery.

## Dedicated default-off five-Read plan

`n71_s3e_gpt_full_once.c` is a separately named translation unit using the common guarded transport with compile-time `N71_GPT_FULL_PLAN=1`. It admits only **1,2,3,4,5**: one4096-byte primary header and four4096-byte entry-array pages. The ordinary module still compiles to four Reads and retains its initial/tail/explicit-pair behavior. The fifth slot is new physical qualification, not an already accepted tag.

Even an armed full-plan module refuses before the board/PMGR gate unless `ans_ro_gpt_full_once=1`, block mode and the root-only character probe are selected, pair/tail/single/standalone-series modes are off and pair_base stays unselected. Existing flags32, NS1/native4096 geometry, Identify/Create/Delete, owned HMB/DART/NVMMU and all original source/power guards remain required. No data-dependent address, sixth request, ring wrap, reuse, background storage load, userspace block open, partition scan or NAND Write is introduced.

Five unique tags/CIDs/SQ/CQ slots own ten distinct retained DMA data/SGL frames, five retained CPU snapshots and five separate retained CPU bio targets. All selected TCB slots are zero-checked and staged atomically while preserving tag0/unused slots; publication is count-last. Every command, CQE, data arrival,12KiB target guard and earlier-buffer stability check remains exact. Both original kernel and userspace interfaces enforce the compile-time budget. All hardware backing stays held through success/failure; neither normal shutdown nor later unchanged RAM authorizes DMA release.

## Integrity and private parser

This plan deliberately reads five distinct sectors; it does not claim repeated-pair equality. After the fifth validated arrival, both the kernel snapshots and independently copied CPU bio targets must match a valid native GPT header and its complete array CRC. The last user copy is gated by the CPU-target witness. The ARM64 helper independently performs the same CRC checks and parses all128 entries. The accepted geometry is explicitly fixed to array_lba2,128 entries of128 bytes; any mismatch fails this named plan without alternate-address retries.

The parser validates every used range against the header's usable limits and rejects overlap across any entry/page. Result buffers clear on failure. Success emits only counts, standard type hints and validation flags, plus explicitly private parsed numeric coordinates for later sector selection. Raw sectors/CRC values/sector hashes, unique GUIDs, partition names, keys and user files are never exported. Core dumps/dumpability remain disabled, the node is root-only0600 in /dev with identity/no-follow checks, and private data/result buffers are erased before exit. A short/failed Read aborts without retry.

A valid complete primary array still does not validate the backup GPT, APFS superblock/checkpoints/object maps, encryption access, a general block service or filesystem mounting. No partition change, installation, format or persistent write is authorized by this trial.

## Offline evidence and RAM build

Ten additional tests execute the real five-command encoder/CQE/failure matrix, ten-frame staging/foreign-owner exclusions, five-bio request rejection and terminal budgets, actual kernel character handler copy/timeout/close failures, exhaustive explicit-mode gates and the real userspace helper/parser. GPT fixtures use independent zlib CRCs and entries on all four pages through slot128; corruption in each page (including unused bytes), cross-page overlap, bad ranges/geometry/header CRC and no-retry failures are checked. The earlier CPU observer remains pinned to the legacy four-target owner ABI and is not authorized to inspect the new module.

The exact-kernel full and legacy modules and static ARM64 helper must build without warnings. The complete1,974-test suite, HBPP audit, manifest/evidence and privacy checks must pass before handoff. The final private RAM image replaces the inert module/helper, native charger, startup script and runtime hashes, and adds the explicit hashed two-hour charging opt-in. All other CPIO entries, boot prefix, DTBs and compressed kernel remain identical. The first storage-only intermediate image was superseded before boot; its one-hour charging profile is not the current candidate. All twelve runtime hashes and gzip/CPIO roundtrip must pass. [Sanitized candidate metadata](N71_S8000_GPT_FULL_ARRAY_CANDIDATE_2026_11_26.json). Build/host validation is not a hardware acceptance claim.

## One fresh attended epoch

The previous S3E epoch is held and cannot be reused or forcibly unloaded. After a new attended RAM boot, verify direct USB topology, strict key-only SSH identity, board/kernel, exact source/image/module/helper/runtime hashes, completed encrypted-backup metadata and unused epoch. Keep storage/helper inert until that qualification completes.

Apply the named source-backed lower-reserve profile, declared before this pending attempt after the owner's instruction to continue with active charging. Both reported and RC/FCC reserve must be at least15%, Remaining Charge at least150000uAh, and agreement within2 points. Require Good health, cell3.6..<4.1V, temperature10..<35C, eight fresh positive-current samples with nondecreasing RC and an immediate positive sample. Independently attest direct USB500mA, native500mA input, VBUS4.75–5.5V, a fresh native monitor and at least120 seconds left in the finite lease. The separately qualified recovery demonstrated +292.25mA mean current at15%,33.2C with normal30s rollback; this supports a brief fixed five-Read source-backed trial, not unrestricted low-battery I/O. The earlier35% and high-reserve admission histories remain unchanged. [Exact charging/source rationale and two-hour candidate limits](N71_S8000_TWO_HOUR_CHARGE_PROFILE_2026_11_26.md).

Launch `--gpt-full` and the exact new module once. Acceptance requires five exact guarded Reads, five bios/user copies, both kernel CRC witnesses, helper GPT_FULL_PASS with checked128/array_complete1/CRC_checked1/CRC_ok1 and all-range validation. Require exact Delete SQ/CQ, normal shutdown/disable/BME-off traces, interface removal and retained owners. Keep raw evidence and coordinates private; publish only sanitized flags/counts. Any failed stage ends this epoch without retry, forced unload, backing release or mount.

## Pre-handoff physical status

No new NAND attempt or candidate boot occurred. The initial read-only17%/3.402V result correctly deferred storage after normal one-hour lease expiry. The owner then explicitly requested continuing Linux work with charging beyond one hour. A separate unchanged-native500mA/30s recovery passed, and a finite500mA build-support session now charges the old held epoch. Later measured17%, Good/Charging,+289mA,33.2C, cell3.869V and VBUS4.775V. No iOS reboot is required for this recovery. The new image's two-hour profile remains a built/tested candidate; physical activation/expiry and the full GPT array trial are pending. Every original S3E owner remains held; fresh attended RAM boot is required for the next storage attempt.

## Physical acceptance

The exact final two-hour-profile image booted and passed the single five-Read trial: header/full-array CRC checks, all128 entries, one used APFS-type partition, all ranges/overlaps and five user copies pass. Exact queue deletion/shutdown/disable and retained stability passed. This epoch remains held with no further NAND trial authorized. The charging profile is active, while physical two-hour expiry remains pending. [Measured report](N71_S8000_GPT_FULL_ARRAY_SUCCESS_2026_11_26.md) and [acceptance JSON](N71_S8000_GPT_FULL_ARRAY_ACCEPTANCE_2026_11_26.json).
