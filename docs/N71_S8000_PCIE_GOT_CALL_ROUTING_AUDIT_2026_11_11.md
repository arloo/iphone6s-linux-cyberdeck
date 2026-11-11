# A9 S8000 original PCIe driver: resolved indirect-call map

Date: 2026-11-11. Classification: offline-only, read-only metadata/control-flow classification of a locally obtained iOS 15.8.8 ARM64 prelinked kernelcache. No binary Apple code, VM addresses, disassembly, GOT entries or proprietary function bodies are published.

## Verified call routing

The earlier original Apple firmware audit identified four modules: IOPCIFamily, AppleEmbeddedPCIE, AppleS800xPCIe and AppleS8000PCIe. The specialized S8000 module has only 2,928 bytes of native ARM64 __text instructions.

The new audit found exactly **55 immediate AArch64 BL calls** in the specialized module. Nine call code in the same section. The other 46 target the module's __stubs section, **not their final destinations**. There are 16 twelve-byte trampolines, 14 of which are actually referenced.

Each trampoline uses the verified AArch64 ADRP x16, LDR x16 and BR x16 sequence, which resolves a pointer through the module's __got region mapped within Apple's shared __PLK_DATA_CONST. The pointers are interpreted through the original kernelcache's prelinked executable regions, without publishing any address or executable bytes.

| Resolved destination group | Calls |
|---|---:|
| AppleS8000PCIe itself | 9 |
| AppleS800xPCIe shared controller | 14 |
| AppleEmbeddedPCIE shared controller | 1 |
| IOPCIFamily | 0 |
| Other kernel/extension routines | 31 |
| **Total** | **55** |

This establishes where the direct-call dependencies lead. It does NOT identify the S8000 port reset registers, clock enable order, PHY, PCIe link training, MSI configuration, or a valid DMA stream ID. Indirect BLR/C++ virtual dispatch and other runtime behavior are NOT included in this limited static graph.

## Public reproducibility

New pure-stdlib source: tools/n71_kernelcache_pcie_callgate.py. It works only on an operator-supplied, already decompressed, lawfully obtained private ARM64 Mach-O kernelcache and reuses the previously validated prelink KEXT mapper.

The tool validates the nested KEXT header, code, trampoline and GOT bounds; decodes the AArch64 branch displacement and indirect-call trampoline shape; resolves GOT pointers under strict size constraints; rejects unknown or non-executable targets; and emits ONLY aggregate destination group counts. No code export, file writes, address logging or hardware I/O are performed.

Private invocation:

    python3 tools/n71_kernelcache_pcie_callgate.py /private/path/to/kernelcache.macho

The output includes A9_PCIE_CALLGATE_PASS and HARDWARE_BLOCKED. Twelve synthetic unit tests validate signed AArch64 branch/ADRP decoding, GOT loads, wrong-register rejection, memory bounds, target group classification and absence of code extraction. The raw Apple image, GOT pointers, firmware and disassembly remain in the Dell's private research directory.

Public source for coalesced XNU prelinked segments:
https://github.com/apple/darwin-xnu/blob/main/osfmk/arm64/arm_vm_init.c

The modern Linux Apple PCIe driver is a **different controller family**; its register offsets are not evidence of A9 compatibility:
https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c

**Verified follow-up:** The [six-case A9 original register-offset audit](N71_S8000_PCIE_COMMON_REGISTER_OFFSETS_2026_11_11.md) recovered port1-relative controller offset formulas but NOT an MMIO base or safe register semantics.

## Remaining critical path to true native Wi-Fi

1. Independently identify the hardware semantics and shared/port1 register effects of the relevant S800x/embedded initialization paths, while protecting port0 storage and port2 modem from global reset, clock and PHY operations.
2. Determine and validate the real DART1 stream ID, DMA translation, page tables and IRQ fault handling. The already verified BCM4350-to-mapper-apcie1 logical relation does not establish these.
3. Extend the default-off RFC0011 S8000 kernel guard only with independently reviewed behavior, then stage a distinct supervised RAM-only physical experiment. Preserve the existing functioning Linux LCD+multitouch+USB recovery image.
4. Once an actual PCIe BCM4350 endpoint and safe DMA are operating, deploy the separately built Broadcom WLAN stack with properly licensed and board-matched private firmware/NVRAM and secure authenticated access.
5. Require the strict on-device native-Wi-Fi acceptance script to show wireless PHY, association to the router WLAN and gateway/Dell reachability **over wlan, never USB**.

**The iPhone Wi-Fi is not working yet. No on-device PCIe access occurred in this audit.**
