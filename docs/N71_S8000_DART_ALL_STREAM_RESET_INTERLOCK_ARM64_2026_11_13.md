# N71 Samsung S8000: all-stream DART reset interlock (offline ARM64)

**13 November 2026. Status: source compiled for ARM64, independent exact-patch and synthetic policy gate PASS. The code was NOT booted on an iPhone.**

## Why another guard is necessary

Inspecting the kernel source revealed that `apple_dart_hw_reset()` builds a **full stream bitmap** with `bitmap_set(stream_map.sidmap, 0, dart->num_streams)` and subsequently calls both `apple_dart_hw_disable_dma(&stream_map)` and `apple_dart_hw_clear_all_ttbrs(&stream_map)`. On S5L8960X this covers all **four stream IDs** of the targeted DART instance, regardless of which device owns them.

The function is called during **probe, remove and resume**. An earlier experimental [patch 0015](N71_S8000_DART_ORDERED_TTBR_TLB_FAILCLOSED_ARM64_2026_11_13.md) protects already-owned streams when TLB invalidation fails, but cannot make a reset affecting all streams safe. Nor does it establish which *physical* PCIe requester maps to a DART SID.

The original Apple evidence identifies a **logical** WLAN DART mapper on PCIe port1, but it does not prove the actual physical requester-to-DART1 stream connection, ownership of all streams, or that the shared Apple A9 root clocks and resets cannot affect storage port0 or baseband port2. Separate per-port DART register apertures should not be mistaken for proof of shared-root electrical isolation.

## What patch 0016 actually does

The narrow experimental [source patch 0016](../experimental/patches/0016-n71-s8000-all-stream-dart-reset-interlock-offline.patch), based on exactly the previously compiled isolated source from 0015, adds a **fail-closed reset interlock**:

- If the driver is handling legacy **S5L8960X DART** and the machine is recognized as `apple,s8000`, `apple,n71` or `apple,iphone8,1`, then `apple_dart_hw_reset()` returns `-EOPNOTSUPP` **before its first MMIO lock-register read**, before constructing a stream-wide bitmap, and before clearing any TTBR.
- On other hardware models, the existing driver path is unchanged; no unreviewed new MMIO write or IOMMU operations were added.
- The existing **N71 WLAN DART1 pre-MMIO probe guard** remains present, ahead of `devm_platform_get_and_ioremap_resource()`. That is a separate and earlier protection for the actual WLAN DART1 aperture. The central reset interlock on its own does **not** protect all other probe-time resource/clock operations: the kernel may already have mapped a resource or enabled a clock before calling reset.
- The `remove` path now checks and logs refusal of reset instead of silently ignoring the return code. `probe` and `resume` already propagate reset errors.
- There is **no runtime parameter, override Device Tree flag, boot argument or opt-in switch** allowing an unverified reset.

This intentionally prevents the legacy S8000 DART reset. It is **not a working replacement per-stream reset** and will prevent a DART instance relying on this reset from becoming operational until a separately proven hardware ownership design is implemented.

## Exact build and reproducibility

The patch changes only `drivers/iommu/apple-dart.c` in the **isolated** owner-private worktree and is represented as an exact **two-hunk unified source delta**. It adds one central predicate, checks reset refusal at entry, and handles teardown refusal.

Previous isolated post-0015 source SHA-256:

```text
75e2808234541e1424e15ac411c512df5c9cefdab75535bdec469582bbd3e10e
```

New isolated post-0016 source SHA-256:

```text
67b33806dbb36f5fdb305d66f773af2c30db52cf69f61f076b33be0fa2edc65e
```

The Dell cross-compiled `drivers/iommu/apple-dart.o` from this source, with the existing owner kernel's ARM64/WLAN-enabled Kconfig. It is a true **ELF64 AArch64 relocatable** object:

```text
Size:   371176 bytes
SHA256: de8a360959dcba30f377a62861719a5617c539631c4cd2834b7bd30901c59c3c
```

The public [reset-interlock verifier](../tools/n71_s8000_dart_reset_interlock_offline_gate.py) checks these source/object SHA-256 pins, the exact two-hunk public patch, disallowed hardware operations in added lines, and the real C call graph. It enforces reset refusal **before the first reset MMIO read**, N71 DART1 `probe` pre-MMIO refusal, and checked return values in `probe`, `remove` and `resume`.

The [23 synthetic adversarial tests](../tests/test_n71_s8000_dart_reset_interlock_offline_gate.py) examine multiple N71/S8000 compatible strings, all four symbolic SIDs, host-architecture and ELF corruption, guard bypass, new MMIO writes, changing unrelated source files, and lifecycle error handling. These are static and symbolic software checks; they are **not live DART hardware tests**.

Owner-private, read-only verification example:

```bash
cd ~/Documenti/iphone6s-linux-cyberdeck-public
python3 tools/n71_s8000_dart_reset_interlock_offline_gate.py \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-dart-isolated-safety-pre-reset-interlock-20261113.c \
  ~/Documenti/cyberdeck-a9-linux/worktrees/n71-s8000-dart-isolated-safety-20261113/drivers/iommu/apple-dart.c \
  ~/Documenti/cyberdeck-a9-linux/private-touch-live-test/build-n71-dart-isolated-safety-20261113/drivers/iommu/apple-dart.o
```

The previous physically booted phone kernel `Image` remained byte-identical. The real iPhone was left running the known-good Linux USB gadget `05ac:4142` with `cfg80211` and `brcmfmac` built in and original private `albarossa` firmware stored in its RAM rootfs.

## What we still must prove to make Wi-Fi useful

The patch does **not** prove physical DART1 stream/SID ownership, safe per-stream reset, port1 PCIe root training, PCIe requester isolation or native BCM4350 Wi-Fi enumeration.

The next concrete task is to correlate **original N71 iOS AppleDARTMapper and PCIe port1 evidence** with the precise A9 root-port transaction routing, then implement a proven **per-stream-only** reset or a verified safe existing-hardware-state adoption strategy, with independent noninterference evidence for storage and modem. Because unknown shared A9 clocks/reset domains may affect multiple ports, no actual MMIO or DART1 enablement is justified yet.

The source-level interlock **must remain in place until such evidence exists**. Do not infer real WLAN success from Bluetooth HCI `chip id 110`, the presence of Linux `brcmfmac`, a firmware file, or a successful USB Internet test. No DFU/Pongo, new kernel boot, real PCIe bus scan, on-phone MMIO, DMA, NAND write or Bluetooth radio activation was performed during this offline patch work.
