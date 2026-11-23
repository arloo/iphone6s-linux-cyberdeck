# N71/S8000 internal NAND — authoritative Git acceptance checkpoint (2026-11-23)

This page is the repository-side storage milestone ledger. **Git source, tests, the physical measurement archive and GitHub issues must agree**; no compile-time result is a physical NAND success. The owner-private original Apple kernelcache, raw NAND/user metadata and hardware identifiers stay outside Git. This checkpoint follows main commit `85c489166199ae8002d3655417f69646278d538b` and is updated with each subsequent evidence-backed change.

## Verified on real phone

- [x] N71/Samsung S8000 native RAM Linux boots; touchscreen, Wi-Fi, BLE and authenticated USB SSH work.
- [x] Internal ANS/S3E NVMe controller responds to real BAR0/PCIe and bounded admin command sequence.
- [x] **Admin Identify Namespace 1 completed on physical NAND hardware**: 15,625,000 × 4096-byte LBAs = 64,000,000,000 bytes nominal.
- [x] Controlled controller shutdown, disable and endpoint BME-off observed; previous DMA resources **still quarantined**.
- [ ] Independent proof that every outstanding DMA transaction has drained; none is currently available.
- [ ] Real I/O CQ/SQ creation and physical NVMe NVM Read of LBA0; **not yet done**.
- [ ] Read-only Linux block device or persistent NAND-backed Linux; **not yet done**.

## Implemented/verified offline on Dell; never submitted to device

- [x] Kernel-compiled, inert 64-byte `Create I/O CQ`, `Create I/O SQ`, and one-4096-byte `Read (0x02)` candidate encoders; read range validated.
- [x] Inert four-stream DART0 L2 leaves 18/19 for I/O SQ/CQ, preserving admin leaves 16/17, with atomic host-C ownership checks.
- [x] Kernel-compiled pre-BME Linux DMA allocator for **four independent 16 KiB pages** (I/O SQ, CQ, read data, read SGL); post-epoch pages remain quarantined.
- [x] Genuine original AppleS800xPCIe source/ADT verifies 128 TCB slots ×128 bytes, 8 MiB FlatDMA tag stride; tag0 0x40000000 Identify, distinct candidate tag1 0x40800000. Earlier 0x40001000 guess was unsafe (same tag0) and is rejected.
- [x] Host-C tag1 TCB/SGL staging checked without modifying tag0 or any physical DART/NVMMU mappings; **not approved for Read I/O until Apple transport is qualified**.
- [x] **Original `Read → IOVM/PRP` path source-qualified:** authentic IONVMeFamily embedded block-device handler branches to the Read builder, calls a distinct IOVM/PRP generation routine, and constructs 4 KiB-granularity PRP1/list pointers. A second source gate pins the original function-call targets and 32 instruction fingerprints, checked against the full original executable fingerprint. The original request initializer sets internal flag bit3 when its constructor x6 argument is nonzero; the Read builder **conditionally** translates that bit3 to CDW0 bit13 (command byte1 `BIT(5)`); the original phone's live I/O-path policy for setting this bit, and ANS/S8000 tag1 mapping, remain unverified. `tools/n71_s8000_original_ionvme_read_prp_gate.py` and `tests/test_n71_s8000_original_ionvme_read_prp_gate.py`.
- [x] **Original IONVMeFamily 2.1.0 `BuildCommandReadStruct` source provenance gate:** real original kernelcache prelink verified, correct `__TEXT_EXEC.__text` of 272,392 bytes extracted, complete binary fingerprint pinned, and 15 selected ARM64 instructions checked. Original request builder constructs opcode `0x02`, NSID, LBA, CDW12/CDW13 at standard offsets and has conditional request-dependent CDW0 bits 10/11. These facts do NOT establish that transport `BIT(5)` and FlatDMA tag1 are accepted for NVM Read. See `tools/n71_s8000_original_ionvme_read_source_gate.py` and `tests/test_n71_s8000_original_ionvme_read_source_gate.py`.

## Mandatory next steps (fail-closed)

1. **Original Apple I/O policy still open:** `Read` builder selection and the following 4 KiB PRP/IOVM generator are now source-qualified. Trace *the N71 request-pool initializer's x6 argument* (the source-proven input that controls internal bit3), which conditionally produces CDW0 bit13 (byte1 `BIT(5)`), and prove how the resulting PRP is translated through ANS tag1. Independently qualify S8000 I/O SQ/CQ creation, direction, ownership and completions. Do not infer unconditional `BIT(5)` from successful admin Identify or merely from the presence of the ANS2 class in the same kernelcache.
2. **Independent DMA lifetime:** identify a transaction-drain/fence mechanism or retain all mapped pages and driver ownership through the entire experimental boot. `CSTS`, CC, BME-off and DART bit31-clear **do not prove quiescence**.
3. **Owner-attended hardware preflight:** stable battery reserve preferably at least 50%, physically qualified bounded charger and temperature below the owner's maximum 38°C, healthy VBUS, fresh clean S3E epoch. Do not loosen the user's temperature ceiling or silently alter brightness.
4. **One real read-only trial:** before any physical I/O SQ/CQ or read execution, qualify all four DART streams, new owned pages, tag1 TCB/SGL and queue completions. Issue exactly one 4096-byte read for namespace1 LBA0, confirm CQ phase/CID/SQID/status and private payload ownership; **do not print raw LBA0/iOS contents**.
5. **Read-only block device:** only after safe repeated physical reads and adequate DMA lifetime evidence; disable automount. NAND writes, formatting or installing Linux on the internal media require separate explicit approval, backup and recovery plan.

## GitHub issue coordination

Issue numbers **#1–#8** currently track touch, Wi-Fi, Bluetooth, boot, Kali, UI, SSH and power. No standalone storage issue exists in the retrieved list. A request to create the storage issue through the GitHub connector on 2026-11-23 was denied with **HTTP 403 (Resource not accessible by integration)**; do not assert that an issue was created. This version-controlled ledger is the canonical storage acceptance record until an authorized GitHub issue can be opened. Link any eventual issue back to this document.

## Verification / provenance rules

Before each change: review Git `main` latest commit, worktree, this ledger, DMA audit, and related GitHub issues; compare against the phone's actual hardware state. After each change: run relevant unit tests, `make test`, exact ARM64 module build if kernel code changed, privacy audit and `git diff --check`; commit/push only grounded results. Make a clear distinction between host-only tests, original-firmware source evidence and physical iPhone results. Never upload the original Apple binaries, personal data, device IDs or secrets.

Supporting audit: [`N71_S8000_S3E_DMA_RETIREMENT_AUDIT_2026_11_20.md`](N71_S8000_S3E_DMA_RETIREMENT_AUDIT_2026_11_20.md).
