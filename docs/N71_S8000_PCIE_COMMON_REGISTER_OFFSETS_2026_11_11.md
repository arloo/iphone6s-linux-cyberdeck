# N71/S8000 original Apple PCIe common-register offset audit

**Date:** 2026-11-11. Offline STATIC code analysis of the operator's private iPhone 6s iOS 15.8.8 ARM64 kernelcache. No on-device PCIe, MMIO, clock, PHY, reset, DMA, or radio operation was attempted.

## Verified six-case A9 register selector

The real original AppleS8000PCIe specialized kernel extension contains a function selecting among six common-register IDs, checking both the supplied PCIe port index against the number of ports and the register ID against the range 0..5. Its signed jump table dispatches to these statically verified offset formulas:

| ID | Relative offset formula | Port1 result |
|---|---|---|
| 0 | fixed 0x24 (shared/global) | 0x24 |
| 1 | fixed 0x2C (shared/global) | 0x2C |
| 2 | 0x100 + port_index * 0x80 | **0x180** |
| 3 | 0x114 + port_index * 0x80 | **0x194** |
| 4 | 0x124 + port_index * 0x80 | **0x1A4** |
| 5 | 0x12C + port_index * 0x80 | **0x1AC** |

**New root-class mapping evidence:** [The verified S8000 root startup audit](N71_S8000_ROOT_START_RESOURCE_INDEX_2026_11_11.md) shows that the original common-register selectors produce provider resource indices **9** and **10**, corresponding conditionally to ADT reg[9]/reg[10]. This does NOT prove provider ADT order, register semantics or safe MMIO access. The former index-zero PHY inference was incorrect.

These are the first independently decoded A9/S8000-specific register offset formulas in this project. They are NOT full physical register addresses. The actual common-controller MMIO base and numerical ID meanings remain unverified. Port1 offsets alone do not establish safe read/write behavior. Particularly, IDs 0 and 1 are global/shared offsets and are off-limits until their effects on storage port0 and baseband port2 are established.

The private original KEXT also names separate PCIe PHY and APCIe common mapping paths; the current evidence does not establish the exact relation between those paths and the two global PCIe regions recorded in the ADT, or any PHY/reference-clock sequencing.

## Public, reproducible and fail-closed analysis

New read-only Python 3 tool: tools/n71_s8000_common_reg_audit.py. Run only against your own private, already decompressed ARM64 iOS 15.8.8/19H422 Mach-O:

    python3 tools/n71_s8000_common_reg_audit.py /private/path/to/kernelcache.macho

The tool locates the A9 original KEXT from verified prelink metadata, validates bounded code size and the exact six-case selector structure, port and register-index safety checks, signed jump table, AArch64 MOVZ/LSL/ADD patterns and common return instruction. It only outputs derived register offset formulas and HARDWARE_BLOCKED; no Apple code, firmware, raw disassembly, private identifiers or binary file bytes are exported. Unexpected firmware versions and modified instruction/data structures fail closed.

Fourteen fully synthetic tests in tests/test_n71_s8000_common_reg_audit.py validate positive formula decoding, changed bounds guards, wrong argument register, altered jump targets, changed port stride/offsets, truncation, missing epilogue and no live hardware/binary-export functions. The private Apple image was independently checked against this tool and passed.

The previous original S8000 GOT/callgraph audit showed 14 direct calls into the shared AppleS800xPCIe module across five distinct branch destination addresses (call multiplicities 6/5/1/1/1). Those addresses have NOT been independently established as callable hardware initialization functions, and C++ virtual calls are outside that earlier limited direct-call graph.

**Historical selector trace:** [The corrected PHY selector audit](N71_S8000_PCIE_PHY_RESOURCE_INDEX_2026_11_11.md) checks an argument-zero call, whose returned mapped resource index is **10** in the actual S8000 root class. It does NOT justify adding these relative offsets to a physical address or activating a controller.\n\n## Remaining strict bring-up gates

1. Establish exact A9 common MMIO region and functional names, bitfields, read/write permissions and global side effects for each numeric ID.
2. Determine safe port1-only root-complex, PHY/refclock, reset and link training ordering while proving storage0/baseband2 isolation, including global controller changes.
3. Verify hardware DART1 stream ID, IOVA/page tables, DMA translation and fault handling. The already resolved Apple ADT logical BCM4350-to-DART1 mapper relation is not proof of DMA safety.
4. Extend the deliberately inert default-off S8000 Linux RFC0011 only once those prerequisites are reviewed; use a separate supervised RAM-only candidate without modifying NAND or the known-good Linux GUI/touch payload.
5. Then enumerate a genuine BCM4350 PCIe endpoint, deploy the independently cross-compiled ARM64 Broadcom WLAN components and securely provision compatible private firmware/NVRAM.
6. Require direct association of the iPhone's own WLAN PHY to the Dell's authorized wireless network and the on-device native Wi-Fi-only gateway/Dell acceptance test. USB is not accepted as a radio test.

**No functioning native Wi-Fi is claimed or demonstrated at this stage.**
