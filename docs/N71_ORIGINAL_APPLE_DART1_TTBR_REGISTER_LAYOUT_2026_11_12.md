# N71/S8000: original Apple DART1 TTBR 4-stream × 4-register layout verified against actual Linux driver

**2026-11-12 | Actual hardware target:** owner-controlled iPhone 6s N71, Samsung A9/S8000, onboard BCM4350 Wi-Fi on PCIe port 1. **Sources:** privately retained original Apple iOS 15.8.8 N71 ARM64 Mach-O, two original N71 Apple Device Trees, prior original Apple IODARTFamily mapper/TCR code, and the owner's separate *experimental* Linux `drivers/iommu/apple-dart.c`. **Result:** the actual original Apple per-stream TTBR-clearing register address layout agrees precisely with the current Linux S5L8960x DART driver.

## Important distinction: hardware register layout is now evidenced; actual DMA routing is not

The original Apple `AppleS5L8960XDART` instance constructor's **actual vtable** has its TTBR-clear method at **slot 1728**, pointing to original ARM64 method relative code offset `0x1b6c`. This is the instantiated driver's vtable, not an unrelated MetaClass virtual table.

The original method first rejects a logical stream number greater than or equal to four, loads the native register map, computes `16 * logical_stream`, adds a hard-coded **`0x40`** offset, and clears exactly four 32-bit registers in a loop that advances by four bytes and terminates when the within-stream offset reaches `0x10`.

The original address formula, independently confirmed by pinned 32-bit AArch64 instruction signatures and the actual instance vtable, is:

```text
S5L8960x_DART_TTBR_REGISTER_OFFSET(stream, index)
  = 0x40 + 16*stream + 4*index
stream = 0..3, index = 0..3
```

| Original Apple logical DART stream | TTBR 0 | TTBR 1 | TTBR 2 | TTBR 3 |
|---|---:|---:|---:|---:|
| 0 — original WLAN mapper logical 0 | `0x40` | `0x44` | `0x48` | `0x4C` |
| 1 | `0x50` | `0x54` | `0x58` | `0x5C` |
| 2 | `0x60` | `0x64` | `0x68` | `0x6C` |
| 3 | `0x70` | `0x74` | `0x78` | `0x7C` |

All sixteen offsets are unique, aligned, and well within the original N71 DART1 MMIO window `0x602008000` (16 KiB) as independently proven from the original Apple Device Tree. Original Apple firmware software connects the Wi-Fi mapper's `reg=0` to **logical TCR lane0**, but that **still does not prove that the physical BCM4350 PCIe requester transmits hardware DART stream/SID 0**, nor that the other three streams are physically unused.

The experimental Linux driver uses:

```c
#define DART_S5L8960X_TTBR 0x40
#define DART_TTBR(dart, sid, idx) ((dart)->hw->ttbr + \
    (((dart)->hw->ttbr_count * (sid)) << 2) + ((idx) << 2))
// In apple_dart_hw_s5l8960x:
// .max_sid_count = 4, .ttbr_count = 4
```

This is exactly the original Apple TTBR register layout when `ttbr_count=4`. Both `apple_dart_hw_set_ttbr` and `apple_dart_hw_clear_ttbr` in Linux use this macro. We now have original-code evidence for that software register addressing rather than relying on later Apple M1/T8103 assumptions.

## Exact original/source verification

The new public read-only tool [`tools/n71_original_s5l_dart1_ttbr_register_layout_gate.py`](../tools/n71_original_s5l_dart1_ttbr_register_layout_gate.py) strictly checks:

- Original N71-specific ADT identity, dedicated DART1 single declared WLAN mapper and preexisting original IODARTFamily `reg=0` → Apple S5L DART logical lane0 evidence.
- Exact original private `AppleS5L8960XDART` 17,156-byte ARM64 executable length, actual constructor-installed instance vtable slot **1728** and thirteen pinned instruction words that implement the stream bound, map pointer, stream-index multiplication, `0x40` offset, four per-stream zero stores and bounded slot loop.
- The actual separately compiled Linux test worktree's S5L-specific TTBR base, stream count, table count, 4-byte slot stride, 16-byte stream stride and both TTBR set/clear accessor expressions.
- The separately published [0013 pre-MMIO DART1 guard](../experimental/patches/0013-n71-s8000-dart1-pre-mmio-wlan-probe-guard.patch), which still rejects DART1 mapping **before hardware**. A correct TTBR layout is not permission to bypass that guard.

The gate passed against **both original Apple ADT files**, the same genuine owner-held kernelcache, and the actual Linux S5L source in the Dell experimental worktree. The [23 synthetic adversarial tests](../tests/test_n71_original_s5l_dart1_ttbr_register_layout_gate.py) mutate original ARM64 instructions, Linux TTBR constants and strides, the original vtable target, S5L hardware descriptor stream counts and the fail-closed guard. All public fixtures are synthetic; no original Apple executable, original ADT, iOS IORegistry, calibration, unique device IDs or proprietary payload is published.

Owner-only reproducibility:

```bash
python3 tools/n71_original_s5l_dart1_ttbr_register_layout_gate.py \
  /private/original-n71-kernelcache.macho \
  /private/original-n71-apple-adt.bin \
  /private/experimental-linux/drivers/iommu/apple-dart.c

python3 -m unittest discover -s tests \
  -p test_n71_original_s5l_dart1_ttbr_register_layout_gate.py -v
```

## What is still required for functional native Linux Wi-Fi

This checkpoint **does not** establish the valid bit, physical TTBR page-base encoding, actual Apple DART page table entry and IOVA semantics, the live hardware SID assigned to the PCIe endpoint, DMA transaction ownership, fault isolation or safe port1 reset and clock order. It verifies **register addresses used by software** in an original native per-stream TTBR clear function.

The owner's experimental Linux worktree retains two existing safety patches: [0012 original packed-TCR lane-preservation fix](../experimental/patches/0012-apple-dart-s5l8960x-packed-tcr-rmw-fix.patch) and [0013 N71 WLAN DART1 pre-MMIO all-stream-reset blockade](../experimental/patches/0013-n71-s8000-dart1-pre-mmio-wlan-probe-guard.patch). No additional hardware write sequence was added, and **the DART1 early-probe block must remain** until actual requester SID, valid IOVA/TTBR page-table format, fault and rollback handling are established. The original 100-microsecond REFCLK/PERST delay and 10-microsecond root-status retry are independently proven, but the physical sequencing and bit4 cross-port electrical effects remain unknown.

**The known-good RAM-only Linux touchscreen/LCD/USB rescue image is unchanged. The iPhone remains in original stock iOS. Native Linux WLAN is not yet working.**
