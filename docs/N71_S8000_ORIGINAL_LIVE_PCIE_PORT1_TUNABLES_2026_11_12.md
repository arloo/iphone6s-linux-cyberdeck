# N71/S8000 iPhone 6s: original stock-iOS PCIe tuning recovered and privately staged

**Date:** 2026-11-12. **Device target:** iPhone 6s, N71, Samsung A9/S8000, native BCM4350 Wi-Fi on PCIe port 1. **Evidence:** original N71 Apple Device Tree, original AppleEmbeddedPCIE ARM64 code from a privately held iOS 15.8.8 kernelcache, and an independent read-only IORegistry snapshot captured from the same N71 running stock iOS 15.7.9.

**Result:** All four expected native PCIe/PHY tunable data blocks are **identical byte-for-byte** in the original N71 Apple Device Tree and in the live original-iOS IORegistry. The original driver code independently confirms each 24-byte record's size, field layout and **32-bit masked read/modify/write calculation**. The actual board-specific numeric tunable values were staged only in the owner's private Dell research tree, never in this public repository. No hardware changes were made.

## Independently corroborated original properties

| ADT / IORegistry source | Property | Genuine records | Exact original/live match |
|---|---|---:|---|
| S8000 PCIe root (`apcie`) | `apcie-common-tunables` | 34 | PASS |
| S8000 PCIe root (`apcie`) | `apcie-phy-tunables` | 41 | PASS |
| PCIe port 1 (`pci-bridge1`) | `apcie-config-tunables` | 6 | PASS |
| PCIe port 1 (`pci-bridge1`) | `pcie-rc-tunables` | 2 | PASS |
| **Total** | | **83** | **PASS** |

All 83 records have a width of exactly four bytes, are aligned, and have register-relative offsets within their respective bounded original control/PHY windows. All corresponding masks and values fit 32 bits, and every set bit is permitted by its mask. The common root array has **no direct record targeting relative offset `0x2C`**, where earlier static original-code evidence identified a shared status bit4 poll. This does **not** establish the meaning or safety of nearby register operations, nor authorize any root/shared writes.

The original Apple `AppleEmbeddedPCIE` KEXT contains the diagnostic assertions for `spdsTunable` length and `tunable->size == sizeof(uint32_t)`, and actual ARM64 loops that step by `0x18` (24) bytes. Original code additionally loads two 64-bit quantities at record offset `+8`, an offset at `+0`, width at `+4`, and computes a masked value `(old & ~mask) | (new_value & mask)` before dispatching a write callback. These original-software observations establish the packed field format:

```c
// Format description only; not executable hardware access.
struct original_apple_pcie_tunable {
    uint32_t register_offset;
    uint32_t register_width; // verified 4
    uint64_t clear_mask;     // original device values fit 32 bits
    uint64_t set_value;      // original device values fit 32 bits
}; // sizeof = 24
```

**Not proven:** whether applying these original values in the wrong order is electrically safe; the meanings of S8000 shared bit4, clock/refclock/PHY/PERST#, MSI, resets and per-port power; any DART1 DMA fault containment; and the S8000 requester-to-DART1 SID path. The original code was from iOS 15.8.8 while the captured phone is running iOS 15.7.9. Cross-version and source-byte corroboration do **not** establish identical executable versions.

## Reproducible strict provenance check (public tools; private inputs)

`tools/n71_s8000_private_pcie_tunable_stage_gate.py` validates the original S8000 ADT and WLAN/DART1 topology, compares original ADT data against genuine stock-iOS runtime OSData, decodes all four blocks, and checks original AppleEmbeddedPCIE ARM64 instruction signatures for the masked-RMW and 24-byte stride. It does not communicate with the phone, create writable device mappings or apply any hardware values.

`tools/adt-pcie-map.py` gained a backward-compatible opt-in `extra_props` parameter. By default it still suppresses unrelated and device-private values; only the explicit, carefully scoped original/source checker asks to read the four tunable properties.

```bash
python3 tools/n71_s8000_private_pcie_tunable_stage_gate.py \
  /private/original-n71-adt.bin \
  /private/stock-ios-15.7.9-entry-apcie.plist \
  /private/stock-ios-15.7.9-entry-pci-bridge1.plist \
  --original-kernelcache /private/original-n71-kernelcache.macho

python3 -m unittest discover -s tests \
  -p test_n71_s8000_private_pcie_tunable_stage_gate.py -v
```

The checker outputs only the record counts and explicit NO/FAIL-CLOSED hardware status, not original tunable data, original kernel sections, source paths, device IDs, Wi-Fi MAC, SSID, firmware/OTP or calibration.

## Private, hardware-inert staging (already completed on Dell)

A second version of the exact original per-device 83-record data manifest was created **outside GitHub and outside the public Git worktree**. The original/private working directory is mode `0700`, the manifest file is mode `0600`, creation requires an existing private marker and uses exclusive/no-symlink semantics. The manifest declares `enable_register_writes=false`, `enable_pcie_port1_link=false`, `enable_dart1_dma=false` and `cross_port_effects_qualified=false`. It includes a static proof that the original Apple software uses the masked-RMW algorithm, but **is not an executable or safe hardware initialization sequence**.

The public tool can recreate such a manifest only in a separately marked and permission-restricted private output folder using `--stage-private`. No private original data is tracked, copied into the public repository or printed in logs.

Synthetic tests in `tests/test_n71_s8000_private_pcie_tunable_stage_gate.py` enforce record-length, width, alignment, window bounds, masks, original ARM64 instruction words, source mismatch rejection, opt-in private property handling, disabled hardware flags, marked/private-only output and data leak prevention. Neither this checker nor its test suite accesses MMIO, GPIO, PCIe, DART, radio or any Apple NAND partition.

## Next step toward genuinely working Wi-Fi

1. Combine the **verified private per-device tuning data** with a new **separate** S8000 PCIe port1-only controller implementation, preserving all existing known-good RAM-only touchscreen/LCD/USB boot assets.
2. Verify original S8000 port1 PHY/refclock/PERST#/power/MSI order, prove all shared writes' cross-port effects, and add bounded timeouts and recovery.
3. Qualify DART1 requester-to-logical-stream (currently original Apple mapper index0 and packed TCR lane0 verified in original software), actual physical DMA routing, TTBR/IOVA/fault containment and a safe alternative to the stock four-stream Linux DART reset.
4. Only after those conditions: perform a supervised, reversible RAM-only Linux hardware test with the original owner, then confirm real on-phone `brcmfmac` physical BCM4350 enumeration, correct private **C5** WLAN firmware and direct wireless association/traffic to the Dell network. USB routing is not accepted as a substitute.

No actual PCIe/WLAN/DART1 activation or Linux network operation was verified in this milestone. Avoid transplanting newer T8103/M1 register semantics into Samsung A9/S8000 without original evidence.
