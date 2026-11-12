# N71/S8000 iPhone 6s: genuine Linux AArch64 DART1 fail-closed pre-MMIO guard

**Date:** 2026-11-12. **Hardware target:** N71 Samsung A9/S8000, owner-controlled original iPhone 6s, BCM4350 Wi-Fi under original Apple PCIe port1 and dedicated DART1. **Milestone:** the real Hoolock-derived Linux `drivers/iommu/apple-dart.c` now has **both** the proven 4-lane S5L8960x TCR RMW correction and an explicit **pre-MMIO fail-closed guard** for the N71 WLAN DART1 physical aperture. This code compiled as an actual ELF64/AArch64 relocatable **kernel object** in the separate private Dell Linux build tree. It was **not** linked to the unchanged known-good RAM recovery image or booted on the iPhone.

## Why this guard matters

The original S5L8960x Apple DART IOMMU Linux driver has two distinct issues in its original source:

1. Its 32-bit packed translation-control register (`TCR`) stores four 8-bit stream lanes. The unmodified `apple_dart_s5l8960x_write_tcr` masked off **all other lanes** and failed to shift the new byte into the selected lane. Applying the separately audited public [0012 packed TCR correction](../experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch) fixes this in a serialised, bounded `spin_lock_irqsave` RMW. The C implementation has already passed 50,000 adversarial synthetic vectors and was independently compiled against the original Linux AArch64 kernel tree.
2. On probe, the same original Linux DART code calls `apple_dart_hw_reset()`, which disables DMA for **every stream of the probed instance**, clears all TTBR page tables, handles error state and may manipulate clocks/IRQs. The original physical BCM4350 PCIe requester-to-DART1 hardware SID, exact TTBR/IOVA/fault domain and port1 link reset order have **not** been proven. Therefore fixing the packed TCR byte update **does not make a DART1 probe safe**.

The new [0013 N71/S8000 pre-MMIO guard](../experimental/patches/0013-n71-s8000-dart1-pre-mmio-wlan-probe-guard.patch) addresses the second problem by explicitly refusing the dedicated *WLAN DART1 instance* **before the first allocation, device-register mapping, clock, reset, DMA, TTBR, interrupt or state-changing operation**.

## Precise protection policy

The source uses only the kernel `of_machine_is_compatible()` board metadata and `platform_get_resource(pdev,IORESOURCE_MEM,0)` to examine a **resource descriptor**, not the physical device.

Only when **both** `apple,n71` and `apple,s8000` identify the real board, it rejects:

- Any nonempty resource range with `start <= 0x60200BFFF` and `end >= 0x602008000`, covering **every partial or complete overlap** with the original dedicated 16-KiB DART1 controller window.
- Any malformed resource descriptor whose `end < start`, since such a range must not reach a hardware mapping.
- The probe then prints a generic kernel warning and returns `-EOPNOTSUPP`.

The new guard is placed at the **very beginning of `apple_dart_probe()`**, before `devm_kzalloc` and (critically) **before `devm_platform_get_and_ioremap_resource`**. This limits the change to the owner-verified N71/S8000 DART1 physical aperture; unrelated DART instances do not match this hardware window. If the guard does not match, the original driver logic is unchanged (including its existing whole-instance reset behavior). Therefore this is a **targeted risk reduction**, not a generalized assertion that all DART probes are safe.

The original N71 Apple Device Tree and [live Apple iOS DART1 evidence](N71_S8000_UNLOCKED_IOS_LIVE_DART1_PCIE_PORT1_2026_11_12.md) established the controller window, the unique declared WLAN mapper index 0, and the correct Apple driver class. The [original ARM64 mapper-to-packed-TCR lane proof](N71_ORIGINAL_APPLE_DART1_MAPPER_TCR_LANE_2026_11_12.md) independently verified the logical lane0 software route, but **not the physical PCIe transaction-to-SID route**.

## Reproducible patch chain

The new patch is deliberately separate and **applies only after** patch 0012:

```bash
# ONLY in a disposable, nonbooted Hoolock Linux test tree:
patch -p1 < experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch
patch -p1 < experimental/patches/0013-n71-s8000-dart1-pre-mmio-wlan-probe-guard.patch

# Compile the Linux driver with an isolated ARM64 O= build directory:
make -C /private/linux-worktree O=/private/arm64-build \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  drivers/iommu/apple-dart.o
```

The owner already applied both patches to the separate **experimental** Linux worktree, and a reproduction test confirmed that patch 0013 applied to an independent copy of the previously fixed 0012 source yields a byte-for-byte identical driver. The built object was inspected with `file` and reported `ELF 64-bit LSB relocatable, ARM aarch64`.

The previous dedicated experimental DART worktree still has only the original 0012 TCR correction and was used as the comparison input. The original known-good, separate RAM-only touchscreen/LCD/USB boot bundle remains unchanged.

## Real executable C safety test

`tests/test_n71_dart1_pre_mmio_probe_guard.py` extracts the **exact original C function implementation** from the newly published 0013 unified diff, adds fake in-memory `platform_device`, `struct resource`, `of_machine_is_compatible`, `platform_get_resource` implementations and compiles that real C with `gcc -O2 -Wall -Wextra -Werror -std=c11`. It runs **50,018 synthetic resource vectors**, including 50,000 randomized bounds, source start/end boundary cases, one-byte intersections, accidental exposure of other ports, false board identities, missing resources and malformed/overflowing descriptors. Every scenario is checked against an independent policy oracle. Eleven additional Python unit checks verify the C guard's source order, code boundaries, absent hardware APIs and published patch ordering. Separately, the original 0012 executable C TCR test still passes its **50,000** synthetic stream-update vectors.

Reproduce in the public repo, without private files or hardware:

```bash
python3 -m unittest discover -s tests \
  -p test_n71_dart1_pre_mmio_probe_guard.py -v

python3 -m unittest discover -s tests \
  -p test_n71_s5l8960x_packed_tcr_fix.py -v
```

## Critical remaining dependencies before native Wi-Fi

**Not yet safe for Linux Wi-Fi operation:** original S8000 PCIe root bit4 electrical meaning, true PHY/refclock/PERST#/MSI sequencing and shared cross-port effects; BCM4350 requester-to-**hardware** DART1 SID routing, stream TTBR and IOVA table format, valid DMA mappings, isolation, exception/fault handling and bounded rollback. The Apple code's 100-microsecond REFCLK/PERST parameter and 10-microsecond shared-status retry were separately proven from genuine XNU `_IODelay`, but correct timing alone does not qualify hardware initialization.

The 0013 guard is designed to be **removed or explicitly reworked only after those physical dependencies are independently qualified**, and never as an arbitrary workaround. Its existence prevents the experimental kernel from inadvertently reaching original all-stream DART1 reset through a routine device-tree auto-probe.

No on-device Linux PCIe or WLAN probe, Wi-Fi association, GPIO/PMIC change, live shared MMIO, DART1 DMA, Apple NAND write, DFU, iOS reboot or known-good RAM image modification was performed during this milestone. **Native onboard Wi-Fi under Linux is still not operational.**
