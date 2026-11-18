# S8000 NVMe Ready and first queue DMA fault, 2026-11-18

The physical N71/S8000 ANS controller reached CSTS.RDY=1 after CC.EN under owned memory mappings. A single Identify namespace-1 command was submitted. **No completion or Identify payload arrived.** Namespace geometry, block access and persistent Linux storage remain unproven.

## What the physical trial did

The pilot used the previously verified, owned contiguous 8 MiB HMB and S8000 SART path, owned NVMMU TCB/aux roots, and 16 owned DART0 root pages. Eight additional 16 KiB backing pages held SQ, CQ, a 4 KiB Identify response, a FlatDMA SGL and four L2 tables. Each DART stream exposed only the two 4 KiB queue pages. Absolute/relative queue windows were mirrored; the data response used FlatDMA tag0 with device-to-memory direction and page count published last.

The controller accepted queue register programming (depth16, 4 KiB controller pages), and its admin interrupt vector was masked. Both 16-bit PCI command words changed from 2 to 6 only after preparation; PCI status W1C bits were not written. CC was 0x00460001. Following a 100 ms settle, Ready was observed after 979 bounded poll iterations, roughly 1.2 seconds from enable.

Only opcode6, NSID1, CNS0 was placed in SQ entry0; the SQ tail doorbell was written once. No I/O queue, block read, write, format or partition operation exists in this pilot.

## Physical failure and retention

Immediately after submission CSTS became 3 (Ready plus fatal). CQ phase remained zero; the completion loop stopped at its first observation. Clearing CC did not clear Ready within the 2,000-iteration disable bound. Both PCI command words were verified back at 2, so BME was off before PERST was reasserted.

A separate read-only snapshot, with port0 power held and GPIO160 output low, captured:

| Register / decoded fact | Observed value |
| --- | --- |
| DART0 error | 0x80000102 |
| Error stream | 0 |
| Low error code | 0x02, NO_PMD in the locally held S5L decoder |
| Fault IOVA | 0x00010000, the relative SQ address |
| DART command / packed TCR | 0x00000f02 / 0x80808080 |
| NVMMU control / invalidate | 1 / 0 |
| SART enable | 1 |
| GPIO160 | Output low |
| Native WLAN | Carrier remained up |

The faulted pilot used PA|1 for its upper-level child-table descriptor, following generic modern io-pgtable-dart code. Original Apple S5L8960x code proves a different non-leaf encoding: mask the child-table PA to bits35:12, OR **3**, then store a 64-bit descriptor. The original leaf encoding alone was not sufficient proof of this upper level.

The pilot returned its quarantine result, pinned its module, and retained HMB, NVMMU, queue and DART memory plus port0 power and reset ownership. No retained memory was freed, no forced unload occurred, and the fault register was not cleared. Normal cleanup was deliberately refused. An authenticated full restart was requested after all evidence was saved; the next trial requires a fresh physical boot, never rearming this held state.

Physical faulted pilot SHA-256: c5fe70394003188177743a38b174cd9c60d82c93d6ae7baf4ff4b92e4f923a27.

## Corrected candidate, not yet tested on hardware

The next candidate uses PA|3 for non-leaf descriptors, matching the original instruction sequence. It also refuses a DMA-coherent supervisor device so streaming cache synchronization cannot silently become a no-op. This is a source-backed correction to test, not a completed fix or successful Identify claim.

The original-only static audit passes against the owner-held N71 kernel and ADT. It now checks the upper-level builder as well as TTBR and leaf encodings. This mode explicitly makes no Linux guard or hardware DMA claim. The historical full Linux audit remains strict: its old WLAN-blocked guard signature no longer matches the evolved working WLAN tree.

The 47 S3E transaction regressions and 22 original-format regressions pass. Both the corrected pilot and the read-only fault snapshot module compile for the running ARM64/16 KiB-page kernel without warnings. The corrected pilot is built and its fresh-boot, single-run staging harness is prepared; it has not been loaded or armed.

Corrected candidate SHA-256: fc1067b1c3e8721fb4914a1a0134f566eb44ba449c358105a090a7fcedb4bb47.

Next physical gate: boot the same verified RAM image, requalify the authenticated USB link and battery support, then stage the corrected pilot once. A successful Identify must include both a valid CQ entry and independently arrived data; Ready alone is insufficient.
