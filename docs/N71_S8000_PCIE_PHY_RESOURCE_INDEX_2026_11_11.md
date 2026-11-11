# N71/S8000 PCIe resource-index investigation — corrected interpretation

**Correction: the earlier index-zero conclusion was wrong.** The original A9/S8000 configuration routine supplies **selector argument zero** to a virtual method. That method returns **resource index 10** when the root controller reports four ports; the returned index is subsequently supplied to the hardware provider's memory-map API. These are not the same integer at different stages.

The original code paths are independently validated in the [root startup and resource-index audit](N71_S8000_ROOT_START_RESOURCE_INDEX_2026_11_11.md), using the privately held original iOS 15.8.8/N71 Mach-O and Apple ADT. Do not rely on earlier index-zero PHY interpretations.

## Original class-specific evidence

The original AppleS800xPCIe and AppleS8000PCIe root configuration methods both contain an argument-zero virtual selector followed by a provider memory-map call, null-check and stored map/base metadata. Additional AppleEmbeddedPCIE root startup code uses two virtual selectors for its configuration and common mappings. The corrected root-class analysis resolves these actual virtual slots and their original ARM64 formulas, rather than assuming their return values.

With ADT #ports=4:

| Mapping role | Original root virtual selector | Returned resource index | Corresponding ADT tuple, **conditional on provider ordering** |
|---|---|---|---|
| Configuration/ECAM | Embedded root slot 1856 | **0** | reg[0], 0x610000000 / 16 MiB |
| Common registers | S800x root slot 1880 | **9** | reg[9], 0x600000000 / 32 KiB |
| Additional PHY/common resource | S800x root slot 1888 with argument zero | **10** | reg[10], 0x600008000 / 16 KiB |

The local ADT independently verifies exactly 11 original host ranges, four ports, the BCM4350 WLAN under PCIe port1, and a unique logical WLAN-to-DART1 mapper relationship. The **resource-order relationship within AppleARMIODevice remains unproven**. Consequently the physical addresses above are candidates, NOT validated register access addresses.

## Historical narrowly scoped tool

tools/n71_s8000_phy_resource_gate.py still checks the original A9/S800x root selector-argument-zero instruction patterns and the existence of two additional EmbeddedPCIe map calls, but now states that it **does not calculate the returned provider index by itself**. Its output explicitly uses VIRTUAL_SELECTOR_ARGUMENT 0, not MAPPED_RESOURCE_INDEX 0. The separate tools/n71_s8000_root_resource_gate.py performs the full inheritance, selector-formula and private ADT verification.

Both tools are offline-only; no Apple firmware or per-device secrets are included in the public repository. The historical 17 synthetic tests still validate the original instruction patterns and fail-closed behavior; a further 19 synthetic tests validate the new root-dispatch/index calculations.

## Hardware access remains blocked

Do not map guessed physical PCIe addresses or touch unknown global clock/reset bits. Actual provider memory order, S8000 bitfields, port1-only link initialization, DART1 stream/DMA security and genuine Linux BCM4350 enumeration remain unverified. Preserve the existing RAM-only Linux display, touchscreen and USB recovery path, and do not modify NAND. The actual native WLAN association to the same authorized access point as the Dell has not yet been performed.
