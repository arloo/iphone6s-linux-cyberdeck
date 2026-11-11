# N71 S8000 PCIe: original controller-self and provider argument audit

Date: 2026-11-11. **Offline-only study of the original iOS 15.8.8 N71 ARM64 kernelcache.** No hardware PCIe, MMIO, DMA or radio activity.

## Verified argument flow within a separate AppleEmbeddedPCIE method

**ROOT/PORT CORRECTION:** The [port-constructor audit](N71_S8000_CONSTRUCTOR_CHAIN_PORT3_OVERRIDE_2026_11_11.md) examined a separate AppleS8000PCIePort class and was incorrectly extrapolated to the ROOT controller. The [new root-class audit](N71_S8000_ROOT_START_RESOURCE_INDEX_2026_11_11.md) has now verified that the S800x root start routine statically calls this EmbeddedPCIe root start method through its parent vtable, and that its actual S8000 root virtual selectors return indices 0 and 9. This original method's X19/X20 register-flow observations remain valid. Physical provider resource ordering remains unverified.

The AppleEmbeddedPCIE method saves its first argument (X0: controller object / self) to X19 and its second argument (X1: hardware provider) to X20. Both resource-selector virtual calls load the vtable through X19 and invoke the selector with X19 as receiver. In each case the returned value becomes the memory resource index passed to a distinct virtual mapping call on the provider X20. This distinction is verified from the original ARM64 instruction path.

Independent original Apple prelink metadata includes a single IOKit matching personality for the A9 root PCIe controller:
- Bundle: com.apple.driver.AppleS8000PCIe
- IOClass: AppleS8000PCIe
- IOProviderClass: AppleARMIODevice
- IONameMatch: apcie,s8000

The private N71 Apple ADT has the matching apcie,s8000 device node. This is evidence of the intended class/provider match, not a live iOS runtime trace.

The earlier zero/unsupported values were from a **PORT-object MetaClass** audit, not the root-controller vtable. The later root audit independently resolves the inherited base-start call and confirms the root selector return indices 0/9/10 for the four-port N71 ADT. The conditional physical mappings remain unqualified pending runtime provider-resource-order verification.

## Public reproducibility

Tool: tools/n71_s8000_start_receiver_gate.py, a standard-library-only, fail-closed, read-only auditor of a private decompressed Mach-O and private Apple ADT.

Local command (private inputs only):

    python3 tools/n71_s8000_start_receiver_gate.py /private/kernelcache.macho /private/n71-adt.bin

The tool verifies the exact original ARM64 register flows and a unique, matching original IOKit personality, then prints sanitized metadata. Successful execution explicitly reports that the runtime vtable and common MMIO bases remain unproven. It never outputs firmware, original code or linked function addresses. The 15 synthetic tests cover both receivers, provider separation, virtual selectors, malformed input, personality parsing and no hardware-effect APIs.

## Remaining strict qualification

1. Prove the effective runtime vtable/override/thunk path or independently establish S8000 common-controller register resource indices and roles.
2. Prove the provider memory ordering and safe port-1-only reset/PHY/clock/MSI/link behavior without affecting storage port0 or baseband port2.
3. Prove the real DART1 stream/context/page table/fault behavior; logical BCM4350 mapper reference alone is not sufficient for bus-master DMA.
4. Only then stage a reviewed RAM-only S8000 PCIe driver test, preserving the existing Linux GUI, Z2 touch, USB recovery and NAND.
5. Bring up real BCM4350 with the offline-built Broadcom ARM64 stack and legitimate board-matched private radio firmware; require authenticated SSH before independent WLAN.
6. Pass the on-device wireless-only test against the authorized Dell access point and router. USB tethering cannot count.

**Native Wi-Fi association is still blocked by unverified S8000 PCIe and DART hardware behavior.**
