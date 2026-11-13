# Original Samsung A9 S8000 PCIe port-local configuration writer: provider-pointer provenance

**2026-11-13. Verified directly against owner-private original N71 Apple kernelcache Mach-O, authentic N71 ADT, and original iOS PCIe root/port1 IORegistry snapshots. Entirely OFFLINE; no iPhone PCIe/MMIO/DART activity.**

## Correction: the mapping initialization below belongs to a different class

The original analysis incorrectly connected the shared-module initializer at +0x2074 to the port-instance +208 pointer. That initializer belongs to another class in the same executable; equal field offsets do not establish object identity. This report's index0/global-config inference is superseded by `tools/n71_s8000_port_local_mmio_gate.py`. The constructed port uses the Embedded port initializer (vslot104, +0x4918): its root vslot1864 selects `1+2*port`, the map object is stored at +200, its virtual base at +208 and a physical/helper result at +216. Port1 selects resource3, 0x602000000/0x4000. The exact original vtables, instruction chain and original live resource list pass the new gate. The old tool's initializer-fragment checks alone do not prove port-pointer provenance.

## Historical findings (partially superseded)

We resolved a previously opaque part of the authentic Apple `AppleS800xPCIePort` driver: the **port-local virtual configuration writer** and its pointer provenance. This is original Apple runtime-source analysis and **not** a new Linux driver that can operate Wi-Fi.

- The actual constructed N71 S8000 port vtable identifies **port method slot 1568** as the inherited S800x configuration selector. Its source reads a local state field, uses a bounded relative jump table, and has branches accessing relative configuration offsets `0x124` and `0x128` through the port-object virtual **slot 2008**. The `0x128` write value is formed from a separate object field through an OR of the register value and its left-shifted 16-bit copy. The available code signatures prove the **source paths**, not which branch is taken on the physical Wi-Fi module.
- The original port virtual **slot 2008** invokes a virtual validation/access check at slot 1688 before a direct 32-bit indexed store. That write takes its base pointer from the **port instance field at offset +208** and uses the relative offset argument; this is distinct from a previously identified second mapping-related field at **+216**.
- The port instance initialization path loads **provider virtual slot 976** from its parent/root provider, passes source argument **index 0** (plus second argument 0), invokes it, stores the first returned pointer at port-object field **+208**, checks for null, then calls a method on the returned object and stores the second result in **+216**.
- Independently, the original N71 Apple ADT and **real iOS** `apcie` IORegistry prove the provider's `IODeviceMemory` array has **11 ordered resources**. The index-0 **global PCIe configuration aperture** is `0x610000000` with extent `0x1000000`. The separately documented **WLAN port1** resources are **index 3**: `0x602000000/0x4000` and **index 4**: `0x602004000/0x4000`. The previous [original live provider ordering audit](N71_IOS_LIVE_IODEVICEMEMORY_ORDER_2026_11_12.md) independently established their address/size ordering.
- The new evidence therefore raises a **specific risk**: the original port-local configuration writer's provider-index-zero source path is associated with the **global PCIe configuration window**, not obviously the two port1-specific register apertures. To prove the pointer's *actual physical target* requires qualifying what the provider's dynamic virtual call returns at runtime. Neither an opcode nor a metadata index alone establishes that the write can affect only Wi-Fi.

**Do not conflate**: an Apple code path using offset `0x124`/`0x128` within a provider-selected mapping, the root-common control bank at `0x600000000`, and the port1 resource bank at `0x602000000`. These are separate potential address spaces; a register's relative offset has no unambiguous meaning without its **verified MMIO base** and full PCIe bus/requester selection.

## Reproducible, privacy-safe provenance gate

The new [original port-config pointer verifier](../tools/n71_s8000_original_port_config_pointer_provenance_gate.py) reuses the project's independent verified original Apple kernelcache/ADT/iOS constructor and port fanout audits, then checks selected original ARM64 instruction identities for three distinct mechanisms:

