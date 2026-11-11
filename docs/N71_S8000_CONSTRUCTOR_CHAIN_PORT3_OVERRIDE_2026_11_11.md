# iPhone 6s N71/S8000: constructor-chain and port-3 override audit

Date: 2026-11-11. **Original, privately owned iOS 15.8.8/19H422 kernelcache examined OFFLINE.** No live PCIe/MMIO, PHY, DMA, NAND, wireless configuration or reboot.

## Critical correction: MetaClass is not the constructed PCIe instance

The earlier [constructor-vtable report](N71_S8000_PCIE_VTABLE_SELECTOR_LIMITS_2026_11_11.md) inspected the pointer stored by the **MetaClass constructor** near the first part of the S8000 and S800x KEXT executable sections. The static zero-return and IOKit unsupported-status method found at MetaClass virtual slots 1856 and 1880 are **not evidence** of the same behavior on an instantiated A9 PCIe controller.

The original Mach-O contains separate constructors which write a second, different vtable pointer to an instance. The old [start receiver audit](N71_S8000_START_RECEIVER_PROVENANCE_2026_11_11.md) correctly showed the register flow inside a lengthy method in the AppleEmbeddedPCIE module, but **that method is not established as the actual startup code invoked by an S8000 root object**. It belongs to a separate vtable from the constructed ancestry analyzed here. Earlier reports must therefore not be used to infer S8000 common-memory resource numbers from that method.

The previous public read-only vtable tool has been corrected to identify its old findings as **MetaClass** methods and to validate that the two instance selector entries are instead inherited from S800x.

## Three nested constructors are statically resolved

By decoding the original AArch64 BL-to-stub operations and following the bounded module-specific GOT entries in the fully prelinked Mach-O, we recovered this original constructor sequence:

1. AppleS8000PCIe instance construction calls an AppleS800xPCIe constructor.
2. That AppleS800xPCIe constructor calls an AppleEmbeddedPCIE base constructor.
3. Each constructor installs its **own instance vtable** after the parent constructor returns.

This proves a static **base-to-derived construction chain**, not that a specific constructor or IOKit call executed on a currently running iOS system. Both the parent-call targets and final instance-vtable pointer calculations are validated with original ARM64 instruction-pattern checks. No original code or addresses of linked executable functions are redistributed.

Comparing the first 256 pointer slots in the verified constructed instance vtables gives:

| Comparison | Identical slots | Different slots |
|---|---:|---:|
| EmbeddedPCIe → S800xPCIe | 207 / 256 | 49 / 256 |
| S800xPCIe → S8000PCIe | **252 / 256** | **4 / 256** |

The four S8000 differences occur at vtable byte offsets **0, 8, 56, and 1816**. The first three are class lifecycle / metadata-related entries; the fourth is the only additional virtual-method override within that examined 2,048-byte window.

### S8000 override at virtual slot 1816

At this virtual slot, the S8000 constructed instance points to an original S8000-specific method. The parent S800x virtual slot 1816 points to a different original S800x method.

The original S8000 override checks one virtual hardware-query result against the constant **3** and also compares its stored **port index** with **3**. Only the matching special case enters the alternative branch. The other branch obtains a fallback method pointer from the original parent S800x vtable and tail-branches to it. We verified in the original kernelcache that the fallback pointer and the parent's virtual-slot-1816 pointer are **identical**.

Thus, for a port whose index is **1**, the port-index-equals-3 condition cannot select that special branch: the observed override uses its inherited S800x method for this virtual operation. This conclusion is restricted to the one original override and cannot be extrapolated to all PCIe power/clock/reset or Wi-Fi initialization.

The previous [A9 six-register offset selector](N71_S8000_PCIE_COMMON_REGISTER_OFFSETS_2026_11_11.md) remains a separate, valid static offset-formula result. Its physical base and functional register roles remain unproven.

## Public reproducibility without proprietary data

New public read-only tool: `tools/n71_s8000_constructor_chain_gate.py`. It:

- Parses prelinked original ARM64 Mach-O metadata, confines code and constants to declared sections, and validates three constructor vptr assignments.
- Validates both parent constructor calls by resolving AArch64 BL → twelve-byte trampoline → bounded GOT → allowlisted parent KEXT.
- Compares the first 256 instance-vtable slots and requires exactly the four observed differences.
- Validates the A9 override's two port-3 guards, parent-vtable indirection, and **exact** parent virtual method fallback.
- Emits ONLY aggregate class relationships, vtable-slot numbers and sanitized status. It does **not** print original instructions, private addresses, firmware, calibration, unique device identifiers or credentials.

Reproduce on a machine with its own legally held, already decompressed ARM64 Mach-O:

    python3 tools/n71_s8000_constructor_chain_gate.py /private/kernelcache.macho

Success includes `N71_S8000_CONSTRUCTOR_CHAIN_STATIC_PASS`, `A9_NON_PORT3_SHARED_METHOD_FALLBACK=VERIFIED_STATIC`, and `HARDWARE_BLOCKED`.

The accompanying `tests/test_n71_s8000_constructor_chain_gate.py` uses **18 synthetic tests** for BL/ADRP address calculations, wrong-register mutations, mismatched vptr assignments, vtable differences, dual port-3 guards, bounded constant-data pointers and inherited-target equality. All synthetic data is fabricated from generic ARM64 encodings; no Apple executable file is shipped.

## Still required before **native BCM4350 Wi-Fi**

1. Identify actual physical root-complex MMIO resources and register semantics on S8000 **without assuming** the unrelated original startup path provides the dynamic resource indices.
2. Independently validate port1 PHY/refclock/reset/MSI/link training while safeguarding storage port0, modem port2, unknown port3 and shared controller state.
3. Verify DART1's **actual** DMA stream/context mapping, IOVA translation, fault handling and isolation. A logical Apple ADT IOMMU mapper reference is insufficient.
4. Compile and review a distinct **default-off** and RAM-only Linux PCIe S8000 experimental driver with a reliable rollback and no Apple NAND writes. Do not enable DMA bypass or guess registers.
5. Only after a real onboard Broadcom PCIe function enumerates, enable the already cross-compiled ARM64 brcmfmac/cfg80211 stack with correctly licensed board-specific firmware and authenticated remote access.
6. The physical iPhone must show an actual WLAN PHY, join the **same authorized Wi-Fi network** as the Dell, and pass gateway/Dell ICMP tests using `scripts/n71_native_wifi_acceptance.sh`, with no USB relay, forwarding or alias.

**Status: original class-construction and one virtual-method fallback verified offline; S8000 PCIe link and native BCM4350 Wi-Fi remain BLOCKED.** The iPhone continues operating in its existing RAM-booted Linux display/touch/USB configuration.
