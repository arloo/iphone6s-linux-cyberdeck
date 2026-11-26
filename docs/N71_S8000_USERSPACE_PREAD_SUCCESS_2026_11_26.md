# N71/S8000: bounded local userspace NAND preads accepted — 26 November 2026

The corrected candidate at 4247848b7cb2e871dffe887d3c8191c39d486e4a has physically passed in one fresh authenticated owner-attended epoch. The local ARM64 helper opened its root-only 0600 character node in /dev, triggered four real NAND Reads through the accepted trusted Linux bio path, privately received all four validated 4096-byte sectors and compared both complete same-LBA pairs. Helper rc0 and PRIVATE_PREAD_PASS completed4/pair_equality1 are confirmed. This is a new userspace initiation/copy boundary over the prior kernel-path acceptance, not a repeated first NAND Read or capacity discovery.

## Exact request and data proof

| Index | LBA | Tag / CID / SQ head | CQ status | Result |
|---|---|---|---|---|
| 0 | 0 | 1 / 1 / 1 | 0001 | Validated bio and private pread completed |
| 1 | 1 | 2 / 2 / 2 | 0001 | Validated bio and private pread completed |
| 2 | 0 | 3 / 3 / 3 | 0001 | Full-sector pair matched |
| 3 | 1 | 4 / 4 / 4 | 0001 | Full-sector pair matched |

Every CQE had the exact SQID1/phase/CID/head and was acknowledged only after validation. Each independent512-word data witness arrived with its12KiB guard intact, using two CQ polls and one data poll. The bridge recorded admitted4/delivered4/client_completed4/client_rc0/private_pair_equality1/rejected0. The character interface recorded requested4/copied4/rc0/char_removed1. The helper's write-open, malformed-size and out-of-sequence checks ran without consuming hardware slots. No raw bytes or sector hashes were printed, transferred to the Dell or saved to a payload file; local user buffers were compared and erased.

Five core stability checks and five additional retained-RAM-only samples at50ms intervals observed unchanged completed buffers. Exact Delete SQ/CQ passed. Normal shutdown returned0/CSTS9 after937 polls; disable returned0/CSTS0 and BME-off passed. Whole-pilot rc-3 still preserves quarantine because independent DMA drain is unproved and the legacy post-disable qualifier remains false. The temporary disk, character registration and private node were removed; all DMA/HMB/DART/NVMMU, snapshots, targets and original power/reset owners remain retained with the S3E module pinned. There was no forced unload or same-boot retry.

## Identity, power and reserve

Exact source/image/module/helper, all eleven runtime hashes, board/kernel, direct USB ancestry/route, strictly pinned key-only SSH, finished encrypted-backup metadata and unused epoch passed. The original conservative50% target had been explicitly revised for this named four-pread trial before its attempt; it was not bypassed during execution. Reported reserve40–41% agreed with RC/FCC40.080–40.161%. All eight fresh samples positively charged at+227 to+316mA, 33.2–33.3C, cell3.965–3.999V and native VBUS4.750–4.775V on a finite500mA input lease. The automatic300mA profile had first been observed with zero-current samples; its healthy baseline restoration was verified before the previously qualified500mA profile was applied. No electrical, thermal or charger source limit was raised beyond the accepted profile.

Postflight remained Good/Charging at41%, Remaining/Full Charge510000/1245000uAh, +197mA, 33.3C, cell3.986V and fresh native VBUS4.775V. One S3E module/trial was held, with no NAND block node, character registration or private probe node. The finite charger still has no automatic renewal and stops on its owner/native bounds, consistent55% target or one-hour deadline. This does not claim a permanent charger driver.

## Scope and next boundary

The accepted interface is an explicitly armed, single-open, four-pread character probe over the initial pair, not a generally openable Linux block disk. No filesystem mount, arbitrary request service, ring wrap, descriptor/data-buffer reuse, long-duration/error recovery, independent DMA retirement, NAND Write or persistent Linux is established. Prior final-LBA reads remain separate kernel-only evidence. The current held epoch cannot serve further Reads. Broader request admission and queue/buffer lifetime/error handling must be qualified before general read-only service and any filesystem work.

The earlier nodev failure is retained as a separate failed epoch. Its negative controller-stop trace is not replaced by this later success. [Sanitized acceptance](N71_S8000_USERSPACE_PREAD_ACCEPTANCE_2026_11_26.json), [preceding failure/correction](N71_S8000_USERSPACE_PROBE_NODEV_FAILURE_2026_11_26.md) and [original contract/reserve revision](N71_S8000_USERSPACE_PREAD_PROBE_TRIAL_2026_11_26.md).
