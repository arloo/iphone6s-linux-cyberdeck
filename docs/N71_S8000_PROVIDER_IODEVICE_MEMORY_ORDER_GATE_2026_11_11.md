# N71/S8000 AppleARMIODevice provider resource-order acceptance gate

Date: 2026-11-11. Scope: iPhone 6s N71 Samsung A9. Offline read-only analysis of the privately held original iOS 15.8.8 ARM64 kernelcache and Apple Device Tree. No physical PCIe MMIO, clock/reset, DMA, WLAN operation or reboot.

## Established index formulas, unverified physical provider order

The A9 ROOT PCIe controller's original ARM64 methods compute provider memory-resource indices 0 (configuration), 9 (common root-controller registers), and 10 (supplementary controller/PHY) when the original N71 ADT declares four ports. The eleven original ADT host register tuples independently include:

- reg[0]: 0x610000000, length 0x1000000 (16 MiB), configuration/ECAM CANDIDATE
- reg[9]: 0x600000000, length 0x8000 (32 KiB), common-controller CANDIDATE
- reg[10]: 0x600008000, length 0x4000 (16 KiB), supplementary controller/PHY CANDIDATE

**Not yet established:** that the original AppleARMIODevice runtime IODeviceMemory resource array has exactly the ADT reg-tuple ordering. IOService getDeviceMemoryWithIndex operates on the assigned device memory ranges; that alone does not prove the binary Apple ADT tuple order.

Apple API reference: https://developer.apple.com/documentation/kernel/ioservice/1809999-getdevicememorywithindex

## Implemented strict, offline-only verifier

Public source: tools/n71_s8000_provider_order_gate.py.

- It first validates the private N71 ADT with the existing strict silicon/PCIe/DART consistency gate.
- Without an authentic original-iOS provider IORegistry snapshot, the tool explicitly reports ADT-only PASS, runtime sample missing, provider-order NOT PROVEN and hardware BLOCKED.
- If an independently obtained and sanitized original-iOS provider sample becomes available, the tool compares exactly eleven ordered address/length pairs; it rejects any order difference, duplicate JSON key, unknown extra property, missing/extra range, noncanonical hex, misalignment, zero length, overlap or 64-bit overflow.
- An operator-supplied matching JSON is not independent proof of its own capture provenance. The tool explicitly reports CAPTURE_PROVENANCE_INDEPENDENTLY_AUTHENTICATED=NO and PROVIDER_RUNTIME_ORDER_PROVEN_FROM_TOOL_ALONE=NO even when a sample passes.
- The script prints no original device addresses from the sample, has no hardware APIs, does not copy original firmware or save files, and does not authorize PCIe register accesses.

Existing, real A9 private ADT-only command:

    python3 tools/n71_s8000_provider_order_gate.py /private/n71-adt.bin

Optional future privately captured original-iOS memory-provider sample:

    python3 tools/n71_s8000_provider_order_gate.py /private/n71-adt.bin --ios-provider-snapshot /private/n71-apcie-provider.json

Required sanitized JSON fields, and no others: schema=n71-s8000-ios-provider-ordered-memory-v1, source=operator-captured-original-ios-ioreg, provider_class=AppleARMIODevice, compatible=apcie,s8000, node_path=/arm-io/apcie, and IODeviceMemory as an array of exactly eleven ordered objects holding only address and length canonical lowercase hex strings.

Do NOT create the runtime evidence by copying the ADT. A future capture would require a separately supervised return to original iOS and trusted collection of only the apcie provider memory resource list. Keep raw IORegistry dumps private: other properties can contain personal or per-device identifiers. No original-iOS capture was performed in this stage.

## Synthetic test coverage

25 synthetic regression tests in tests/test_n71_s8000_provider_order_gate.py cover an ordered fabricated array and fail-closed behavior for swaps (including common/PHY and storage/WLAN), absent or excess resources, modified addresses/lengths, overlap, alignment, zero, overflows, malformed identity/source, duplicates, added private fields, oversized data, invalid ADT and absent hardware effects.

These test fixtures use invented addresses deliberately unrelated to the actual N71 layout. Synthetic matching is NOT evidence of Apple runtime mapping.

## Remaining native Wi-Fi gates

1. Independently establish AppleARMIODevice runtime provider-array ordering (or authoritative implementation evidence).
2. Verify functional roles, read/write permissions, cross-port effects and port1-only reset/clock/PHY/MSI/link setup while protecting storage port0 and baseband port2.
3. Verify DART1 physical stream ID, actual IOVA translation, page table format, faults and isolation before any bus-master DMA.
4. Review and opt into a separate default-disabled RAM-only kernel test with known-good Linux GUI/touch/USB rescue and no Apple NAND writes.
5. Enumerate the actual BCM4350, use appropriately licensed board-matched private radio firmware, and pass real on-device WLAN association and LAN reachability independently of USB.

**Result: original private ADT gate PASS; runtime Apple provider memory array unavailable; native BCM4350 Wi-Fi is NOT operational.**
