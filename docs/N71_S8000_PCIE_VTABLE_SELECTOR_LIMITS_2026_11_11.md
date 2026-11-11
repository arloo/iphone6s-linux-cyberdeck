# A9/S8000 PCIe — MetaClass vtable selector audit (corrected)

**IMPORTANT CORRECTION:** [The later actual instance-constructor audit](N71_S8000_CONSTRUCTOR_CHAIN_PORT3_OVERRIDE_2026_11_11.md) proves that the zero/unsupported return values below came from the **MetaClass constructor's vtable**, NOT from the constructed S8000 PCIe instance. The two instance selector slots are instead inherited from S800x. Never use the historical MetaClass table to infer a hardware resource index.

**Date:** 2026-11-11. Offline static study of a locally held iOS 15.8.8/19H422 N71 ARM64 prelinked kernelcache. No live PCIe/MMIO, DMA, PHY, reset, Wi-Fi or NAND operation.

## New original Apple code evidence

In the original AppleEmbeddedPCIE startup, two indirect calls use virtual slots at offsets 1856 and 1880 and feed their results into provider memory-resource mapping calls. The prior audit correctly detected two **dynamic selectors** but did NOT establish the runtime receiver object or those selectors' numerical resource indices.

The AppleS8000PCIe **MetaClass** constructor assigns a class-metadata vtable using a bounded AArch64 ADRP/ADD/STR sequence. The shared AppleS800xPCIe **MetaClass** constructor assigns a different metadata vtable. Resolving the two virtual slots through original prelinked constant data and the allowlisted original executable module ranges yields:

| Original **MetaClass** constructor | Virtual slot 1856 | Virtual slot 1880 |
|---|---|---|
| AppleS8000PCIe | Returns zero | Returns 0xE00002C7 |
| AppleS800xPCIe | Nontrivial method | Nontrivial method |

0xE00002C7 is Apple's documented kIOReturnUnsupported status:
https://developer.apple.com/documentation/iokit/kioreturnunsupported
https://leopard-adc.pepas.com/documentation/Darwin/Reference/IOKit/IOReturn_h/index.html

The two S8000 **MetaClass** slot targets are in original IOPCIFamily executable code. These are not the constructed instance's virtual-method slots and are **not proof of the receiver's actual vtable during AppleEmbeddedPCIE startup**. An unsupported return cannot safely be used as a physical resource index. The correct runtime dispatch chain and any subclass overrides must be established before identifying either common MMIO window.

This means the ADT common ranges at 0x600000000/0x8000 and 0x600008000/0x4000 remain unassigned to these virtual selectors. The earlier port1-relative offsets (0x180,0x194,0x1a4,0x1ac) may NOT be added to either base. The index-zero PHY path remains a separate observation; ADT reg[0]=0x610000000/0x1000000 is still a candidate only because provider IODeviceMemory ordering is unproven.

## Public read-only verification

Tool: tools/n71_s8000_vtable_selector_audit.py

It decodes only the generic ARM64 MetaClass-vtable address computation (ADRP/ADD/STR), separately verifies instance-constructor pointers, validates original private vtable slots, bounds-checks all pointers against prelinked data/executable sections, and classifies only exact constant-return patterns. It never outputs executable code, original pointers, disassembly or per-device data. Twelve entirely synthetic tests verify signed address arithmetic, modified register/store rejection, zero and unsupported status classification, malformed input and zero hardware effects.

Local invocation on privately obtained and already decompressed firmware:

    python3 tools/n71_s8000_vtable_selector_audit.py /private/kernelcache.macho

The output deliberately includes RUNTIME_DISPATCH_OBJECT_PROVEN=NO, COMMON_MMIO_RESOURCE_INDEX_RESOLVED=NO, and HARDWARE_BLOCKED.

**Later source-flow verification:** [The A9 startup receiver provenance audit](N71_S8000_START_RECEIVER_PROVENANCE_2026_11_11.md) verifies X19=controller/self versus X20=separate provider at both mapping callsites, and the intended S8000 class/personality. It does NOT prove the active runtime vtable or numerical common-register indices.

## Hardware-blocking prerequisites

1. Identify the **actual runtime receiver** for each AppleEmbeddedPCIE virtual-selector call, including inheritance, constructor chaining and overrides.
2. Establish provider memory-range ordering versus the original Apple ADT and identify functional common controller register base/bitfields.
3. Independently validate A9 port1-only PHY/refclock, clocks, reset, MSI and link training while excluding cross-port impact on storage0/baseband2.
4. Verify actual DART1 SID, page tables, DMA isolation/fault handling. Do not bypass the IOMMU.
5. Only then stage a separately reviewed, supervised RAM-only Linux hardware bring-up and enumerate the onboard BCM4350. Preserve existing LCD/touch/USB fallback and never alter NAND.
6. After authenticating device access and supplying licensed board-correct radio firmware, require an **iPhone wlan PHY** association to the authorized Dell Wi-Fi and gateway/Dell WLAN-only acceptance test. USB tethering is not a pass.

**Native iPhone BCM4350 Wi-Fi is not yet operational.**
