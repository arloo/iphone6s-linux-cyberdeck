# N71/S8000: storage-port DART0 and NVMe MMU MMIO physically accessible

17 November 2026. A real iPhone 6s Samsung A9 running the existing RAM
kernel completed a new bounded storage-port trial. This resolves the
previous all-ones MMIO-access blocker; the storage endpoint and its
namespaces have not yet been enumerated.

## Physical change and result

The existing pilot already held NAND GPIO160 OUTPUT LOW, enabled the
port0 NVMe mode, powered pcie_link0 and set port0 ID3/ID2 bit0.
That sequence returned all ones from the storage controller windows.

The new opt-in `stock_late_controls=1` adds two original port-local
operations: clear ID2 bit8 at root+0x100, then set ID4 bit0 at root+0x124.
Both operations were source-verified against the genuine constructed
S8000 root vtable and had previously been microleased on WLAN port1.
This is a research combination under asserted endpoint reset, not a
claim to replay the complete Apple startup method or its status waits.

| Real observation | Before late controls | New physical result |
| --- | --- | --- |
| Port0 selector-ID5, root+0x12c | 0 | 1 immediately after ID2 bit8 was cleared |
| Port0 ID2 | 0x01000110 baseline | 0x01000011 during the trial |
| Port0 ID4 | 0 | 1 during the trial |
| DART0 command, 0x601008000+0x00 | 0xffffffff | 0x00000f02 |
| DART0 packed TCR, +0x0c | 0xffffffff | 0 |
| NVMe MMU control, 0x601004000+0x00 | 0xffffffff | 1 |
| NVMe MMU invalidate, +0x04 | 0xffffffff | 0 |
| Port0 local +0x22c | 0xffffffff | 1 |

ID5 becoming 1 after the ID2 change is an observed correlation.
The trial does not independently isolate which change made each MMIO
window readable, and ID5 alone is not PCIe endpoint enumeration.

## Rollback verified on the phone

After approximately 25ms, ID4 was restored first, followed by the
original ID2 and ID3 values. pcie_link0 then returned OFF, the temporary
NVMe mode returned to zero, and GPIO160 returned to its exact original
INPUT configuration. WLAN carrier remained1 and its power domain stayed
ON. The module unloaded successfully with no residual GPIO160 consumer.
Battery at the end was61%, Charging, +307mA net; the preceding eight
samples were all positive, averaging +278.25mA.

The actual ARM64 binary was built for the running
`7.3.0-rc1-n71-batt2-g68aadac820d0-dirty` kernel. Its staged SHA256 was
`e4d6b8096e9652f402724146f13c615795d080f14259b7af1e39840d7a4eb3ff`.
It first passed a real inert load/unload. The powered trial used a
single finit_module call, a session one-shot marker, verified charging
and the current encrypted iOS backup metadata.

## Selector correction and next work

The original S8000 selector uses base0x12c plus port*0x80 for ID5.
Older port0 pilots sampled 0x16c in some status/preflight paths; that
was not the proven selector. Current port0 sources now use0x12c.
Their independently logged DART/NVMMU all-ones observations remain valid.

## Linux-owned DART0 tables physically programmed and restored

Two further real-phone transactions passed with NAND reset held LOW:

| Stage | Owned roots | Active packed TCR | Invalidate command | Observed polls | Result |
| --- | --- | --- | --- | --- | --- |
| SID0 | 4 | 0x00000080 | 0x00000102 | 2 | inner_rc0, restore_pass1, pages_zero1, free_safe1 |
| All four streams | 16 | 0x80808080 | 0x00000f02 | 2 | inner_rc0, restore_pass1, pages_zero1, free_safe1 |

The sixteen 4KiB roots used sixteen distinct 16KiB Linux pages, 256KiB
of backing RAM. Every direct-DMA address was verified as the original
36-bit physical address; inherited-root overlap and duplicate roots
were rejected before zeroing. No table or physical allocation address
is published. The original ADT consumer graph identifies only S3E as a
declared DART0 consumer; DART0 and WLAN DART1 use the same stock driver
compatible and original TTBR format.

The outer transaction checked all sixteen TTBR cells, the packed TCR,
command status and fault state, then restored the inherited roots before
freeing the owned buffers. SID0 invalidation leaves the command's stream
selector at0x102; it does not replay0xf02 just to reproduce a readback.
The all-stream command selects all four exclusive storage DART0 streams.
Each invalidation loop has at most100 polls with1us ticks. Failure to
disable translation, finish a command, restore roots or observe reset LOW
retains the pages, module, domain consumer and reset hold for quarantine.

The all-stream trial's ARM64 SHA256 was
`f6560f10af82a615eb2f8d33e1744f1bd41d16e3ca406ed7c5a5f24626970311`.
Its final readings were battery68%, Charging, +276mA net; the eight
preflight samples were all positive. The module unloaded normally after
verified rollback and WLAN carrier stayed1. A host-compiled fault harness
also checks success, timeout, failed TCR disable/page retention, bad TTBR
readback, fault-state change, missing reset and duplicate roots. Those
control-flow tests are distinct from the physical results above.

Next: qualify bounded endpoint reset release and read-only PCIe config
identification while the owned tables remain active. Programming and
readback of empty roots have passed; endpoint DMA fault containment,
S3E enumeration, namespace reads and persistent Linux remain unqualified.
