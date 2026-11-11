# N71/S8000 PCIe: original Apple PHY and shared-MMIO resource-index audit

Date: 2026-11-11. **OFFLINE research; hardware MMIO, DMA, PCIe resets and Wi-Fi remain blocked.**

## New original Apple A9 evidence

The privately preserved, checksum-verified iOS 15.8.8 ARM64 kernelcache contains original AppleS800xPCIe, AppleS8000PCIe and AppleEmbeddedPCIE drivers. A bounded read-only source analysis demonstrates:

- Both AppleS800xPCIe and AppleS8000PCIe request device-memory **resource index 0**, call a virtual provider memory-map function, reject a null map, and store its map and address metadata in matching private object fields.
- The shared AppleS800x module labels that mapping path with PHY-related diagnostic names. This is **evidence of a PHY-related resource-index-zero path**, not proof of a specific physical MMIO base.
- AppleEmbeddedPCIE separately acquires **two common-controller memory maps**, each of whose **resource index comes from a different virtual method**, not from an immediate constant. Their actual index values remain unverified; assuming they mean a particular raw ADT reg entry would be speculation.

Apple documents the semantics of IOService::mapDeviceMemoryWithIndex(index, options) as selecting a device memory range by index. Source:
https://developer.apple.com/documentation/kernel/ioservice/1810261-mapdevicememorywithindex

The read-only audit validates the control-flow shape and its common provider virtual call. It does NOT independently prove the precise Apple class ABI slot identity, the private provider's IODeviceMemory array ordering, or the eventual physical mapping.

## Candidate region versus verified hardware address

The private A9/N71 ADT root apcie,s8000 describes eleven physical ranges, with reg[0] = 0x610000000 (16 MiB). **This is a candidate PHY resource base**, contingent on proving that the original Apple provider creates its IODeviceMemory array in raw ADT reg order.

The two shared/global root-complex ranges are reg[9] = 0x600000000 (32 KiB) and reg[10] = 0x600008000 (16 KiB). They must NOT be paired with AppleEmbeddedPCIE's two dynamic resource requests until those selectors and their provider mapping are resolved. The existing A9 common-register selector has already proven six relative offset formulas (two common offsets and four port-indexed offsets); neither shared physical base is uniquely identified by those arithmetic formulas.

Other PCIe resources remain strictly protected: storage port 0, baseband port 2 and unknown port 3. No global reset, PHY or clock operation may be attempted from this evidence alone.

## Public reproducibility gate

Public tool: tools/n71_s8000_phy_resource_gate.py

It accepts only a locally obtained and already decompressed original ARM64 Mach-O and a locally held private Apple ADT. It reuses the previously tested prelink and S8000 ADT readers, validates the three KEXT code-section lengths and bounded ARM64 control-flow signatures, confirms both resource-index-zero paths and both dynamically selected common-resource paths, and checks the ADT first-range metadata. No original Apple code, full disassembly, raw ADT, firmware, addresses from the private executable or unique device identifiers are printed.

Local command:

    python3 tools/n71_s8000_phy_resource_gate.py /private/kernelcache.macho /private/runtime-apple-adt.bin

Successful output contains A9_PHY_RESOURCE0_MAPPING_INSTRUCTIONS_PASS together with:
- MAPPED_RESOURCE_INDEX 0
- ADT_REG0_CANDIDATE 0x610000000 size 0x1000000
- OTHER_COMMON_MMIO_RESOURCE_SELECTORS_DYNAMIC 2
- PROVIDER_RESOURCE_ORDER_CONFIRMED=NO
- COMMON_REGISTER_BASE_CONFIRMED=NO
- HARDWARE_BLOCKED

The tool uses a small collection of generic ARM64 instruction-pattern signatures, not a redistributed original kernel function. Seventeen synthetic tests in tests/test_n71_s8000_phy_resource_gate.py check positive and negative paths, invalid indices, changed virtual dispatch, null guards, state stores, dynamic resource selector changes, input bounds and absence of hardware-effect APIs.

## Physical bring-up remains gated

1. Independently resolve Apple A9 provider memory-resource ordering and the two dynamic common selectors; establish functional register roles and verified physical windows, including global side effects.
2. Prove S8000 port-1-only PHY/refclock, reset, link training and MSI setup without disturbing storage, modem or unknown port3.
3. Verify actual DART1 SID mapping, DMA translations and fault handling; no DMA bypass.
4. Extend the existing default-off Linux RFC 0011 only with reviewed and tested hardware-specific code. Use a separate supervised RAM-only image and preserve known-good Linux display/touch/USB, without NAND writes.
5. After real BCM4350 PCIe enumeration, use the already cross-compiled ARM64 brcmfmac/cfg80211, private board-matched firmware, authenticated SSH and on-device WLAN-only association test against the Dell LAN. A USB ping does not count.

**Native BCM4350 Wi-Fi is NOT yet active, and no hardware probe occurred.**
