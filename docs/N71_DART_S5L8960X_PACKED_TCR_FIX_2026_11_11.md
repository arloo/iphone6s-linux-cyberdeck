# N71/S8000 Wi-Fi: S5L8960x DART packed-TCR safety correction

**Date:** 2026-11-11. **Status:** patched C function compiled for AArch64 and exercised in a native-host C register emulator. **NOT qualified for live DART1/PCIe/DMA use.**

## Reproducible software defect

The retained GPL Linux `drivers/iommu/apple-dart.c` extension for `apple,s5l8960x-dart` holds four stream control fields in a **single 32-bit TCR**, each exactly **8 bits wide**. Its legacy `apple_dart_s5l8960x_write_tcr()` read-modify-write sequence previously used these expressions:

```c
tcr &= 0xff << (sid * DART_S5L8960X_TCR_BITS_PER_STREAM);
tcr |= val;
```

This is a defect **independent of unknown S8000 register addresses**. The first line retains only the target byte instead of preserving the *other* three bytes. The second ORs the unshifted stream value into the lowest byte rather than the byte for `sid`.

For an entirely invented original TCR `0xA1B2C3D4`, stream 2 and new byte `0x55`, the old calculation yields `0x00B20055` (wrong stream altered and unrelated fields removed). The correct isolated update is `0xA155C3D4`.

## Patch and verified results

Public source: `experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch`.

**Isolation from established boot series:** this patch deliberately resides in experimental/patches/, NOT the automatic original patches/0001 through patches/0011 sequence. scripts/check_kernel_rfc.sh must continue replaying only the 11 prior source patches. No future iPhone RAM-boot payload may include this DART change implicitly without a separate review.

The patch adds strict `sid` 0..3 and `val` 0..255 validation, calculates `mask = 0xffU << (8*sid)`, writes `tcr = (tcr & ~mask) | ((val << shift) & mask)`, and serializes that entire shared-register read-modify-write using the driver's initialized `dart->lock` with IRQ-safe locking. Invalid reads return 0 rather than using an out-of-range shift.

The public unit test `tests/test_n71_s5l8960x_packed_tcr_fix.py` extracts the **actual patched C function bodies from the published unified patch**, compiles them into a mock-MMIO userspace C harness using `gcc -Wall -Wextra -Werror`, and executes **50,000 deterministic vectors** across all four stream lanes. It verifies preserved neighbor lanes, correct target byte, matching readback, lock pairing and invalid SID/byte rejection. The previous arithmetic is demonstrated to fail.

The patch was applied **only** to a new private, detached source worktree at original Linux commit `68aadac82`. A separate, private cross-build using the original successful A9 kernel configuration compiled the **real** patched `drivers/iommu/apple-dart.o` into an **ELF64 little-endian AArch64 relocatable object**. The known-good Linux touchscreen/display/USB source worktree, kernel image, RAM boot and phone NAND were not modified.

## Separate critical all-stream reset hazard

Even with the packed-TCR correction, the original `apple_dart_hw_reset()` selects **all four streams** of a DART instance, disables their DMA and clears all their TTBR table pointers. This whole-instance reset is currently called from:

- `apple_dart_probe()` — initial driver bind
- `apple_dart_remove()` — driver removal
- `apple_dart_resume()` — power-state resume

The new read-only `tools/n71_s5l8960x_dart_safety_gate.py` verifies those original paths in the **patched private Linux source**, validates the real AArch64 compiled object header, and rechecks the privately retained authentic N71 ADT: dedicated WLAN port 1 topology, unique DART1 mapper, distinct DART windows. It **explicitly returns** `DART1_PHYSICAL_BRINGUP_AUTHORIZED=NO`, because a correct TCR implementation is not evidence of safe reset, real stream ID, IOVA translation, fault containment or DMA isolation. Fifteen additional synthetic tests reject accidental changes in the source/guard, unsupported hardware identifiers and non-ARM64 object formats.

The Linux driver family in this private source includes an `apple,s5l8960x-dart` extension; do not assume that upstream Apple M-series DART implementations prove correct registers on this Samsung A9. The original Apple ADT's `dart,s5l8960x` compatibility fallback is helpful metadata, not a register-level contract.

## Offline reproduction

```bash
# C-model tests (no device)
python3 -m unittest discover -s tests -p 'test_n71_s5l8960x_packed_tcr_fix.py' -v

# Offline-only gate using operator-held private A9 source, ADT, object
python3 tools/n71_s5l8960x_dart_safety_gate.py \
  /private/patched-linux/drivers/iommu/apple-dart.c \
  /private/original-n71-adt.bin \
  /private/arm64-build/drivers/iommu/apple-dart.o
```

**Hardware activation remains prohibited** until root PCIe resource ordering, port1-only power/refclock/PERST#/link, physical DART1 stream assignment, correct IOVA/page tables and DMA isolation are separately verified. Neither a kernel boot, device probe nor module insertion occurred. The real iPhone USB link is still inaccessible.