| Original code region | Source-level verification | Hardware inference boundary |
|---|---|---|
| Port slot 1568 | State-selected indirect config-access path to `0x124` and `0x128` | Selected state, actual radio endpoint and global bus effects are unproven |
| Port slot 2008 | Access validation precedes a 32-bit indexed store through object field `+208` | No claim that the dynamically returned pointer is port1-only |
| Original port initialization | Parent provider slot976(index0,0) returns pointer stored `+208`; second object-derived result stored `+216` | Global provider index-0 candidate; neither dynamic return nor actual physical write observed |
| Original ADT + iOS IORegistry | Root provider index0 is global config and indexes3/4 are separate port1 windows | Provider list ordering is source evidence, **not** a scoped MMIO test |

The [16 synthetic adversarial tests](../tests/test_n71_s8000_original_port_config_pointer_provenance_gate.py) mutate every selected ARM64 signature, verify function identity and method ordering, reject unknown relative offsets and overwide values, and intentionally **refuse even a symbolic write if the provider scope is unproven**. The source checks only a handful of selected instruction signatures; they are not full formal control-flow verification.

The private original file inputs remain exclusively on the owner's Dell; the public tool prints fixed flags rather than proprietary source, identifiers or raw source-specific values.

Example local offline-only usage:

```bash
cd ~/Documenti/iphone6s-linux-cyberdeck-public
python3 tools/n71_s8000_original_port_config_pointer_provenance_gate.py \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/s8000-pcie-kernelcache-offline/kernelcache.release.n71.macho \
  ~/Documenti/cyberdeck-a9-linux/private-firmware/runtime-n71/runtime-apple-adt.bin \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-dart1-live-ioreg-2026-11-12/live_apcie.plist \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-dart1-live-ioreg-2026-11-12/live_pci-bridge1.plist
```

The actual private-original check passed:

```text
N71_S8000_ORIGINAL_APPLE_PCIE_PORT_CONFIG_POINTER_SOURCE_PASS
N71_ORIGINAL_PORT_METHOD1568_CONFIG_OFFSETS_0X124_0X128=YES
N71_ORIGINAL_PORT_WRITER_METHOD2008_VALIDATES_BEFORE_STORE=YES
N71_ORIGINAL_PORT_METHOD2008_STORES_VIA_INSTANCE_FIELD208=YES
N71_ORIGINAL_PORT_FIELD208_FROM_PARENT_PROVIDER_SLOT976=YES
N71_ORIGINAL_PORT_SECOND_MAPPING_RESULT_STORED_FIELD216=YES
N71_IOS_ROOT_PROVIDER_INDEX0_GLOBAL_PCIE_CONFIG_WINDOW_PASS=YES
N71_ORIGINAL_PORT1_RESOURCE_INDEX3_4_DISTINCT_FROM_GLOBAL_CONFIG=YES
N71_PORT_WRITER_INDIRECT_PROVIDER_CALL_REQUESTS_INDEX0=SOURCE_PROVEN
N71_PORT1_PHYSICAL_MMIO_PROVIDER_REGION_BOUNDARY_PROVEN=NO
N71_PORT1_0X124_0X128_CROSSPORT_EFFECTS_SAFE=NO
N71_S8000_PCIE_DART1_REQUESTER_SID_PROVEN=NO
N71_PHYSICAL_PCIE_OR_NATIVE_BCM4350_WIFI_ACTIVATION_AUTHORIZED=NO
```

## Consequences for safe Linux port1 bring-up

The **global configuration window** must not be included in any naive port1-only write allowlist. Before considering real PCIe MMIO, prove the exact object/mapping returned by provider slot976, identify how the original Apple code selects the specific port/bus during the `0x124`/`0x128` accesses, and independently qualify effects on storage port0 and modem port2.

We must also retain the separately proven N71 **WLAN bridge1 → DART1 mapper** relationship while acknowledging that the actual physical PCIe requester→DART1 SID/IOVA and safe multi-stream reset remain unproven. The offline experimental [DART all-stream reset interlock](N71_S8000_DART_ALL_STREAM_RESET_INTERLOCK_ARM64_2026_11_13.md) remains active in the *separate* experimental source and is **not** installed on the currently running phone.

**Current device state:** previously verified RAM-only Linux, original Apple BCM4350C5 C5 firmware and Broadcom Linux software present, USB Internet via Dell, no native PCIe Wi-Fi endpoint or WLAN interface. During this original-kernelcache analysis the phone was not rebooted; no MMIO/DART/DMA/storage access was attempted.
