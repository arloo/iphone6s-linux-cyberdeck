# N71/S8000: original Apple WLAN DART1 logical mapper 0 → packed TCR byte lane 0

**2026-11-12 | Hardware:** iPhone 6s N71, Samsung A9/S8000 | **Evidence:** original privately held iOS 15.8.8 ARM64 prelinked kernelcache and original S8000 N71 ADT | **Result:** ORIGINAL SOFTWARE MAPPER-TO-TCR-LANE CONTROL-FLOW PASS, actual PCIe requester routing and safe Linux DMA remain UNPROVEN.

## Concrete original Apple firmware breakthrough

Previously the Apple Device Tree established only that the onboard BCM4350 WLAN node was the sole **declared** consumer of the child mapper of dedicated `dart-apcie1` and that this mapper's Apple `reg` property was exactly the 32-bit value `0`. There was no proof that `reg=0` was used as a native DART stream index.

We have now independently extracted **only into the private Dell research tree** and inspected the authentic original ARM64 executable sections of two Apple KEXTs:

| Original Apple driver | Original AArch64 executable size | Relevant function |
|---|---:|---|
| `com.apple.driver.IODARTFamily` | 64,836 bytes | Mapper property read, object-field storage and virtual dispatch |
| `com.apple.driver.AppleS5L8960XDART` | 17,156 bytes | Four-stream index validation, packed TCR-byte selection and register access |

The version-pinned original disassembly establishes a complete **software** chain:

1. `IODARTFamily` obtains the mapper provider's actual property named `reg` (not a guessed string), interprets its first 32-bit value and stores it in the mapper instance's field at relative byte offset `272`.
2. During the mapper enable/disable paths, that same field is loaded unchanged and passed to original controller virtual slot **1408**. The original enable call passes boolean `1`; disable passes `0`.
3. The actual constructed `AppleS5L8960XDART` **instance vtable** (not a MetaClass table) resolves slot **1408** to a method whose controller/stream-index argument is forwarded into original virtual slot **1736**.
4. The actual vtable resolves slot **1736** to the hardware TCR update routine. It rejects stream indices outside `0..3`, uses the supplied index to select one of four bytes of a packed 32-bit TCR value, sets the selected byte's bit `7`, and uses the mapped controller register at relative offset **`0xC`**. The unrelated three packed byte lanes are preserved by the original staging algorithm.
5. Original S8000 N71 ADT independently proves this WLAN mapper `reg=0`, and the whole-tree IOMMU census establishes that no other node in the supplied ADT declares consumption of its mapper.

**Derived original-driver result:** The onboard BCM4350's Apple mapper logical index **0** is routed through the genuine Apple driver to **packed TCR byte lane 0**. This is stronger than a metadata-only identity guess. It is **not yet an observation of live DART1 DMA traffic**. A potential PCIe requester-ID-to-stream-ID mapping stage, controller power sequencing, on-chip DMA masters, TTBR state and IOVA fault isolation still require proof. We must not claim that WLAN traffic physically uses stream 0 until the entire endpoint-to-IOMMU path is qualified.

## Reproducible and privacy-safe original-code gate

`tools/n71_original_dart_mapper_tcr_lane_gate.py` verifies original iOS ARM64 Mach-O header and prelink segment bounds, exact KEXT metadata, pinned KEXT executable lengths, original instruction-level property getter, field load/store, enable and disable dispatch, actual Apple S5L DART constructed instance vtable targets, original per-stream byte update instruction chain and original complete N71 ADT DART1 topology and `reg` value. It never executes Apple binary code, reads MMIO, changes phone state or writes private input files.

All original executable bytes, KEXT sections, Apple Device Tree, live device registry, SysCfg, MAC, Wi-Fi calibration and firmware remain PRIVATE. Only original ARM64 instruction word signatures and hardware-invariant, vendor-independent derivations are published in the checker, not any proprietary Apple binary payload or unredacted device capture.

Run locally on the authorized Dell, supplying privately retained inputs:

```bash
python3 tools/n71_original_dart_mapper_tcr_lane_gate.py \
    /private/original-n71-kernelcache.macho \
    /private/original-n71-apple-adt.bin

python3 -m unittest discover -s tests \
    -p test_n71_original_dart_mapper_tcr_lane_gate.py -v
```

Actual verified original-file result:

```text
N71_ORIGINAL_APPLE_DART_MAPPER_TO_TCR_LANE_STATIC_PASS
ORIGINAL_IODARTFAMILY_MAPPER_REG_TO_FIELD_AND_DISPATCH=VERIFIED
ORIGINAL_S5L_DART_VTABLE_DISPATCH_TO_TCR_BYTE_LANE=VERIFIED
WLAN_DART1_APPLE_LOGICAL_MAPPER_INDEX 0
ORIGINAL_S5L_TCR_BYTE_LANE 0
ORIGINAL_S5L_TCR_RELATIVE_OFFSET 0xc
ORIGINAL_S5L_HARDWARE_STREAM_INDICES 0 1 2 3
ACTUAL_PCIE_REQUESTER_TO_SID_ROUTING_PROVEN=NO
DART1_LIVE_TTBR_IOVA_DMA_ISOLATION_PROVEN=NO
HARDWARE_MMIO_GPIO_RESET_AND_LINUX_WIFI_AUTHORIZED=NO
PROPRIETARY_OR_PRIVATE_ORIGINAL_PAYLOAD_EXPORTED=NO
```

The companion `tests/test_n71_original_dart_mapper_tcr_lane_gate.py` contains **22 synthetic safety and regression tests**, including mutation of every pinned original instruction signature, malformed Mach-O/ADT rejection, wrong mapper index, unexpected DART1 consumer and non-disclosure of private paths. Full project tests and privacy checks are performed independently before publishing.

## Practical Linux bring-up implications

The existing pinned Linux S5L8960x DART implementation contains a **packed-TCR read-modify-write bug** that overwrites other stream lanes; a separate experimental correction has already been cross-compiled and tested offline but is **not integrated into the known-good iPhone RAM boot**. Original Apple S5L DART behavior now provides an independent implementation reference: select one eight-bit lane and preserve the other three. The Apple per-stream logic must not be blindly copied as a Linux driver, and the experimental fix alone does not solve the driver-wide reset.

The original Linux `apple_dart_hw_reset()` still disables DMA and clears page tables for **all four streams of the probed DART instance**, so automatic probe remains unsafe without validated reset ownership and rollback. No DART1 MMIO, PMIC GPIO, PHY, reset or Wi-Fi chip initialization was performed.

**Next P0:** Verify actual A9 PCIe port1 requester/transaction mapping onto the DART1 hardware index and register base, then prove isolated DART1 TTBR/IOVA/fault containment and boot-safe initialization, keeping port0 storage and port2 baseband intact. Only then use an explicitly authorized reversible RAM-only on-device experiment, enumerate BCM4350 and test its private board-matched C5 firmware, on-device wireless PHY and direct association with the Dell's authorized Wi-Fi (USB relay is forbidden as a success substitute).

**Do not conflate** the Asahi M1/T8103 RID-to-SID mapping mechanism with this N71/S8000 four-port, three-DART topology without direct A9 evidence. Compare APIs and architectures only, not unverified physical register offsets.

Background technical references:
- https://projectzero.google/2017/10/over-air-vol-2-pt-3-exploiting-wi-fi.html
- https://lkml.iu.edu/2109.2/09055.html (M1 RID-to-SID, comparative architecture only)
- https://asahilinux.org/docs/hw/soc/apcie/ (T8103, comparative only)
