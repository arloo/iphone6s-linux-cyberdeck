# RFC 0011 — Samsung A9/S8000 PCIe safety guard (kernel source)

Date: 2026-11-11. **Offline compilation PASS; hardware probing DISABLED.** This is NOT a Wi-Fi driver. The phone still boots the previous RAM-only Linux with proven LCD and automatic two-finger touch; no new hardware experiment occurred.

## Rationale and scope

Previous S8000 private-ADT audits mapped the BCM4350 to PCIe bridge 1 with two 16-KiB controller windows and a physically separate DART1 window. Storage uses PCIe port 0, baseband port 2. While all port windows are disjoint, global power/clock/reset/MSI registers and WLAN DMA stream semantics remain unverified. Therefore even a seemingly safe port-1-only DT is not yet suitable for hardware testing.

Published RFC 0011 adds a separate kernel build option CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD (tristate, default n), a Kbuild target, and new pcie-apple-s8000-guard.c. The guard includes fixed physical address metadata for only port1 and DART1, explicit forbidden ranges for storage, modem, unknown port and global controller windows, and an overflow-checked intersection test. It accepts the exact N71+S8000 root compatibles only and has an intentionally synthetic match string apple,s8000-pcie-research-blocked, absent from any booted DT.

Even when that synthetic compatible is deliberately supplied, the module's probe ALWAYS returns -EOPNOTSUPP. It never calls ioremap/readl/writel, IRQ, clock, GPIO, regulator, DMA, IOMMU or PCI host initialization APIs. It performs no PCI enumeration, RF or NAND operations. This guard is a source-code and integration policy baseline, not functioning radio support.

## Offline build and code-review evidence

An initial compilation through an older out-of-tree Kconfig configuration entered an interactive syncconfig prompt; only that blocked compiler process was terminated. A fresh isolated output directory then completed ARM64 olddefconfig/prepare with CONFIG_PCIE_APPLE_S8000_RESEARCH_GUARD=y specifically for OFFLINE compilation. The compiled kernel object is a 64-bit AArch64 relocatable ELF. Its unresolved imports are limited to platform registration/unregistration, board-compatible predicate, warning and compiler stack check—not MMIO, clock, reset, DMA, IOMMU, IRQ or PCI host functions.

All eleven RFC patches applied sequentially to the exact pinned clean HoolockLinux commit, with the final source, Kconfig and Makefile identical to the private development tree. A **separate independent run** of scripts/check_kernel_rfc.sh then replayed RFC 0001 through 0011 and compiled THREE standalone AArch64 kernel objects successfully: Apple touch clock, Apple Z2 touchscreen and the PCIe S8000 safety guard. The compiled guard imports no MMIO, clock, reset, DMA, IOMMU, IRQ or PCIe host APIs.

That full replay uncovered and fixed a shell brace-expansion bug in the previous public test script: 000{1,...,10} incorrectly expanded the tenth patch to 00010 instead of 0010. The corrected expression 00{01..11} now includes patches 0010 and 0011. An automated regression test checks the exact eleven patch prefixes and compiled guard target.

Eight new public synthetic guard tests verify default-off config, exact board guard, rejection code, register whitelist/denylist, lack of hardware side effects, absence of private firmware or identifiers, no boot-time DT changes and the correct replay script. **All these are OFFLINE gates only, not hardware qualification.**

## External research leads

The Apple iOS KEXT metadata references an AppleS8000PCIe driver bound to apcie,s8000. That identifies a real Apple-specific host software family, but does NOT provide a Linux driver or its register semantics.

- https://github.com/userlandkernel/ios-unstripped-kexts/blob/96ca2b7f012ab20cf0274ea593d0e9a03f576764/kexts/10.3/s8000/AppleS8000PCIe.kext/Info.plist
- https://github.com/OrchardLinux/orchard (S8000 device support research, not a qualified PCIe driver)
- https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c (T8103/T602x comparison; do not copy its offsets to A9)

## Required next qualifications

1. Independently derive S8000 global and port1 PHY/refclock, reset, MSI and link-training register semantics; ensure no indirect effect on storage port0 or modem port2.
2. Resolve the DART1 IOMMU parent and actual DMA stream assignment, page-table format, fault and domain isolation before any bus-master access. Never allow bypass as a shortcut.
3. Extend the guarded driver by a separately reviewed opt-in feature only after the exact A9 register model is proven; first boot from a new supervised RAM-only image, with the current GUI/touch image as rollback.
4. After PCIe link+IOMMU validation and safe enumeration, integrate cfg80211/brcmfmac with private N71 USI firmware/NVRAM; require authenticated SSH before opening independent Wi-Fi networking.

**Outcome:** repeatable ARM64 driver integration with a non-probing security envelope. NO active WLAN, PCIe link training or new live iPhone testing.
