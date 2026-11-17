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

Next: program and verify Linux-owned DART0 translation roots and bounded
TLB operations while NAND reset remains asserted. Endpoint reset release,
PCIe identification and namespace reads require that isolation work first.
This result provides register access, not NAND data or persistent Linux.
