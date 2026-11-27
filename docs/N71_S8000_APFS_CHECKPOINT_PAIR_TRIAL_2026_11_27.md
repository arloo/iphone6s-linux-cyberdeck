# N71/S8000 adjacent APFS checkpoint descriptors — 27 November 2026

## Named question and reused evidence

APFS anchor acceptance `57440dbbecbdea9f4b010bedea93b6f818252558` and retained-map acceptance `4230476925c01d88d50b65ad996c378c3d5185aa` establish the initial NXSB plus a checksummed physical checkpoint map with eight bounded ephemeral mappings, LAST set and a transaction newer than block zero. Capacity, complete primary GPT and the previous map are accepted evidence. The corresponding checkpoint superblock has not been read.

This candidate asks whether the map and immediately following descriptor form one internally consistent, two-slot checkpoint descriptor group with the same transaction. The private selection uses the previously validated GPT/container geometry. Partition-relative **1,2,1,2** is a bounded hypothesis, not a claim that the unread sector must be NXSB. Re-reading the map in a fresh epoch is needed to compare its transaction and current contents jointly with the superblock after iOS has run; it is not a repeated discovery milestone.

## Transport and private RAM image

The S3E owner module is byte-identical to the physically accepted four-Read APFS transport, SHA256 `614de1abd5f733dccdb549a6923c308d51bcca763068d7e2f5d0c6df5252d6de`. It retains four unique tags/CIDs/SQ/CQ slots and independent guarded DMA data/SGL frames, snapshots and CPU bio targets. The explicit private pair base changes at runtime; no new request stream, ring/buffer reuse, general opener, auto-probe or NAND Write is added. The helper performs four actual 4,096-byte preads and both full repeated-pair comparisons. Failed/short Reads stop without retry.

The new verified RAM image replaces only usr/bin/n71-nand-private-probe and its entry in usr/lib/cyberdeck/n71-runtime.sha256. Every other CPIO entry, complete boot prefix, both DTBs, compressed kernel, storage module, firmware/provisioning and accepted native 500 mA / 7,200 s charger/startup/profile remain byte-identical. All twelve runtime hashes and gzip/CPIO roundtrip pass. Storage/helper remain inert at boot. [Sanitized candidate](N71_S8000_APFS_CHECKPOINT_PAIR_CANDIDATE_2026_11_27.json).

## Descriptor validation and limits

The original MIT parser implements fixed wire facts described in Apple's [APFS Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf), container/checkpoint mapping and ring sections; no implementation is copied. The second sector must independently pass NXSB magic, full Fletcher64, known ephemeral object header, supported 4,096-byte single-device-v2 geometry and bounded container/contiguous checkpoint areas. The first must pass the corresponding physical map header, complete checksum, known flags/count and bounded ephemeral mappings. The object transactions must match, LAST must be set and the NXSB descriptor window must consist exactly of the observed ordered map/NXSB pair. Other descriptor-group shapes are unsupported by this finite plan, not automatically corrupt.

All mapping extents must fit the candidate's active data-ring window, including wrapped windows, with no duplicate (volume, ephemeral-object) keys or physical overlap. Container spaceman and any nonzero reaper reference must resolve to correctly typed root-scoped map entries. Large virtual/ephemeral IDs remain identifiers rather than block addresses; preserved padding is ignored. Only flags/counts are public. Parsed physical container/object-map/spaceman/reaper references may be saved with PRIVATE_CHECKPOINT_REFS strictly for owner-private next-read planning. UUIDs, numeric object/transaction IDs, names, keys, raw sectors/checksums/sector hashes and actual NAND coordinates are not emitted publicly.

Success accepts a locally consistent descriptor pair. It does **not** compare the new candidate UUID with the earlier block-zero UUID, scan all descriptor slots, establish newest-checkpoint selection, read/check the mapped data objects, walk object maps/volumes, decrypt data or mount/install a filesystem. No complete-checkpoint or filesystem acceptance follows merely from this pair.

## Host/build evidence

Twelve new tests execute the actual portable parser and helper with independent checksum stamping and mocked system calls. Coverage includes matching/mismatched transactions, corrupt headers/checksums, unsupported geometry/groups, cursor/LAST faults, active data windows/wrap, independent set-model ring enumeration, mapping overlap/duplicate keys, required container links, large nonphysical IDs, preserved padding, malformed/overflowing CLI coordinates, all failed/short-Read positions, cleanup and output privacy. All **2,004 host tests**, manifest/evidence validation and HBPP/privacy checks pass. The static AArch64 helper builds warning-free. Existing kernel transport is reused exactly; no replacement kernel module build is substituted for its accepted binary.

## Attended boot and physical gate

The launcher verifies image size/hash and refuses an already-running Linux epoch. Its private guard verifies the intended N71/S8000 iOS device and existing encrypted/finished backup metadata, active iOS charging and at least 15% reported capacity. A same-port DFU/Pongo continuation needs a candidate-bound successful iOS proof no older than 15 minutes. The established attended Pongo wrapper and temporary fwupd isolation/restore are preserved. The owner performs the physical DFU step; the launcher only loads RAM and never inserts S3E or starts the helper.

After boot verify direct USB 500 mA topology, strict pinned key-only SSH, fresh N71/S8000/kernel identity, exact candidate/runtime/component hashes and unused epoch. Independently reapply the accepted NAND power gate: reported and RC/FCC at least 15%, Remaining Charge at least 150,000 uAh, agreement within 2 points, Good health, cell 3.6..<4.1 V, 10..<35 C, eight fresh positive-current samples/nondecreasing RC and an immediate positive sample; fresh guarded native 500 mA / 7,200 s monitoring, VBUS 4.75–5.5 V and at least 120 seconds of remaining finite lease. The iOS launcher check does not replace this Linux measurement window. No new 50% condition or charger renewal is introduced.

Bind module pair base and helper --checkpoint FIRST LAST RELATIVE_MAP to the private plan. Save exact commands/identity/power privately before the one insertion. Separate four-Read transport/pair/bio/user-copy acceptance from APFS_CHECKPOINT_PAIR_PASS. Save raw logs privately, require normal queue deletion/shutdown/disable/BME-off and interface removal, retain all original owners/backing and later RAM stability witnesses. Independent DMA retirement remains unproven. No retry, forced unload, DMA release, mount or persistence follows any result.

## Current state

Built, host-tested, packaged and ready for an owner-attended fresh RAM boot. No new boot, NAND command, descriptor-pair physical acceptance, latest selection or mount has occurred during preparation. The phone remained in iOS charging while this candidate was prepared.
