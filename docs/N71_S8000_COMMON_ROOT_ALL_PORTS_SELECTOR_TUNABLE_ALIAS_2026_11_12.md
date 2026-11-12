# N71/S8000: original Apple PCIe root tuning overlaps all four per-port selectors

**Date:** 12 November 2026. **Source:** owner-held original N71/S8000 Apple Device Tree, authenticated live original stock-iOS `apcie` and `pci-bridge1` IORegistry records, and original private N71 ARM64 AppleEmbeddedPCIE / AppleS8000PCIe instruction semantics. **Method:** offline analysis; no live register reads/writes, no DMA, no NAND/storage access, no radio action.

## New verified static finding

The previously established original Apple four-port common-controller selector provides per-port relative register offsets:

```text
selector ID2: 0x100 + port_index * 0x80
selector ID3: 0x114 + port_index * 0x80
selector ID4: 0x124 + port_index * 0x80
selector ID5: 0x12c + port_index * 0x80
```

The original `AppleEmbeddedPCIE` 24-byte tunable record layout is independently verified from authentic ARM64 code, and the authentic N71 `apcie-common-tunables` bytes were independently compared against live stock-iOS IORegistry bytes. Their group contains **34 valid, width-4 masked-RMW records** among **83 original records across four tuning groups**.

**New intersection:** Four of the common root tunable offsets coincide with selector ID2 across **all four** original PCIe ports, not solely the WLAN port:

| Original port | Protected purpose | Original root-relative selector ID2 offset | Corresponding original common-group tunable record |
|---|---|---|---|
| Port 0 | Storage/NAND | `0x100` | **Present**, nonzero RMW mask |
| Port 1 | BCM4350 Wi-Fi | `0x180` | **Present**, nonzero RMW mask |
| Port 2 | Baseband/modem | `0x200` | **Present**, nonzero RMW mask |
| Port 3 | Other / not qualified | `0x280` | **Present**, nonzero RMW mask |

For all four records, the original RMW mask does **not** include bit 0. Neither masks nor new values are disclosed. Original proprietary register values, private ADT and IORegistry binary, firmware and calibration remain on the owner's Dell.

The root common bank has **no direct record** at the known original shared status register relative offset `0x2c`, nor at port1 selector ID5 `0x1ac`. The original port1 config and port1 RC tunable banks have no common relative offsets. One common-vs-PHY-bank relative offset coincides, but those are **distinct resource domains** and must never be called a physical-address overlap without validated mapping.

This is a **static cross-bank address/record comparison**: it does not establish that Apple applied every record during every boot, that the four selector accesses necessarily produce side effects, or that a mask affects the storage/media contents. Physical MMIO mappings, link/clock/reset state, register bit meanings and side effects require additional A9-specific evidence.

## Crucial engineering consequence

The original Apple tuning data are **not a port1-only write recipe**. Copying or replaying the entire `apcie-common-tunables` bank while attempting to bring up Wi-Fi could interact with control state associated with storage port0, baseband port2 and port3, and no safe independent rollback has been proven.

The Linux S8000 port1 research guard's existing unconditional `-EOPNOTSUPP` is the **correct** current behavior. **Do not introduce a shortcut** that replays all 34 common-root records or toggles controller-global state merely to enumerate the BCM4350. The current real Linux kernel still has no functional S8000 PCIe host or native WLAN.

The independent [strict source-and-data cross-port impact gate](../tools/n71_s8000_root_tunables_crossport_impact_gate.py) accepts only private, known-format owner inputs and enforces the original source signature, exact ADT↔stock-iOS tunable bytes, the 83-record structure, four expected cross-port selector aliases, nonzero masked updates, port1/status-register absence, original per-bank uniqueness, and refusal to classify root replay as port1-safe.

[Twenty-one adversarial unit tests](../tests/test_n71_s8000_root_tunables_crossport_impact_gate.py) mutate individual storage/WLAN/baseband/other-port aliases, unexpected selector writes, status register offsets, nonzero bit0, overlapping banks and malformed masks/widths. All must fail closed. The real private original-data invocation passed without exporting raw private masks or values.

## Scope and next engineering gates

The available original Apple evidence provides a concrete reason to **isolate port1 operations from common-root initialization**. The next driver design must establish:

1. Which controller-global/common initialization operations are necessary and how to preserve any state already owned by storage port0, baseband port2 and port3, with known rollback behavior.
2. The original Samsung A9 port1-specific PHY, REFCLK, PERST# and MSI ordering, including bounded polling; original XNU delay provenance proves `100 µs` REFCLK-to-PERST and a separate `10 µs` retry interval but does not prove hardware-safe enablement.
3. Actual physical PCIe BCM4350 requester-to-DART1 stream-ID routing, DMA aperture, fault handling, TTBR/IOVA and independent ownership; the original Apple ADT WLAN→DART1 mapper index0→packed TCR lane0 is *software provenance*, not a validated hardware DMA stream ID.
4. A separately supervised, RAM-only platform driver experiment with a strict NAND/storage and modem isolation gate. No active PCIe host, DART1 DMA or RF initialization until those requirements are independently established.

**Device status:** The physical iPhone 6s remains running known-good RAM Linux with the previously proven passive port1 `probe()` module, touchscreen protocol initialized and USB management reachable. No additional reboot or MMIO/DMA action was required for this analysis.

## Reproduce on the authorized owner's Dell (private inputs never published)

```bash
python3 tools/n71_s8000_root_tunables_crossport_impact_gate.py \
  /private/original-s8000-adt.bin \
  /private/original-ios-apcie.plist \
  /private/original-ios-pci-bridge1.plist \
  /private/original-n71-arm64-kernelcache.macho

python3 -m unittest discover -s tests \
  -p test_n71_s8000_root_tunables_crossport_impact_gate.py -v
```

The comparator emits only redacted aggregate facts and unequivocal `ROOT_BANK_REPLAY_AS_PORT1_ONLY_SAFE=NO`. It does **not** generate register write sequences. For contrast, the upstream Linux `pcie-apple.c` implementation and its RID→SID logic target newer Apple PCIe hardware families; their register offsets cannot be transplanted into the iPhone 6s Samsung A9 without original S8000 verification.
