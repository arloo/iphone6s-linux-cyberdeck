# N71/S8000 last-two-LBA Linux block qualification candidate

The preceding four Linux bios over LBA0/1 remain accepted. This candidate tests a new addressing boundary: the final two 4096-byte blocks of the Identify-derived 64,000,000,000-byte namespace. It is built and host-tested, not physically accepted.

The default-off ans_ro_block_tail_once=1 requires block-only opt-in, flags32, Identify and exact queue Create/Delete setup. Single and standalone series modes remain disabled. Selection without block mode is rejected before the board/PMGR gate. The fixed sequence is **15624998,15624999,15624998,15624999**. Only base0 and base15624998 are admitted; arbitrary pair bases fail before mutation or publication. Existing base0 wrappers preserve the earlier protocol.

Command generation and exact validation, bio sector admission and each request log use the same selected base. RO_BLOCK_PAIR records the absolute base and selection. Legacy lba0_equal/lba1_equal summary names denote equality of pair positions; the per-request logs identify actual LBAs.

Four fresh tags, CIDs and SQ/CQ slots, independent DMA data/SGL pairs, CPU snapshots and trusted bio targets remain unchanged. Data and guard validation precede Linux completion. No ring wrap, data/descriptor reuse, userspace opens, partition scan, Write, mount or persistence is introduced. All hardware backing/owners remain quarantined; shutdown/BME-off is not independent DMA-drain authority.

The exact installed ARM64 kernel build is warning-free. Four new tests run the full command corruption/failure matrix and bio admission/exhaustion/rejection matrix against the tail pair, verify invalid-base atomic rejection and early mode gating. All **1,937 tests**, HBPP audit and manifest/evidence validation pass.

The private RAM image changes only the inert S3E module and its runtime manifest hash. Boot prefix, both DTBs, compressed kernel and every other CPIO entry remain identical. All ten runtime hashes and gzip/CPIO roundtrip pass. Storage does not auto-load. Charging guards are unchanged.

One fresh owner-attended boot and strict direct USB/SSH verification are required. Exact image/module/source, board/kernel, finished encrypted-backup metadata, unused epoch, consistent adequate reserve, finite healthy charger/VBUS and thermal margin must pass before one insertion. The held preceding epoch must never be reused or forcibly unloaded.

Acceptance requires four exact CQEs and independent arrivals with intact guards, unchanged earlier buffers, private same-LBA equality, four actual Linux bio completions, temporary disk removal and exact queue deletion with conservative shutdown/quarantine. No sector bytes or sector hashes are exported. Any failure ends the attempt without retry or owner release. Future acceptance qualifies two additional addresses, not full-drive reliability or a usable filesystem. Broader admission, ring lifetime/reuse, error recovery and independent DMA retirement remain open.
