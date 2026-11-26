# N71/S8000 bounded userspace pread qualification candidate — 26 November 2026

## What this advances

The accepted initial and final two-LBA Linux bio trials remain the hardware baseline at 24589409d06a8423fb5c41a2fad43fd5a7fa49c3. This candidate asks whether an actual local userspace program can initiate four real NAND Reads and privately receive their validated results. It does not repeat capacity discovery or claim another first physical NAND Read.

The implementation and private RAM image are built and host-tested. At the initial preparation checkpoint no candidate boot, module insertion or userspace NAND pread had been attempted. The phone was in iOS charging from its initial 21% reserve. iOS telemetry says charging/external connected; ExternalChargeCapable=false is also recorded, so no unsupported source-capability conclusion is drawn from those flags alone.

## Explicit interface and ownership

The new default-off ans_ro_probe_once=1 requires the existing explicit block-only mode and flags32 with accepted Identify/Create/Delete setup. The initial or final fixed pair is selected by the existing tail option. A root/CAP_SYS_RAWIO-only character interface named n71nand_probe admits one read-only opener and four exact 4096-byte reads at the fixed pair positions. The Linux block gendisk still denies every userspace open and partition scan. This is a bounded character probe, not a generally usable block disk or filesystem.

The character read handler checks size, absolute offset, step, active/failed state and the fixed pair before signaling a request. Concurrent reads fail without mutation. It never performs MMIO, submits a hardware command or exposes DMA memory. The existing kernel client waits for that request, submits its preallocated trusted bio and checks the CPU target guard. Exact hardware CQE, independent data, guard, snapshot and stability validation still precede bio completion. Only then can the read handler copy that step's retained CPU-only target into the caller's local memory. Before the final reply, both complete same-LBA pairs must match.

Malformed requests do not consume hardware slots. Any wait/copy/client failure terminates acceptance without a same-boot retry or owner release. The kernel client requires all four userspace copies before reporting success. Closing admission wakes the waiting client before join and temporary software-bio/disk release. Character registration is removed, but an already entered read may finish copying a retained CPU target: targets and static probe state are never freed, and the callback never references the software bios. Late calls through an existing descriptor fail the closed gate. This lifetime does not prove device DMA drain or authorize buffer reuse.

There are no Write, discard, flush, mmap or passthrough operations in the character interface. Existing direct block opens remain denied. Normal stop and BME-off retain all DMA/HMB/DART/NVMMU, snapshot, target and original power/reset owners, as in the accepted baseline.

## Local helper and payload privacy

The ARM64 static n71-nand-private-probe helper accepts only --initial or --tail. It waits at most 30 seconds for the explicitly registered major, creates one root-owned 0600 character node in RAM, verifies its type/major/minor/ownership, and first checks that write opens, malformed lengths and out-of-sequence reads are refused. It then executes four pread calls with no retry after a failed or short Read, compares the two full-sector pairs and reports counts/equality only. Bytes and sector hashes are never printed, transferred to the Dell or written to a file. Core dumps and process dumpability are disabled; buffers are explicitly erased and the volatile node removed on normal completion/failure.

This uses real namespace reads in the future physical trial; no RAM-backed reply or host disk substitutes for NAND. The standard character open/pread and module references were checked against the exact installed kernel's fs/open.c, fs/char_dev.c, include/linux/module.h and kernel/module/main.c.

## Offline verification

The exact ARM64 kernel module and static helper compile without warnings. Six new tests exercise the real portable admission predicate, actual kernel character handlers under host kernel stubs, and actual helper code with mocked system calls. Cases include initial/final offsets, exhaustion, malformed/foreign sizes and offsets, write/open budget refusal, concurrent-read refusal, timeout, reply error, failed copy, copy completing across interface closure, retained target lifetime, short/failed helper reads with no retry, pair corruption, unsafe nodes and cleanup. These are host tests, not physical I/O evidence. The complete 1,943-test suite, HBPP audit and manifest/evidence checks pass.

The private image changes the inert S3E module and runtime manifest and adds the helper. Bootloader/bootargs, both DTBs, compressed kernel and all other CPIO records remain identical to the accepted tail-pair image. All eleven runtime hashes and gzip/CPIO roundtrip pass. Neither storage nor helper starts automatically; the finite guarded charger profile is unchanged. Firmware, SSH/radio secrets, private binaries and hardware logs remain outside Git.

## Physical trial gate and acceptance

Use one fresh owner-attended RAM boot only after adequate reserve is recovered in iOS. Before insertion, authenticate the direct USB/SSH boot, exact image/module/helper/source, board/kernel, finished encrypted-backup metadata and unused S3E epoch. Require reported reserve and RC/FCC at least 50% with agreement, Good health, safe cell voltage, fresh qualified native VBUS/input/finite lease and thermal margin below the owner's 38 C ceiling. A gauge percentage alone cannot authorize storage.

Launch the one bounded helper over authenticated control, then insert the exact module once with ans_ro_probe_once=1 and the matching initial/tail selection. Its 30-second registration wait and the kernel's eight-second per-request waits are finite; lack of readiness must fail closed. Capture only fixed summaries and private logs. Require four exact hardware Reads, four bio completions and client_rc0, four successful private preads with pair equality, and RO_PROBE_ONCE rc0/requested4/copied4/char_removed1. Exact queue Delete and conservative controller stop/quarantine must also pass. No surviving disk or character registration, retry, forced unload, Write, mount or persistent installation is accepted.

General read-only block service, arbitrary requests, ring wrap/reuse, long-duration/error recovery and independent DMA retirement remain separate work. This candidate has not physically passed those boundaries or its own userspace pread boundary.

## Fresh boot follow-up

The exact candidate has now booted and passed strict direct USB/SSH, board/kernel and all binary/runtime checks. At only 30% reserve the storage gate remains closed; no S3E insertion or userspace NAND pread has occurred. A separately qualified finite charge-only recovery is active with all native/owner guards retained. [Physical boot and power gate](N71_S8000_USERSPACE_PROBE_BOOT_POWER_GATE_2026_11_26.md). The final preparation-only wording above does not supersede this later boot result or qualify userspace I/O.

## Bounded probe reserve revision — before the physical attempt

The initial 50% floor was an operator-selected conservative reserve target, not a NAND controller requirement. The owner explicitly requested proceeding at the current 37% while charging. Fresh observation shows 37% reported, Remaining/Full Charge454000/1245000 uAh (36.47%), Good health, +303mA, 33.1C, cell4.018V and a fresh healthy500mA native lease with more than 40 minutes remaining. S3E and the userspace probe remain unused.

For this sole four-pread qualification, reported and RC/FCC reserve may be at least35% with disagreement at most two percentage points. Require eight fresh positively charging samples plus an immediate positive sample, Good health, temperature10 to below35C, cell3.6 to below4.1V, qualified VBUS4.75 to5.5V and at least120 seconds left in the unchanged finite native/owner lease. VBUS is close to the existing floor; the floor is not lowered and any failed sample stops admission. Exact source/image/module/helper, strict USB identity, completed encrypted-backup metadata and unused-epoch gates remain mandatory. The four-read budget, all write restrictions, timeout/error handling and DMA retention are unchanged.

This revises only the reserve admission criterion for the named bounded probe. It does not authorize general disk use, repeated attempts, a longer workload, charger renewal or any relaxed electrical/thermal guard. No hardware or charger-register change implements this revision; the tested binaries remain byte-identical. The following physical result, if any, must record actual reserve and this protocol revision separately from the original50% target.
