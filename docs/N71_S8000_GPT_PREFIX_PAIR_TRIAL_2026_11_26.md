# N71/S8000 GPT-entry prefix and bounded pair candidate — 26 November 2026

## Starting evidence and named question

The preceding accepted local userspace preads established the guarded kernel-to-user path. A separate CPU-only observation then validated the native4KiB primary GPT header and protective MBR from those retained copies, without another NAND Read. This candidate asks what the first GPT entry-array page contains, so the actual partition/type and later filesystem-sector selection can be based on parsed metadata. Preparation originally stopped at ARM64 build/host tests. It has now passed a single fresh-epoch physical prefix trial; see [measured acceptance](N71_S8000_GPT_PREFIX_PAIR_SUCCESS_2026_11_26.md). The complete entry array remains unverified.

## Explicit bounded pair admission

New default-off ans_ro_block_pair_once=1 requires block mode and an explicit ans_ro_block_pair_base in0..15624998. The default base is unselected (~0U); selecting a base without its mode, omitting the base, selecting tail and pair simultaneously or leaving the accepted namespace is refused before board/PMGR access. Existing initial/tail defaults remain bound to their original pairs. The portable command, command validation, trusted bio admission, user offsets and runtime logging share the same selected base.

For this specific trial use base1, giving exactly **1,2,1,2**: the primary GPT header and first possible entry-array page, both reread. The namespace remains NS1 with15,625,0004096-byte LBAs. All four tags/CIDs/SQ/CQ slots, independent data/SGL/snapshot/CPU-target frames, exact completion/data/guard/stability checks, four-read budget, no ring wrap/reuse and conservative retained-owner stop are unchanged. This broadens address selection; it does not create continuous request service or authorize arbitrary user processes to open a block disk.

The original single and standalone-series modes stay off. Explicit block flags32, accepted Identify/Create/Delete setup and ans_ro_probe_once=1 are still required. The helper is invoked with --layout, which binds the same base1. Neither storage nor helper starts automatically. Do not insert this candidate into the current held epoch.

## Parser and privacy boundary

After four successful private preads and both full-sector pair comparisons, the helper validates the live LBA1 GPT signature, CRC and bounded namespace/header geometry. It requires table_lba2 and128-byte entries before interpreting the returned LBA2 page. A header declaring a different table location fails this named parser rather than treating an unrelated page as a partition table.

At most the first32 entries are examined. Nonempty entries must have ordered start/end within the validated usable range; overlaps among the visible entries fail atomically. Standard APFS partition-type GUID matching follows Apple's [File System Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf), Partition UUIDs. An APFS type is only a hint for a later superblock read, not proof of a valid/decrypted/mountable APFS volume.

If the declared entire array fits the returned4096-byte page, its actual declared byte length is checked against the header's array CRC. If it spans more pages, the helper reports array_complete0/array_crc_checked0/array_crc_ok0. Prefix range checks do not validate unseen entries, whole-array CRC, the backup GPT or a filesystem. No mount should be inferred from a successful prefix result.

--layout emits parsed entry counts, type hints and owner-private numeric partition coordinates for planning the next sector reads. Those per-device coordinates stay in private evidence, not public Git reports. It does not emit raw sectors, CRC values, sector hashes, unique disk/partition GUIDs, partition names, keys or user file contents. The existing core-dump/dumpability guard, root-only0600 /dev node, no-follow/type/major/minor/UID checks, no retry after short/failed Reads, buffer erasure and volatile-node cleanup remain intact. --pair BASE separately supports the same bounded pair without metadata parsing; --initial and --tail remain available.

## Offline validation and RAM image

Nine new host tests exercise the actual portable command corruption/fault matrix at several non-endpoint bases including a65535/65536 carry, actual bio admission/exhaustion/rejection, exhaustive mode combinations, real helper argument parsing and mocked-system-call execution of real --layout helper/parser, independent zlib array/header CRCs, complete versus partial arrays, APFS type classification, corrupted CRC, bad ranges/overlap and failed-parser output atomicity. Existing namespace-bound tests were updated to reject only unsafe consecutive-pair bases, while legacy wrappers remain tested. The full 1,960-test suite plus HBPP and manifest/evidence audits pass.

The exact installed ARM64 kernel module and static helper compile without warnings. The private RAM image replaces only those two inert components and their runtime hashes. Boot prefix, both DTBs, compressed kernel, charger profile and all other CPIO entries stay identical. All eleven runtime hashes and gzip/CPIO roundtrip pass. No candidate boot, new I/O epoch, partition Read or filesystem operation is claimed at preparation.

## One fresh-epoch physical trial

Use a fresh owner-attended RAM boot. Verify strict direct USB/key-only SSH, board/kernel, exact source/image/module/helper and headers, completed encrypted-backup metadata and unused epoch. The named bounded reserve protocol allows reported and RC/FCC at least35% with agreement; require eight fresh positive-current samples and an immediate positive sample, Good health, safe cell/thermal margins and a physically qualified native input/VBUS/finite lease with at least120 seconds left. No electrical, thermal or source-current guard is relaxed.

Launch the helper and insert the module once with the explicit base1 plan. Require four exact guarded Reads and Linux bios, user copied4 and returned-pair equality, followed by a separately parsed GPT_PREFIX_PASS. Record whether array CRC was actually checked and whether only a prefix was available. Capture any parsed coordinates privately, with only anonymized counts/types/range-validation status published. Require exact Delete SQ/CQ and conservative shutdown/quarantine, no surviving probe/disk, no retry or forced owner unload. Every DMA/HMB/DART/NVMMU, snapshot, target and original owner remains retained; no Write, partition change, mount or persistence is authorized by this result.

[Private-image sanitized metadata](N71_S8000_GPT_PREFIX_PAIR_CANDIDATE_2026_11_26.json) and [accepted retained GPT header flags](N71_S8000_RETAINED_GPT_HEADER_OBSERVATION_2026_11_26.json). General block service, long-duration/error recovery, ring/buffer lifetime and independent DMA retirement remain open before filesystem access.

## High-reserve power-window qualification — before the attempt

The exact candidate boot is authenticated and unused. Reported55% agrees with RC/FCC54.54%; the native finite300mA lease remains healthy with VBUS4.875–4.900V, 33.7C and safe cell voltage. Eight samples contain five positive net-current values and three small negatives (-11 to -17mA), averaging +48.625mA, with Remaining Charge unchanged at679000uAh. The initial all-positive observer refused without any hardware storage action. Those negative samples are retained in evidence and are not described as uninterrupted positive charging.

For this short four-read attempt with both reported and counter reserve at least50%, qualification may use a net-positive eight-sample window with nondecreasing Remaining Charge, instantaneous net draw no worse than -100mA, and the unchanged fresh native VBUS/input, health, cell, thermal and remaining-lease guards. A fresh immediate sample is still required. Below50%, the previously documented35% bounded path still requires the positive-current samples. This changes only the observer's reserve/current admission rule; it neither changes the module/helper/image nor increases input current, changes electrical/thermal bounds, renews the lease, expands the request budget or authorizes a retry. The battery reserve backs the brief bounded load while the current-limited source remains physically present.

## Physical outcome

The exact candidate was booted and attempted once after the documented high-reserve power revision. All four userspace Reads and prefix parsing passed:128 declared entries,32 examined, one used/APFS-type hint, array_complete0 and array_crc_checked0. Shutdown/disable passed, all owners remain held and this epoch cannot be retried. [Physical result and limits](N71_S8000_GPT_PREFIX_PAIR_SUCCESS_2026_11_26.md).
