# Apple N71/S8000 PCIe storage startup: original command 3/7 and callback ordering

**17 November 2026.** This report uses the genuine owner-private N71
Samsung S8000 iOS ARM64 kernelcache and original Apple Device Tree.
Original Apple binaries, original device data and source code recovered
from binaries are **not** redistributed. Reproducible proof consists of
version-pinned instruction identities, exact constructed C++ vtable
resolutions, virtual dispatch and synthetic adversarial regression tests.

## Important correction to the original source model

The earlier port1 root fan-out verifier proved one per-port operation:
root vtable **2040** issues a write of `3` to the root common register at
`0x4020 + port*0x40`.

The stock A9 constructor/vtable and ARM64 code now independently prove a
**second** command operating on the *same register*:

| Real N71 constructed C++ instance | Virtual slot | Original method | Real operation |
| --- | --- | --- | --- |
| S8000 root | 2040 | `AppleS800xPCIe +0x7d8` | write32 `3` to `0x4020+0x40*port` |
| S8000 root | 2048 | `AppleS800xPCIe +0x7f0` | write32 `7` to the **same register** |
| S8000 port | 1864 | `AppleS800xPCIe +0xb3c` | forwards port index to root slot 2040 |
| S8000 port | 1872 | `AppleS800xPCIe +0xb54` | forwards port index to root slot 2048 |

All four original vtable slots resolve to these exact methods in the
authentic N71 Apple kernelcache. Two further stock code paths invoke
port slot1872 (the `7` command): shared module `+0xa5c` and
embedded module `+0x3eb0`. Their precise electrical significance and
safety during an independent Linux startup are **not** established.

The live iPhone read-only result is `0` for all four per-port
command-register readbacks, including the currently working WLAN port1
(`root+0x4060`). That observation is compatible with various command
or event-register designs but **does not prove** that writes self-clear,
are safely replayable, or are read-only.

## Proved storage-port start method order

The stock Apple `AppleS800xPCIe` code executes the following **within
the same startup method**, with the branch at `+0x1310` controlling
the conditional local configuration step:

| Instruction/source offset | Verified operation |
| --- | --- |
| `+0x12f0` | Call port vslot1864 -> root vslot2040 -> write `3` to the per-port root control register |
| `+0x1300` | Call port vslot1504: additional nontrivial local PCIe configuration, electrical effects unqualified |
| `+0x1318` | Conditionally call port vslot1848, affecting root ID3 bit8 |
| `+0x1328`, `+0x132c` | Initialize a shared 32-bit callback argument to `1` |
| `+0x1330`, `+0x1338`, `+0x1348` | Dispatch the real DART controller function through object +304, vslot128 |
| `+0x134c`, `+0x1358`, `+0x1368` | Dispatch the distinct NVMMU controller callback through object +2912, vslot128 |

Earlier in the same function, the source performs root ID2/ID3 power
sequencing, bounded waits and port-specific control operations. The
original Apple ADT maps the storage callbacks to **real registry
device** phandles `0x80` (DART0) and `0x82` (NVMMU0); the S3E
endpoint's `iommu-parent` remains `(0x81,0x81,0x82)`.

Another separate stock method (`AppleS800xPCIe +0x1160`) calls the
DART and NVMMU callbacks with a shared argument initialized to `0`
(`+0x1174/+0x1178/+0x1194`). **Source address order is not runtime
execution order across independent methods**: do not assume state-0
must execute immediately before state-1 when booting.

## Consequences for the Linux Cyberdeck

The previous successful physical Linux test asserted NAND PERST160 low,
enabled the root NVMe mode and port0 ID2/ID3 controls, powered
`pcie_link0` for 25 ms, sampled DART0/NVMMU0 and restored everything.
Both storage IOMMU register windows remained `0xffffffff`. The new
static reconstruction shows that the physical test did **not** replay
the original `3` command, the port vslot1504 configuration or the
stock DART0/NVMMU0 callback sequence. That is a real difference to
investigate, **not proof** that these operations alone will resolve
the missing MMIO or train the PCIe link.

**Next hardware enabling gates before another powered trial:**

1. Reverse the S8000-specific DART0 and NVMMU0 `Fact` function handlers
   (IORegistry phandles `0x80`/`0x82`) and identify their real power,
   clock and register side effects.
2. Reverse the port vslot1504 configuration and `3`/`7` command
   semantics; verify their effects remain port-local and reversible
   while WLAN port1 is live. Do not treat root readback `0` as a
   reversible register snapshot for a possibly write-only command.
3. Prepare the Apple S8000 requester/DMA-quarantine path before
   deasserting NAND PERST or attempting generic NVMe commands.
4. Require validated battery/USB supply, exact rollback and a
   successful current encrypted iOS backup check for any physical test.

No iOS/NAND access, PCIe write, reset release, new boot, and no DMA
mapping was performed while producing this original source proof.

## Reproduce safely

Run the offline checker against the owner-controlled stock N71
kernelcache and original ADT (absolute private paths supplied locally):

```bash
python3 tools/n71_s8000_original_storage_pcie_command_order_gate.py \
    /path/to/private/n71/kernelcache.macho \
    /path/to/private/n71/original-apple-adt.bin
python3 -m unittest discover -s tests \
    -p 'test_n71_s8000_original_storage_pcie_command_order_gate.py'
```

The private source gate returned
`N71_APPLE_PCIE_STORAGE_COMMAND_AND_CALLBACK_ORDER_GATE=PASS`.
All 14 targeted synthetic adversarial tests passed. Neither
invocation interacts with the phone.
