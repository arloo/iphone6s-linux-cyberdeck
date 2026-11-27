# N71/S8000 physical first SQ/CQ wrap accepted — 27 November 2026

One fresh owner-attended RAM boot ran exactly seventeen Reads once. All CQEs, guarded data arrivals, Linux bios and private user copies pass. Both 16-entry queues wrap once; command 17 has the expected phase-zero completion. This accepts bounded serial queue progression over a known adjacent pair. Complete descriptor scanning, newest-checkpoint selection and filesystem mounting remain open.

## Provenance and admission

Runtime source `e615632558f22786c51e7404b2bc2f714c856e7c`; launcher correction `76c043d66f92e2c37b83d9301795617592cb8fe5`. Image SHA256 `d30c5a590e3356268efc782c86d53dc35d72c84934ca167db269628885bc0866`, 28329264 bytes; module SHA256 `10aa3a7425c4b5b8fb5a05f89b32d160143cb070c8d3dd8e14c2ee55a7fc204d`; helper SHA256 `69e0cbcdcd227c1f7a9451aec516a748aa174927ccbb4ab586a4d0604b4acf3e`. Exact-kernel ARM64 module and static helper builds are warning-free. Image preparation passed 2,019 tests; the host-only launcher correction passed all 2,025 tests. [Predeclared protocol](N71_S8000_CQ_WRAP_TRIAL_2026_11_27.md), [candidate](N71_S8000_CQ_WRAP_CANDIDATE_2026_11_27.json), [sanitized measurements](N71_S8000_CQ_WRAP_ACCEPTANCE_2026_11_27.json).

The owner's already-entered-DFU launch initially stopped before upload. Its separate recent transition witness used real prior power data, exact owner N71/S8000 identity and USB chronology on the same port; it did not invent native charger rollback. The corrected launch acknowledges the exact RAM upload. Two identical direct-cable Ed25519 samples were privately enrolled, followed by strict key-only SSH. A fresh boot, exact board/kernel, configured direct USB 500 mA topology, all twelve runtime hashes, five component hashes, source/image hashes and an unused epoch passed. No old four-target owner ABI or observer was used.

## Power before NAND

The unchanged startup native 500 mA profile stopped on its battery-voltage guard at 4.259 V and restored input 00/rc0. Its phase=battery/VBUS0 log does not establish a measured USB-voltage drop. The inactive native module was normally removed. No rearm occurred during the NAND trial.

The named `cq-wrap-17` reserve gate passed eight fresh samples, then another fresh window immediately before insertion and an independent immediate sample. The earlier qualifying window spans 14.99 s, minimum 84%/1,082,000 uAh, minimum 83.231% RC/FCC, at most 31.7 C and 3.995–4.036 V. It holds twelve planning windows. All final and immediate measurements independently pass the declared gauge, timing, Good-health, USB, 3.6..<4.1 V, 10..<35 C, 1,000,000 uAh and current limits. The model is 1 A for 300 s, rounded to 83,334 uAh, with at least ten reserve windows. This is admission planning, not measured endurance. Exact checks precede atomic host/guest attempt markers and one finit_module syscall.

## Physical witnesses

| Witness | Result |
|---|---|
| Reads / exact CQEs / snapshots | 17 / 17 / 17 |
| Data and guard per Read | 512 changed 64-bit words; intact 12 KiB guard |
| Tags/CIDs | Seventeen distinct; no data-buffer reuse |
| SQ / CQ wraps | Exactly 1 / 1 |
| Slot-zero reuse | Full old CQ image and 64-byte SQ command validated |
| Command 16 | Phase 1, SQ head 0 |
| Command 17 | Status 0, phase 0, CID 17, SQID 1, SQ head 1 |
| Pair comparisons | Every repeated sector matches its initial parity sector |
| Core stability / bios / private user copies | 18 / 17 / 17 |
| Delete SQ then CQ | Both exact completions, rc0 |
| Normal shutdown | rc0, CSTS9, 1,801 polls |
| Disable / BME-off | rc0, CSTS0 / observed |
| Later retained RAM | Five samples 50 ms apart, all seventeen Reads unchanged |

Helper and loader return zero. RAM character/block interfaces are removed. Original ownership stays `n71_s3e_cq_wrap_once`, ref1/Live, with every DMA/SGL/snapshot/target/HMB/DART/NVMMU allocation held.

Legacy whole-pilot rc-3 and post-disable qualification false remain. The complete Boolean predicate set matches the previously accepted four-Read epoch: HMB base/size fail the pre-start form, while separately observed deletion, normal shutdown, disable and BME-off pass. This preserves the conservative lifetime boundary. No independent DMA retirement, forced unload, backing release, reset or same-epoch retry is authorized.

## Separate charging follow-up

After acceptance/log collection, one explicit activation reused the accepted hash-pinned native 300 mA/7,200 s profile. Seven scoped monitors read 4.875 V/300 mA without a scoped guard-stop. Eight samples at 82% are Good, at most 32.3 C/4.095 V, with 1,055,000 uAh unchanged remaining charge. Battery current is mixed: three positive, two negative, three zero; mean **-15.375 mA**. Applied input is confirmed; sustained positive battery charging is not. Full lease operation/expiry remains unqualified. Existing electrical/thermal/VBUS guards and finite expiry are unchanged; no automatic renewal is added. S3E remains ref1/Live and interfaces absent.

## Next gate and recording boundary

The known pair tested queue progression, not renewed capacity/GPT/APFS discovery. This helper did not validate descriptors, bind UUIDs, scan all slots, select a newest complete checkpoint, read mapped filesystem objects, decrypt, mount, persist or write NAND.

Private planning shows the complete descriptor area exceeds the existing 127-fresh-data-tag budget. One queue wrap is qualified; active data/TCB reuse is not. The next bounded candidate should qualify multiblock Reads with retained fresh buffers, or separately qualify another explicit streaming strategy, before the complete scan and same-epoch block-zero UUID binding. Exact geometry and next-read coordinates stay private. No next image or additional hardware execution is claimed.

Raw logs, exact command/power manifests and parsed acceptance were saved privately on the Dell before a brief remote connection interruption. The connection returned before this documentation update. No hardware trial was retried after the interruption. Binary firmware, keys, boot IDs, raw sectors/checksums/hashes, UUIDs, numeric APFS object/transaction IDs and physical geometry remain outside public Git.
