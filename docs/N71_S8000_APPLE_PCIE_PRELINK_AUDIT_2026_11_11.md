# Native A9/S8000 PCIe: original Apple kernelcache metadata audit

Date: 2026-11-11. Classification: read-only local research using an operator-supplied iPhone 6s iOS 15.8.8 IPSW. No live PCIe, MMIO, clock, reset, DART DMA, NAND or radio action occurred.

## Original, model-specific evidence

The authorized workstation already contained Apple's iOS 15.8.8 (build 19H422) iPhone 6s IPSW. Only its kernelcache.release.n71 member was extracted to a 0700 private directory. The member is an IM4P DER object of type krnl containing a complzss payload. The Apple header records compressed LZSS bytes and the expected expanded length. A private, bounds-checked LZSS decoder produced a 42,827,776-byte, 64-bit ARM64 Mach-O. **Its Adler-32 checksum exactly matched the checksum in the original Apple header (0x333038f4)**. The binary was NOT executed.

The Mach-O has prelinked-kernel segments including PRELINK_TEXT, PLK_TEXT_EXEC, and PRELINK_INFO. The latter contains metadata for embedded kernel extensions. Parsing the original prelink metadata, recovering each nested KEXT Mach-O header from PRELINK_TEXT, and mapping each KEXT executable's virtual address through the global PLK_TEXT_EXEC segment produced the following validated code ownership:

| Original Apple extension | Native ARM64 __text section size |
|---|---:|
| IOPCIFamily | 90,436 bytes |
| AppleEmbeddedPCIE | 46,924 bytes |
| AppleS800xPCIe | 18,552 bytes |
| AppleS8000PCIe | 2,928 bytes |

The specialized AppleS8000PCIe extension has a real, bounded ARM64 executable section. Its native code was privately decoded to verify the section contains actual AArch64 instructions, NOT misidentified strings or header bytes. All extracted firmware, Mach-O objects, LZSS streams and disassemblies stay private. No proprietary code or binary has been copied to the public Git repository.

**Scope of discovery:** this firmly locates original Apple A9 PCIe driver components for comparison against our proposed S8000 Linux host design. It does not yet prove the register writes, shared resource ownership, power-on ordering, DMA routing or safe port-1 link sequence. A small specialized module does not automatically mean all A9 register behavior is confined to that module; much resides in shared Apple PCIe classes.

The fact that iOS bundles a compatible called apcie,s8000 is independently documented by publicly distributed AppleS8000PCIe.kext metadata:
https://github.com/userlandkernel/ios-unstripped-kexts/blob/96ca2b7f012ab20cf0274ea593d0e9a03f576764/kexts/10.3/s8000/AppleS8000PCIe.kext/Info.plist

## New public reproducibility tool

The public repository adds tools/n71_kernelcache_pcie_kext_map.py, a pure-Python standard-library reader for an already **decompressed** and lawfully obtained private arm64 Mach-O kernelcache. It does not perform IPSW downloads or firmware extraction, and does not export proprietary code.

The tool:
1. Strictly parses Mach-O 64-bit ARM64 headers and bounded LC_SEGMENT_64 commands.
2. Locates the original PRELINK_TEXT, PRELINK_INFO and PLK_TEXT_EXEC segments.
3. Parses only the required KEXT prelink metadata from a size-bounded XML section.
4. Requires exactly the four PCIe-related, explicitly allowlisted Apple extensions.
5. Validates each nested KEXT Mach-O header and resolves its executable section through the MAIN kernelcache's coalesced PLK_TEXT_EXEC **virtual mapping**, not the nested KEXT's unrelated file offset.
6. Returns only module identifiers and section byte counts. It never prints or extracts executable bytes, unknown plist fields, firmware, keys or identifying device data.
7. Prints HARDWARE_BLOCKED because the analysis does not validate live PCIe/DART register operation.

Reproduction (on one's own private, already decoded Mach-O):

    python3 tools/n71_kernelcache_pcie_kext_map.py /private/path/to/kernelcache.macho

For kernelcache format background, see:
https://reverseengineering.wiki/index.php/Format:Kernelcache
https://github.com/apple/darwin-xnu/blob/main/osfmk/arm64/arm_vm_init.c

Nine entirely synthetic Mach-O/prelink tests were added under tests/test_n71_kernelcache_pcie_kext_map.py, covering expected four-module mapping, missing/duplicate modules, incorrect prelink size, wrong executable range, invalid ARM64 header, corrupted prelink XML and no private-value echo or binary export.

**Later analysis:** The [S8000 call-routing audit](N71_S8000_PCIE_GOT_CALL_ROUTING_AUDIT_2026_11_11.md) reconstructs 46 trampoline destinations and 9 direct local calls; this improves the verified dependency map but does not prove a safe PCIe controller initialization sequence.\n\n## Current engineering boundary

The hardware Device Tree reference BCM4350-to-DART1 mapper-apcie1 has already been resolved and published separately. RFC 0011 is a tested, **default-off and deliberately non-probing** S8000 kernel guard. The remaining challenge is a reviewable S8000 PCIe host initialization profile extracted from validated open or clean-room research, with explicit protection of storage port 0 and baseband port 2 and proven DART DMA isolation. The original Apple binary metadata is evidence of component identity, not a Linux driver implementation.

Next: isolate independently reviewable A9 controller register effects, exact DART stream/context semantics and port-1-only link initialization; keep all hardware test gates disabled until code review. **Wi-Fi is not yet functional**. The iPhone continues running the known-good RAM native Linux GUI, USB interface and automatic touchscreen.
