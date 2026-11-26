# N71 userspace probe: nodev failure and corrected candidate — 26 November 2026

## Physical result: failed before the first NVM Read

The bounded reserve revision was applied before insertion, rather than treating the original conservative 50% target as a hardware requirement. Eight fresh samples passed at reported 37–38%, RC/FCC 36.948–37.028%, +250 to +321 mA, 33.1 C, cell 3.997–4.022 V and native VBUS 4.750 V. Exact image/module/helper/source, strict direct USB/SSH, unused epoch and finished encrypted-backup metadata passed. No electrical, thermal, native-lease or four-request guard was lowered.

One insertion registered the temporary disk and character probe. Identify completed with arrived data and exact Create SQ/CQ passed. The helper returned1/PRIVATE_CHAR_OPEN_FAILED. The kernel client timed out before any trusted bio: issued0, accepted0, admitted0, delivered0, client_completed0, requested0 and copied0. Both temporary software interfaces were removed. This is **not accepted userspace NAND I/O**, nor another first NAND Read.

The helper had created its 0600 character node under /run, but the actual phone mounts /run as tmpfs with nodev. That location was an implementation mistake: nodev prevents opening the character special file. The root shell has CAP_SYS_RAWIO. A separate diagnostic created temporary aliases of /dev/null (major1/minor3) under /run and /dev; the former was denied and the latter opened. Both aliases were removed. No NAND device was touched by that diagnostic, and /run mount protections remain unchanged.

## Failure cleanup and retained epoch

The error path did not attempt Delete SQ/CQ. Normal shutdown returned -2 with CSTS7, disable returned -1/CSTS7, and BME-off was observed. Therefore controller stop and independent DMA drain are **not proved**. Whole-pilot rc-3 retains all DMA/HMB/DART/NVMMU, snapshots, targets and original power/reset owners. The S3E module stays pinned; there was no forced unload, second insertion, Write, payload export, mount or persistence. Postflight showed one held S3E module, no NAND block node or probe registration/node, Good health, 38%, +250 mA and 32.9 C while guarded charging continued.

The setup failure and the negative shutdown trace must not be presented as a successful storage trial. Retry requires a fresh attended RAM epoch. The failure-path controller-stop behavior remains unqualified; this patch only fixes the proven access-path issue.

## Corrected, not physically booted candidate

The helper now uses /dev/n71nand-probe on devtmpfs, preserving its root-only 0600 node, no-follow open, type/major/minor/UID checks, private buffers, no retry, and cleanup. Open failures now report errno separately from identity-check failures. The storage module is byte-identical; request admission, hardware command code, ownership and charging thresholds are unchanged.

The corrected ARM64 helper compiles without warnings. All 1,944 host tests pass, including a new device-filesystem path regression plus the existing real helper/kernel-handler error tests. The /dev null-alias diagnostic qualifies node opening on this phone only; it does not qualify the corrected NAND probe. The private RAM image changes only the helper and its runtime hash. Kernel, both DTBs, boot prefix, storage module and every other CPIO entry remain identical. All eleven runtime hashes and gzip/CPIO roundtrip pass. Neither storage nor helper auto-starts.

For the next sole four-pread trial, use the bounded reserve revision (at least35% reported and RC/FCC with agreement and fresh positive electrical samples), strict identity/backup checks, Good health and unchanged native/owner thermal, cell, VBUS and remaining-lease bounds. Do not reuse the currently held epoch. General disk access, arbitrary I/O, ring reuse, DMA retirement, mounting and persistence remain open.

[Sanitized failure record](N71_S8000_USERSPACE_PROBE_NODEV_FAILURE_2026_11_26.json), [corrected image metadata](N71_S8000_USERSPACE_PROBE_DEVNODE_CANDIDATE_2026_11_26.json), [original probe contract and reserve revision](N71_S8000_USERSPACE_PREAD_PROBE_TRIAL_2026_11_26.md).
