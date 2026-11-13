# N71/S8000: isolated S5L8960X TTBR/TLB setup and fail-closed DART errors (offline ARM64)

**13 November 2026. Owner's Dell Linux Kbuild only. Status: AArch64 source compilation + synthetic security tests PASS; NEVER booted on the iPhone.**

## Actual engineering milestone

A second, downstream experimental [patch 0015](../experimental/patches/0015-n71-s5l8960x-dart-ios-order-ttbr-tlb-failclosed-offline.patch) has been built on the separately isolated DART source, following [patch 0014](../experimental/patches/0014-n71-s5l8960x-dart-window-and-tcr-lock-offline.patch).

The original [Orchard iommu patch 0006](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0006-iommu-apple-dart-Set-up-S5L8960X-translation-in-iOS-.patch) has 12 implementation hunks. **Nine** applied to the isolated kernel, and **three** required careful manual rebase due to different existing A9 DART functions. The initial compiler error was correctly fail-closed: upstream 0006 also depends on two functions introduced by [Orchard patch 0004](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0004-iommu-apple-dart-Program-the-S5L8960X-error-reflecto.patch). We then implemented the required source-defined register helpers and their **optional, validated Device Tree** property parsing in the same isolated source. No physical Apple register values were guessed.

The new code implements:

| Defense | Source behavior |
|---|---|
| S5L8960X error-reflector and config | Loads `apple,error-reflector`, `apple,fetch-config`, `apple,diag-config` only when present; requires valid 4 KB alignment and representable page number for the reflector |
| S5L8960X translation setup | Disables only the current stream map; checks disabled TCR, sets reflector, writes TTBRs, enables translation, checks enabled TCR, writes configs, invalidates TLB, reads back TTBRs |
| Failure rollback | On error, blocks the affected S5L8960X stream map and records sticky `flush_error` |
| TLB coherency | Propagates invalidation failure through `iotlb_sync_map()` instead of always returning success |
| Future mappings | `map_pages()` rejects maps after a sticky flush error |
| Device attach | Returns translation setup errors instead of falsely reporting a successful attach |
| Existing work retained | Separate packed-TCR spinlock, 4-byte RMW, invalid-window rejection, original N71 pre-MMIO WLAN DART1 activation block |

The exact source-derived TTBR/TCR/invalidator order is checked by an independent [public verifier](../tools/n71_s5l8960x_dart_ttbr_tlb_failclosed_offline_gate.py).

## Actual compile and reproducible provenance

The new code was compiled by the Dell's `aarch64-linux-gnu` cross compiler against the separate Linux kernel source and the previously verified WLAN-enabled Kconfig.

The real output is an **AArch64 ELF64 relocatable** `drivers/iommu/apple-dart.o`:

```text
bytes: 369720
SHA256: af53479fc7b4e19468e180905a0720dff469c26f1a11cb2691e8e857f064edc9
```

The source was audited from two exact owner-private checkpoints:

```text
prior A9 patch-0014 source SHA256:
811c0c4b76e2a47aba9f0ad26dc252d05e61b4164d294ff79d8c0c3b6f0caaa9

post-rebase, patch-0015 source SHA256:
75e2808234541e1424e15ac411c512df5c9cefdab75535bdec469582bbd3e10e
```

The exact [12-hunk patch 0015](../experimental/patches/0015-n71-s5l8960x-dart-ios-order-ttbr-tlb-failclosed-offline.patch) is a byte-for-byte unified source delta between these two checkpoints. Its reversibility passed `git apply --reverse --check` on the isolated branch; no existing source was reverted. The source patch is marked experimental, GPL-2.0-only and attributes upstream Orchard contributors Berkay Kösebay and Henrik Klee.

**Private-only local Kbuild inputs**, not bundled or published:

```text
~/Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-dart-isolated-safety-pre-ttbr-20261113.c
~/Documenti/cyberdeck-a9-linux/worktrees/n71-s8000-dart-isolated-safety-20261113/drivers/iommu/apple-dart.c
~/Documenti/cyberdeck-a9-linux/private-touch-live-test/build-n71-dart-isolated-safety-20261113/drivers/iommu/apple-dart.o
```

The verification command (read-only, host only) is:

```bash
cd ~/Documenti/iphone6s-linux-cyberdeck-public
python3 tools/n71_s5l8960x_dart_ttbr_tlb_failclosed_offline_gate.py \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-dart-isolated-safety-pre-ttbr-20261113.c \
  ~/Documenti/cyberdeck-a9-linux/worktrees/n71-s8000-dart-isolated-safety-20261113/drivers/iommu/apple-dart.c \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/build-n71-dart-isolated-safety-20261113/drivers/iommu/apple-dart.o
```

The [22 adversarial synthetic tests](../tests/test_n71_s5l8960x_dart_ttbr_tlb_failclosed_offline_gate.py) reject loss of error propagation, TCR or TTBR readback, unverified DT configuration, inadvertent alteration of the N71 pre-MMIO block, wrong ELF architecture and an unexpected additional source file. Four expected-failure paths are tested as symbolic failure-state models. **These synthetic models do not emulate a hardware DART, signal races, device power state or PCIe DMA transactions.**

## Mandatory unproven hardware conditions

**The critical all-stream reset problem is NOT solved.** The original `apple_dart_hw_reset()` still constructs a bitmap for **all four stream IDs** and clears all associated TTBRs at probe/remove/resume. Although this experimental code can block domain-owned streams after a failed TLB command, that mechanism alone does **not** guarantee isolation of shared NAND/storage or modem consumers when a DART is probed or reset.

In particular, this branch has **no permission** to activate a DART node on the physical iPhone. The pre-MMIO N71 `0x602008000` WLAN DART1 aperture blocker remains in the driver, ahead of any register mapping. No new enabled functional DART/PCIe node was added to the N71 Device Tree. Actual physical BCM4350 PCIe requester→DART1 SID, stable PCI bus-to-IOMMU ordering, IOVA fault containment and independent NAND/modem reset ownership remain UNPROVEN.

The genuinely booted iPhone remains the **previous** RAM Linux with `cfg80211`, `brcmfmac` and 17 authentic privately staged Apple BCM4350C5 firmware components, Z2 protocol ready and Dell USB uplink. Native PCIe Wi-Fi and DART1 DMA are still blocked. No new phone DFU, reboot, firmware/NAND writes, MMIO access or PCIe probe happened during this work.

## Next high-value gate

Implement and test an **S8000-specific, fail-closed reset/stream-ownership design** that cannot reset unowned streams. Use original Apple source evidence to qualify hardware resource sharing and actual physical requester/SID before any experiment. Only after an independent review may a new RAM-only kernel candidate be considered; a successful standalone object compilation does **not** establish kernel integration, runtime correctness or safe DMA operation.
