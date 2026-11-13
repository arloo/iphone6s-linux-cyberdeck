# S8000/N71 Apple S5L8960X DART: isolated DMA window + TCR lock hardening

**13 November 2026. Scope: successful AArch64 cross-compilation and synthetic validation on the owner Dell. No device installation or real PCIe/DMA test.**

## Actual milestone

An independent Linux kernel source worktree and independent Kbuild output were created on the owner's Dell without changing the kernel that the iPhone 6s is currently running.

The source starts with the project's **previously physically booted kernel lineage**, including the independently verified packed S5L8960X four-stream TCR read-modify-write fix, A9 DMA-window parser and all prior safeguards. One further **isolated, four-hunk experimental patch** was generated and reviewed:

[0014-n71-s5l8960x-dart-window-and-tcr-lock-offline.patch](../experimental/patches/0014-n71-s5l8960x-dart-window-and-tcr-lock-offline.patch)

### Modification A: base-aligned A9 DART DMA windows only

The S5L8960X page-table indexing uses an IOVA mask derived from its window base. Masking is equivalent to subtracting the base only when the window's span is smaller than the least-significant set bit of the nonzero base. A misaligned window can silently map the wrong page. The [Orchard upstream alignment defense](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0005-iommu-apple-dart-Refuse-S5L8960X-DMA-windows-that-ar.patch) is integrated in the **isolated** domain finalization path: for the legacy S5L8960X only, nonzero base and a span at least as large as its lowest set bit return `-EINVAL` before page-table setup.

The original reference aperture `0x80000000–0xBBFFFFFF` is allowed, and an unaligned example `0x90000000–0xCFFFF000` is rejected by synthetic code and the source predicate. This is an **offline arithmetic check**, not the address of a successfully tested physical BCM4350 DMA channel.

### Modification B: dedicated spinlock for the four packed TCR stream bytes

The existing project driver has a corrected packed-byte RMW with range checks and the original shared DART command lock. The [Orchard packed-stream serialization patch](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0007-iommu-apple-dart-Serialize-S5L8960X-stream-control-u.patch) highlights that using the command lock for TCR operations is a possible reentrant locking problem. We preserve our already-proven byte mask and 4-stream bounds and move **only the TCR RMW** to a separate `dart->tcr_lock`, initialized during platform probe. The original `dart->lock` stays in the command paths unchanged.

A synthetic reference model updates only the selected 8-bit lane out of a 32-bit word; adjacent lanes are byte-identical. This does not establish that real DART MMIO is safe to access.

## Reproducible build and proof

The isolated source is held privately at:

```text
~/Documenti/cyberdeck-a9-linux/worktrees/n71-s8000-dart-isolated-safety-20261113
```

The isolated build retained the known-good radio-enabled Kconfig, which already has `CONFIG_APPLE_DART=y`. The Dell cross-compiled the actual `drivers/iommu/apple-dart.o` as a valid **64-bit AArch64 ELF relocatable** object, 350,112 bytes; SHA-256:

```text
42b26b217d230e388bd7883219a10d3888b2a23d742d88b246c709ff1aee40f2
```

The [public exact four-hunk source-delta and AArch64 ELF verifier](../tools/n71_s5l8960x_dart_window_tcr_offline_gate.py) requires the actual prior owner kernel source, isolated new source and real cross-compiled `apple-dart.o`. It cross-checks that:

- The exact diff between the two sources **equals this published patch**, without hidden code changes.
- The new standalone packed TCR lock is declared, used around the RMW and initialized in probe.
- The legacy-only DMA base-alignment check refuses invalid regions with `-EINVAL`.
- The generated ELF header is an **ARM64 relocatable object**, not a host x86-64 object or fabricated text file.
- It does **not** claim any of this proves on-device IOMMU function or BCM4350 PCIe enumeration.

The [15 adversarial public tests](../tests/test_n71_s5l8960x_dart_window_tcr_offline_gate.py) verify boundary cases and malformed 64-bit IOVA windows, all four TCR stream bytes, invalid inputs, host-ELF rejection and **50,000 deterministic synthetic four-stream RMW vectors**. The full public project regression suite must pass independently before publishing.

For an authorized reproducibility run after separately preparing the existing Linux Kbuild source and isolated output:

```bash
cd ~/Documenti/iphone6s-linux-cyberdeck-public
python3 tools/n71_s5l8960x_dart_window_tcr_offline_gate.py \
  ~/Documenti/cyberdeck-a9-linux/worktrees/touch-s8000-cal-ack-next/drivers/iommu/apple-dart.c \
  ~/Documenti/cyberdeck-a9-linux/worktrees/n71-s8000-dart-isolated-safety-20261113/drivers/iommu/apple-dart.c \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/build-n71-dart-isolated-safety-20261113/drivers/iommu/apple-dart.o
```

This reads local code and the ARM64 object; it does not load the module, reboot the phone or write any physical registers.

## Remaining critical blockers — do not bypass

**This patch does NOT solve the larger DART reset problem.** The existing Apple DART Linux driver may reset **all four streams**, clear TTBRs and disable DMA during probe, remove or resume. Such an operation could disturb unrelated storage or baseband owners if shared hardware isolation is unproven. Correct physical BCM4350 PCIe requester-to-DART1 SID, IOVA fault containment, and a safe per-port S8000 PCIe root are still not established.

The more ambitious [Orchard iOS-order translation + fail-closed mapping patch 0006](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0006-iommu-apple-dart-Set-up-S5L8960X-translation-in-iOS-.patch) is **not yet compatible directly** with the project's already modified source and requires a separate controlled rebase/compile review; it was **not** applied here. No S8003 `phy-ip`, bus-numbering assumptions, SID, NVMMU writes or cross-port shared-root tuning were imported.

**On-device status:** the real iPhone 6s remains in the previously physically verified RAM Linux with `cfg80211`, `brcmfmac`, original C5 firmware, Z2 touch protocol ready and USB gadget present. **Zero native PCIe endpoints and zero WLAN interfaces** remain the most recent verification. No DFU, new image, real DART access, NAND or modem side effects occurred during this offline build.

**Next step:** independently qualify the existing all-stream-reset path, the original Apple A9 DART1 hardware stream ID and the requester-to-DART1 relationship, then adapt the fail-closed translation order in an isolated build. Only after that may a separate supervised RAM boot test be considered. Neither this patch nor cross-compilation alone authorizes physical DMA.
