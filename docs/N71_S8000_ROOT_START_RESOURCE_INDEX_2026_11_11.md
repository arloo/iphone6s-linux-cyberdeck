# N71/S8000 root PCIe: correct constructor, startup and memory-resource indices

**2026-11-12 updated evidence:** [Direct live IODeviceMemory verification](N71_IOS_LIVE_IODEVICEMEMORY_ORDER_2026_11_12.md) on the real N71 running iOS 15.7.9 establishes an exact 11/11 ordered match with the independently validated ADT. The old provider-order uncertainty is resolved, but hardware register safety, port1 reset/PHY and DART DMA remain unverified.

Date: 2026-11-11. Research class: OFFLINE, read-only analysis of the operator's locally held original iOS 15.8.8 N71 ARM64 kernelcache and private Apple ADT. The physical Linux iPhone was NOT modified.

## Hardware class distinction

Original Apple IOKit KEXT registration strings distinguish TWO different inheritance chains:

- ROOT controller: AppleEmbeddedPCIE -> AppleS800xPCIe -> AppleS8000PCIe.
- PORT object: AppleEmbeddedPCIEPort -> AppleS800xPCIePort -> AppleS8000PCIePort.

The previous four-vtable-slot [port override analysis](N71_S8000_CONSTRUCTOR_CHAIN_PORT3_OVERRIDE_2026_11_11.md) was mistakenly described as a root controller analysis. Its port-specific discovery remains valid, but its root class attribution was incorrect and has now been corrected.

## Verified ROOT startup and resource-index selection

Independent original ARM64 constructor BL/stub/GOT analysis proves the ROOT constructor chaining from the specialized S8000 root into the S800x root and finally the Embedded root, each installing its own class instance vtable.

The constructed S8000 ROOT vtable has:
- Virtual slot **688** inherited from S800x, with an original S800x start method. Its static parent-vtable call resolves exactly to the original AppleEmbeddedPCIE root start method.
- Virtual slot **1496** overridden with S8000-specific root configuration code.
- Virtual slots **1856**, **1880** and **1888** for resource-index calculations, with the methods listed below.
- Virtual slot **2016** for the separately validated original A9-specific six-case common register offset selector.

Crucially, a zero passed by the S8000 configuration routine as an ARGUMENT to the root virtual selector 1888 is not the memory resource number selected by its returned value.

## Three verified index formulas and matching original ADT tuples

| Root mapping role | Original ARM64-return formula | Index with four ports | Ordered N71 ADT range candidate |
|---|---|---:|---|
| Configuration / ECAM | constant zero from Embedded slot 1856 | **0** | reg[0]: 0x610000000 / 0x1000000 |
| Common root-controller registers | 1 + 2 * port count, S800x slot 1880 | **9** | reg[9]: 0x600000000 / 0x8000 |
| Additional S8000 PHY/common mapping | 2 + 2 * port count + selector argument, S800x slot 1888 | **10**, selector argument 0 | reg[10]: 0x600008000 / 0x4000 |

The privately verified S8000 ADT declares **four ports** and exactly **eleven** host PCIe reg tuples. The original S8000 root configuration calls slot 1888 with argument zero, passes its returned resource number to the provider's indexed memory-map call, and stores the result as its additional root mapping. That selector returns **10**, NOT 0.

**Boundary:** the original index formulas and ADT tuple order are verified separately. To identify an address as a definitive hardware MMIO base, the ordering of IODeviceMemory resources exposed by AppleARMIODevice must still be demonstrated to match the ADT reg tuple order. The three addresses are currently **conditional physical candidates**, NOT authorization to read/write any MMIO register. No clock/reset sequencing, register semantics, PCIe enumeration, IRQ/MSI behavior or DART DMA isolation has been verified.

## Reproducible public source

New offline tool: tools/n71_s8000_root_resource_gate.py. It validates the original ROOT constructor chain, static S800x-to-Embedded parent start call, root vtables, exact AArch64 resource-index formulas, S8000 argument-0 selector-to-provider mapping, and the original private N71 ADT (including #ports=4, all 11 ranges and unique DART1 mapper reference).

Private local command:

    python3 tools/n71_s8000_root_resource_gate.py /private/kernelcache.macho /private/n71-adt.bin

Successful output includes:

    N71_S8000_ROOT_START_AND_RESOURCE_FORMULAS_STATIC_PASS
    RESOURCE CONFIG INDEX 0 ...
    RESOURCE COMMON INDEX 9 ...
    RESOURCE PHY INDEX 10 ...
    ADT_RESOURCE_ORDER_EQUALS_PROVIDER_ORDER_PROVEN=NO
    S8000_PORT1_CLOCK_RESET_DART1_DMA_VERIFIED=NO
    HARDWARE_BLOCKED

Nineteen fully synthetic tests under tests/test_n71_s8000_root_resource_gate.py check ARM64 loads, original selector arithmetic, rejected alternate target slots, wrong parent method/argument, invalid hardware layout and no executable export/hardware APIs. No Apple IPSW/kernelcache, raw private ADT, firmware, calibration or per-device secrets are published.

## Remaining high-priority Wi-Fi gates

1. Verify actual provider IODeviceMemory resource ordering and S8000 root-register bitfields; no guessed global register writes.
2. Determine safe port1-only power, clocks, PHY, reset, MSI and PCIe link-training order; protect port0 storage, port2 modem, unknown port3 and global root state.
3. Validate actual DART1 stream ID, translation, IOVA tables, DMA faults and isolation before any bus-master operation.
4. Extend the default-off S8000 kernel research guard only with reviewed evidence, in a separate supervised RAM-only boot preserving Linux LCD, multitouch and USB recovery; NEVER modify Apple NAND.
5. After a real PCIe BCM4350 endpoint enumerates, load legitimate, board-matched private firmware and N71 Wi-Fi calibration with Linux brcmfmac/cfg80211. Firmware documented for iPhone 7 BCM4355 is NOT interchangeable.
6. Pass the native on-device WLAN PHY-only acceptance test: association to the authorized Dell access point and gateway/Dell connectivity OVER WI-FI, not USB forwarding.

Physical result: native iPhone 6s BCM4350 Wi-Fi is NOT yet operational. No PCIe MMIO or DART hardware operation was attempted in this stage.
