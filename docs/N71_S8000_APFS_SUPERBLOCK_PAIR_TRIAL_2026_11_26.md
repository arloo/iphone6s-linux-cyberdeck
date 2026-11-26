# N71/S8000 APFS block-zero superblock pair candidate — 26 November 2026

## Starting evidence and named question

The complete primary GPT was physically accepted at `015c7495d8f1f3bd34ae7eb2f626802e947d9544`: live native4KiB header, all128 entries/full16KiB array CRC, one used APFS-type partition and valid ranges/overlaps. The next two native sectors were selected inside that partition using owner-private coordinates. This candidate asks whether the first sector is a valid APFS container block-zero superblock. It does not repeat capacity, first-Read or GPT milestones. At preparation it was built/host-tested and privately packaged; it has now passed its single fresh-epoch [physical trial](N71_S8000_APFS_SUPERBLOCK_SUCCESS_2026_11_26.md).

## Reuse the bounded four-Read transport

The exact-kernel ordinary module uses the existing explicit pair mode and exactly four trusted bios/preads at relative0,1,0,1 inside the selected partition. It has four fresh tags/CIDs/SQ/CQ slots, independent DMA data/SGL frames, retained CPU snapshots/targets, exact command/CQE/data/12KiB guard/stability witnesses and both full-sector repeated-pair comparisons. There is no fifth-Read full-GPT mode, general block opener, partition scan, request stream, ring wrap, buffer reuse, NAND Write, mount or persistence.

The host binds the module pair base and helper `--apfs FIRST LAST` arguments to the complete-GPT private selection. FIRST/LAST are strictly parsed native-LBA decimal bounds, including two in-partition sectors and the accepted64GB namespace. Malformed, signed, overflowing or reversed/out-of-namespace bounds fail without probing a device. All existing helper modes remain available; the new parser runs only after four successful copies and both pair comparisons. No failed/short Read is retried.

The current full-GPT owner remains held and cannot be replaced in this epoch. A fresh attended RAM boot is required. The owner-selected launcher verifies the expected old boot/direct USB and exact closed/held storage/native binaries, then normally restores/removes only the native charger before the owner performs physical DFU. It neither unloads/resets/releases S3E nor initiates the new storage trial. An unexpected current epoch is preserved.

## CPU-only APFS validation

The original portable observer reads the fixed wire layout described by Apple's [APFS Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf), obj_phys_t/nx_superblock_t/block-zero checkpoint discussion. The mathematical checksum check follows the primary libfsapfs format research [object-checksum definition](https://github.com/libyal/libfsapfs/blob/main/documentation/Apple%20File%20System%20(APFS).asciidoc). No source implementation is copied.

For this named plan, require NXSB magic, block size4096, the complete object's Fletcher64 match, the known plain ephemeral NX-superblock object header (fixed OID1, nonzero transaction, correct type/subtype), single-device version2 and a plausible container extent within the privately validated GPT partition. Unsupported block sizes, Fusion/unknown incompatible features or checkpoint extent trees fail explicitly; this is not a claim that all such formats are corrupt.

Contiguous checkpoint descriptor/data ranges must fit the container, exclude block zero and not overlap. Block-zero ring next/index/length cursors are deliberately ignored, as they do not select a checkpoint for this anchor. A nonzero physical object-map reference must fit the container; absence is reported without inventing a usable object map. Spaceman/reaper ephemeral IDs and volume virtual IDs are not interpreted as block addresses. Volume-slot bounds/duplicates are checked, with only counts summarized.

The adjacent sector is a transport-repeat witness only; the parser does not claim to validate its object type, choose the latest checkpoint, walk object maps/volumes/trees, decrypt data or mount a filesystem. A successful block-zero anchor still needs checkpoint selection and later filesystem support/lifetime qualification.

## Privacy and lifetime

Only validation flags and slot counts are public-facing. Parsed container geometry/physical checkpoint/object-map references may be emitted with PRIVATE_APFS_REFS for owner-private next-read planning. The selected absolute NAND LBAs and these references stay private, including kernel pair/step logs; public acceptance must use relative sector labels. No raw sectors/checksum values/sector hashes, UUIDs, transaction/virtual/ephemeral IDs, names, keys or user file contents are emitted. Failed parses clear results; helper results/data are erased, core dumps/dumpability stay disabled and the root-only0600 no-follow/identity-checked /dev node is removed.

Every original DMA/HMB/DART/NVMMU, data/SGL/snapshot/CPU-target owner remains held through success/failure. Exact Delete SQ/CQ and normal shutdown/disable/BME-off traces are required, but do not establish independent DMA retirement. No retry, forced unload or backing release follows the attempt.

## Offline evidence and exact image

Ten new tests execute the actual parser and actual helper with mocked system calls. Fletcher64 is checked against fixed vectors and an independent weighted-word oracle on randomized objects. Coverage includes checksum/header corruption, malformed geometry/physical references, cross-range overlap/overflow, unsupported formats, ignored block-zero ring cursors, large nonphysical IDs, slot limits/duplicates, strict arguments, all failed/short-Read positions and cleanup. The complete **1,984-test suite**, HBPP, manifest/evidence and privacy audits pass. Module/static ARM64 helper builds are warning-free.

The private RAM image replaces only the inert storage module/helper and their runtime hashes. Boot prefix, DTBs, compressed kernel, every other CPIO entry and the physically activated500mA/7200s charging profile remain identical to the accepted full-GPT image. All twelve runtime hashes and gzip/CPIO roundtrip pass. No device-specific addresses are embedded in the image/public candidate. [Sanitized candidate hashes](N71_S8000_APFS_SUPERBLOCK_PAIR_CANDIDATE_2026_11_26.json).

## One fresh-epoch physical gate

Before insertion verify direct USB500mA topology, strict key-only SSH/fresh boot, N71/S8000/kernel and exact candidate/source/component/runtime hashes, completed encrypted-backup metadata and unused epoch. Storage/helper remain inert at boot. Reuse the accepted source-backed power gate: reported and RC/FCC at least15%, Remaining Charge at least150000uAh, agreement within2 points, Good health, cell3.6..<4.1V,10..<35C, eight fresh positive-current samples with nondecreasing RC and an immediate positive sample. Require fresh native500mA/7200s monitoring, VBUS4.75–5.5V and at least120 seconds of lease remaining. The native electrical/thermal/rollback guards and finite deadline are unchanged; no renewal is part of this image transition.

Run the exact private four-pread plan once. Separate transport acceptance from APFS_SUPERBLOCK_PASS. Require expected exact CQEs/data/guards/pair comparisons/user copies, independently parsed APFS flags, exact queue deletion/normal stop, interface removal and retained owners. Keep raw logs/coordinates private. A metadata failure does not relabel successfully delivered sectors as validated APFS and never authorizes a hardware retry in the held epoch.

## Physical outcome

Four actual private pair preads/user copies and all transport/guard/stability/equality checks passed. APFS_SUPERBLOCK_PASS reports NXSB/Fletcher64/object/geometry/checkpoint/physical-object-map bounds valid,100 maximum slots and seven virtual-volume references. Latest checkpoint and filesystem mount remain0. Exact Delete SQ/CQ and shutdown/disable passed; all owners stay held and no hardware retry is authorized. [Measured acceptance](N71_S8000_APFS_SUPERBLOCK_ACCEPTANCE_2026_11_26.json).
