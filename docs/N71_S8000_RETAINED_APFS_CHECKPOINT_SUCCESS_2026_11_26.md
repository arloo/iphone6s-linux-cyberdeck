# N71/S8000 first retained APFS checkpoint map validated — 26 November 2026

## Measured CPU-only result

Sourcec862b1f3734e5eab0cddd4a2bfb9bc8e61fe6ec6 ran once against the already accepted APFS pair epoch. Exact direct USB500mA topology, strict key-only SSH, unchanged boot/kernel, all twelve runtime hashes, exact owner SHA/176-byte ABI and independently agreeing ELF section/offset plus live symbol addresses passed. The module was built warning-free for the exact ARM64 kernel after all1992 host tests passed.

Both50ms-separated CPU copies of all four retained16KiB targets agree. Both repeated4KiB sector pairs, every12KiB guard and the complete closed owner state are unchanged. No new NAND Read, NVMe command, owner-buffer write or MMIO access was issued. The original four-Read count remains four. Loader and observer returned0.

The already-retained adjacent sector is a valid **physical APFS checkpoint-map descriptor**, inside the anchor descriptor area. Its complete4KiB Fletcher64, physical object header, mapping flags/count/extent bounds and ephemeral mapping types pass. It contains **eight mappings**, all bounded within the container and the anchor checkpoint-data area. The CHECKPOINT_MAP_LAST flag is set. Its nonzero transaction is **newer than the block-zero anchor**; the numeric IDs and physical coordinates stay private.

The NXSB-only UUID/geometry/ring fields are not applicable to this map; their zero result flags are not failed checks. Virtual/ephemeral IDs and preserved padding were not mistaken for physical addresses. No raw sectors/checksum values/sector hashes, UUIDs, identifiers, names, keys or file contents were exported.

## What is still open

The corresponding checkpoint superblock and mapped data objects have not been read or matched to this map's transaction. LAST ends a map sequence; it does not establish a complete checkpoint or newest-checkpoint selection. The full descriptor area is not covered by the retained pair. Latest-checkpoint selection, object-map/volume traversal, encryption access, general block service, filesystem mounting and persistence remain unqualified.

The next NAND plan must answer the missing checkpoint-descriptor/transaction question in a fresh attended epoch, bound to the private GPT/container geometry. Reading a descriptor again is justified only where necessary to jointly validate a checkpoint transaction, not to rediscover this accepted map or repeat capacity/GPT. No next hardware image is declared ready by this CPU observation.

## Lifetime and power

The observer acquired one ordinary owner reference and retained it. The original S3E owner stays Live with refcount2 (previously1); its buffers/mappings/backing remain held. No disk/probe node or character registration survives. There was no owner call, reset, forced unload, DMA unmap/free, hardware retry or NAND Write. Independent DMA drain is still unproven.

Preflight was44%, Good/Charging,+278mA,33.8C and cell3.988V. The immediate postload sample briefly reported Discharging/-191mA; a subsequent six-sample window was consistently Good/Charging at44%,+132..226mA (mean+179.33mA),33.9C and native VBUS4.775V/input500mA. Native500mA/7200s guards and deadline were unchanged; no charger renewal/replacement occurred. The physical full two-hour expiry remains untested.

[Sanitized measured observation](N71_S8000_RETAINED_APFS_CHECKPOINT_OBSERVATION_2026_11_26.json), [source/build/CPU-only contract](N71_S8000_RETAINED_APFS_CHECKPOINT_TRIAL_2026_11_26.md), [exact candidate](N71_S8000_RETAINED_APFS_CHECKPOINT_CANDIDATE_2026_11_26.json), [initial APFS anchor acceptance](N71_S8000_APFS_SUPERBLOCK_SUCCESS_2026_11_26.md) and [canonical storage ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).
