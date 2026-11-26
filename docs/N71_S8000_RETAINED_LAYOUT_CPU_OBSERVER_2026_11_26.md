# N71 retained CPU-target layout observer — 26 November 2026

## Purpose and boundary

The accepted four local userspace preads at 313dff8b6103a56485adba52ece15bda4b7069f1 left four distinct CPU-only bio targets retained in the pinned storage owner. This diagnostic asks what structural hints those already returned LBA0/LBA1 copies contain. It does not issue another NAND Read or create a DMA epoch, and never calls the owner's hardware routines. The held owner and every existing mapping/table/power/reset claim stay retained.

The standalone GPL observer is default-off. Its caller must attest the exact live owner SHA256 `7a28e2b600356213a765ea7f93d1b66f034e1f94110c08e60bed92acdf240dcc`, exact kernel/build/source ABI, same accepted boot, successful initial-pair userspace mode and live symbol addresses. Addresses come from owner-qualified kallsyms and independently cross-checked ELF/sysfs section offsets, not guesses, and remain private. The boolean attestation parameter records that caller precondition; the observer does not cryptographically hash its owner from inside the kernel.

The observer checks RAM page backing before no-fault metadata copies, the expected module name/LIVE state and that both the module header and owner object lie inside the copied MOD_DATA extent. It retains one additional ordinary module reference, including on subsequent failures. This reference count change is intentional; target data, the owner's closed block state, device registers and all DMA owners are never written or released.

The owner field declaration is mirrored exactly from the pinned source, checked by a source regression and compiled against the same kernel configuration. Compile-time assertions require the ELF object's 176-byte size, target-array offset48 and 16KiB host pages. The live object must show a completely closed, successful four-bio flow: no disk/bios/pending bio/client/major remain, all four client completions and pair equalities passed, and every CPU target is a distinct aligned valid non-reserved non-slab ordinary RAM page. No arbitrary structure layout is inferred from a different kernel.

Four complete target frames are privately copied twice, 50ms apart. Both owner-state copies, each full frame, both same-LBA pairs and every12KiB target guard must remain unchanged/valid before classification. These CPU targets were never DMA-mapped or placed in a TCB/SGL by the accepted owner. The diagnostic allocates only its own unmapped CPU scratch, erases its scratch before freeing it, and does not free any owner allocation. An unchanged CPU witness is not proof of independent device DMA drain.

## Classification, not mounting

The portable parser examines only its private 4KiB copies. It reports MBR/protective-MBR flags; GPT primary signature, CRC and bounded primary-header geometry in the native 4KiB view and a separately labeled embedded 512-byte candidate view; APFS NXSB/APSB signature hints at the documented object-header offset; and all-zero/all-FF/cross-LBA difference flags. It never logs raw bytes, CRC/hash values, disk or partition UUIDs, names, keys or user contents.

A valid embedded 512-byte-view header does not change the Identify-derived native 4096-byte NVMe LBA or qualify a 512-byte I/O interface. Both candidate views are reported separately. A GPT primary-header result does not validate its partition entry array or backup header, which are not present in these copies. APFS signatures alone do not validate a container, checksum, volume, encryption state or mountability. Missing signatures do not prove encryption or damage. A format result cannot authorize disk opening, Write, partition changes, mounting, a new Read, ring reuse or DMA release.

GPT field/CRC rules were checked against the installed kernel's block/partitions/efi.h and efi.c. APFS signature locations are based on Apple's [File System Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf), Objects and Container/Volumes definitions. Only signature hints are implemented for APFS.

## Offline validation and execution protocol

The exact ARM64 module build is warning-free. Seven new tests cover the actual portable parser with an independent zlib CRC oracle, every primary-header bit corruption, malformed sizes/geometry with recomputed CRCs, overflow-safe owner ranges, input immutability, unknown/zero/FF blocks, signature-only APFS hints, exact owner field mirroring and prohibited hardware/export operations. The full 1,951-test suite plus HBPP and manifest/evidence checks are required before invocation. These tests do not constitute a physical layout result.

Before one explicit invocation, the owner control path must verify strict same-boot direct USB/SSH identity, exact deployed module/helper/source, closed successful trial evidence, unchanged initial-pair parameters, private symbol/section address agreement, and ordinary power/health telemetry. Transfer only the diagnostic module into RAM, verify its hash and invoke it with the validated private addresses. Record before/after owner state, held reference count and unchanged NAND command/trial counts. No S3E retry, forced unload, DMA mapping/release, controller reset or owner cleanup is permitted. The observer remains inert afterward; a module reference intentionally remains with the held owner.

At preparation this observer has not been invoked on the phone. Its physical flags, if obtained, must be appended separately, with the retained-data provenance and unchanged hardware command count stated explicitly.
