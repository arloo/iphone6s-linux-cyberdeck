# N71/S8000: actual storage DART and NVMe MMU Fact implementations

17 November 2026. Continues the
[original PCIe command/callback order](N71_S8000_STOCK_STORAGE_PORT_COMMAND_3_7_CALLBACK_ORDER_2026_11_17.md).
This is static analysis of the owner's genuine Apple kernelcache and ADT,
not a new physical storage activation. Private firmware and device data
remain outside this repository.

## Exact next-stage result

The two storage `Fact` callbacks are not interchangeable clock enables.
The original software performs driver-state restoration, including MMIO
writes derived from previously initialized state. No Linux port0 startup
or DMA isolation is qualified by this source result.

| Original component | Proven source route | Consequence |
| --- | --- | --- |
| DART0 | IODARTFamily recognizes `Fact`, converts the argument to a Boolean and dispatches constructed AppleS5L8960XDART vslot1536 | The original ADT's `manual-availability=1` enables the support flag at object offset2368 bit31 |
| DART availability | S5L method +0x1d84 saves the requested Boolean at offset2386 and calls vslot1744 (+0x1cb4) | The manual path compares desired/current availability and selects vslot1680 or1688 |
| DART activation | vslot1688 resolves to +0x3984 | Calls provider vslots1384 and1392, then vslot1704; this is more than a lone PMGR transition |
| DART restoration | vslot1704 resolves to +0x3b68 | Restores saved DART control state at register offset0x0c and checks stream enable bits; Linux cannot assume the Apple object's saved values exist |
| NVMe MMU callback | Real Fact-factory object and constructor share a vtable; vslot128 resolves to +0x38c4 | Reads the Boolean argument, obtains its owner at offset40 and calls +0x368c |
| NVMe MMU activation | +0x368c | Restores two saved 64-bit values into register pairs 0x10/0x14 and 0x08/0x0c, then restores optional configuration at 0x20/0x24/0x28/0x2c |
| NVMe MMU invalidation | +0x27e8 | Writes 0x10000 at register0x04, reads back, and polls bit16 in a two-instruction loop with no local deadline |

The NVMe MMU implementation resides in **AppleS800xPCIe**, rather than
the NVMe block-controller implementation in IONVMeFamily. The original
mapDeviceMemory index0 path stores its mapped address at owner offset216;
the authentic ADT identifies that first resource as **0x601004000,
length0x4000**. Its second resource is **0x601000000, length0x4000**.
These are stock mappings, not proof that Linux can currently access them.

**The NVMe MMU inactive branch is not an inverse hardware sequence.**
When changing state to zero, +0x368c stores the software Boolean and
returns without undoing the activation's MMIO writes. Replaying a
`Fact(0)` call therefore cannot be accepted as an exact Linux rollback.

The names and electrical effects of the DART provider's vslots1384/1392,
the source of all saved translation state, cross-port isolation, and
bounded hardware invalidation still need a complete Linux design.
Stock driver control flow alone does not supply these guarantees.

## Reproduce against the actual original input

```bash
python3 tools/n71_s8000_storage_fact_implementation_gate.py \
  /path/to/private/n71/kernelcache.macho \
  /path/to/private/n71/original-apple-adt.bin
```

The source gate verifies existing root/port/ADT provenance, actual
constructed virtual targets, property/class literals, original resource
mapping and pinned ARM64 instruction identities. It passed on the genuine
owner-held inputs. Four deliberate changes to those real source bytes
(Fact selector, DART dispatch, NVMe MMU call target, invalidation backedge)
were independently rejected. These are source-integrity checks, not
simulated phone tests.

The phone was checked separately before this analysis: native WLAN
carrier1, storage link0 OFF, no block devices, battery51% Charging,
+176mA net battery current, 36.6C and USB VBUS4.775-4.800V under the
existing supervised 500mA input lease. This is a dated observation,
not an unattended charging guarantee.

Next: resolve the provider power operations and initialize Linux-owned
translation/quarantine state before another storage-port powered trial.
The source audit itself performs no hardware operation.
