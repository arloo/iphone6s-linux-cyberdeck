# N71/S8000 retained APFS descriptor CPU-only observation — 26 November 2026

## Named observation

The APFS anchor and adjacent native4KiB sector were already delivered and retained by the four-Read pair trial accepted at57440dbbecbdea9f4b010bedea93b6f818252558. Owner-private geometry confirms that the adjacent sector is the first block in the anchor descriptor area. The retained pair does not cover the full descriptor area. This observer issues no new NAND Read or NVMe command and cannot choose the latest checkpoint.

## Exact owner and CPU admission

The new module is inert by default and pinned to the accepted owner binary SHA614de1abd5f733dccdb549a6923c308d51bcca763068d7e2f5d0c6df5252d6de, exact running kernel and four-target176-byte ABI (target array offset48). Before insertion the host must verify the unchanged boot and exact local/runtime hashes. Both owner symbols must be derived from this ELF's sections/offsets and independently agree with nonzero live module kallsyms. Addresses and partition geometry stay private. Wrong symbols, sizes, boot, owner refcount/state or artifact identity stop without insertion.

The module validates module-RAM backing before nofault metadata copies, Live owner identity and containing data ranges. It acquires one ordinary owner reference and retains it on all subsequent paths. Closed complete four-bio state, absent disk/client/bios and four distinct aligned normal-RAM targets are required. It copies all four16KiB CPU targets twice50ms apart, compares complete frames and owner state, checks both repeated4KiB pairs and all12KiB guards, then parses only its own copies. Only those temporary copies are wiped/freed. Original buffers, DMA mappings and the owner are never modified, called, released or reset.

## Bounded metadata classifier

The original MIT portable classifier uses the fixed wire facts in Apple's [APFS Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf): object header, checkpoint_map_phys_t, checkpoint_mapping_t and container checkpoint rings. No source implementation is copied. It revalidates the accepted anchor and uses complete-object Fletcher64, descriptor-area membership, known physical checkpoint-map or ephemeral NXSB headers and bounded structures. A candidate NXSB also needs the same container UUID, valid geometry and valid descriptor/data cursors. A map needs known flags, bounded count, bounded nonempty mapped physical extents and ephemeral object types. Mapping size is rounded up to blocks; padding is preserved/ignored, and virtual/ephemeral IDs are not addresses. Membership in the anchor data area is a separate observation because a stale anchor cannot establish the selected checkpoint layout.

Zero/FF, unknown, stale or checksum-invalid sectors are reportable observations rather than accepted descriptors. A valid shape is only one locally consistent descriptor. No complete checkpoint transaction, referenced object, latest selection, volume readability, decryption or filesystem mount is accepted by this observer.

## Verification and execution boundary

Eight synthetic CPU tests cover valid maps/NXSBs, independent checksum stamping, corrupted checksums/headers, overflow/out-of-range mappings, large nonphysical IDs, nonzero padding, UUID/ring faults and wrapped ring membership against an independent enumerated model. They also check exact owner ABI, guarded default-off CPU-only source and identifier-free result schema. All1992 host tests and the warning-free exact-kernel ARM64 module build pass. [Candidate hashes](N71_S8000_RETAINED_APFS_CHECKPOINT_CANDIDATE_2026_11_26.json).

The attended, unchanged held epoch permits at most one such observer insertion. Save the command/manifest privately before loading; keep the observer and extra owner reference retained. Immediately save sanitized flags and postflight identity, interface absence, held reference count and charging telemetry. Full hardware logs and coordinates remain private. No S3E reload or hardware retry follows any result. At the source checkpoint physical acceptance was pending; the subsequent single CPU-only observation passed, as recorded below.

## Physical outcome

The exact observer passed full retained CPU copies/guards/owner-state checks without a new NAND Read. The first descriptor is a valid physical checkpoint map with eight bounded ephemeral mappings, LAST set and a transaction newer than the initial anchor. The held owner reference count becomes2. Corresponding checkpoint superblock/data and complete/latest checkpoint selection remain open. [Measured result](N71_S8000_RETAINED_APFS_CHECKPOINT_SUCCESS_2026_11_26.md).
