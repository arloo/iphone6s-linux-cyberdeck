# N71/S8000: original Apple ADT proves the logical PCIe-to-DART IOMMU graph

**13 November 2026. Original Apple stock iOS evidence, examined OFFLINE on the owner Dell. No physical DMA or Wi-Fi PCIe enumeration is implied.**

## Source and method

The owner previously captured an authentic iPhone 6s N71/Samsung S8000 Apple Device Tree (`ADT`) and iOS IORegistry snapshots. This new analysis uses the locally retained **original 163,840-byte ADT container**, never a third-party generic S8003 Device Tree.

The original ADT contains **178 parsed nodes**, followed by an expected zero-filled reserved buffer. Every `AAPL,phandle` used here is resolved **by exact four-byte equality** inside that same original tree; no reference numbers, pointers, original binary data, serials, calibration, SSIDs, MACs or private identifiers are printed or committed.

The new [read-only source verifier](../tools/n71_original_apple_adt_iommu_parent_graph_gate.py) checks source bounds, duplicate handles, the original `apcie-port` numbering, each `iommu-parent` reference and the corresponding `mapper-apcie*` nodes' local `reg` index. The [18 entirely synthetic negative tests](../tests/test_n71_original_apple_adt_iommu_parent_graph_gate.py) reject swapped radio/modem IOMMUs, incorrect port numbers, duplicate references, bad mapper index, malformed ADT lengths and unexpected nonzero suffix. Synthetic test fixtures invent their own small phandles.

## Verified original Apple logical topology

| Original Apple PCIe path | Original bridge number | Original IOMMU parent relationship | Status |
|---|---:|---|---|
| `apcie/pci-bridge0/s3e` (internal storage) | 0 | First **two of three** `iommu-parent` references resolve to `dart-apcie0/mapper-apcie0` | Exact original ADT phandle links proven |
| `apcie/pci-bridge1/wlan` (BCM4350C5 `albarossa`) | 1 | Single `iommu-parent` resolves to `dart-apcie1/mapper-apcie1` | Exact original ADT phandle link proven |
| `apcie/pci-bridge2/baseband-pcie` (modem) | 2 | Single `iommu-parent` resolves to `dart-apcie2/mapper-apcie2` | Exact original ADT phandle link proven |

**All three selected DART mapper nodes have original `reg = 0`**, the **logical mapper-local index**. The three Apple mapper `AAPL,phandle` values are different. The third storage parent-cell reference is deliberately **not assigned a physical meaning** by this verifier; it is outside the minimum set of relationships required to prove the WLAN-to-DART1 mapping.

This is stronger than guessing a Wi-Fi DART from the filename or from another Apple SoC: the original N71 Apple tree itself describes Wi-Fi on bridge1 and points to the separate DART1 mapper.

## What this does NOT prove

The Apple `iommu-parent` phandle relationship is a **logical software description**, NOT an observed PCIe transaction or hardware DART stream trace. A mapper-local `reg = 0` does **not** establish that the actual physical BCM4350 PCIe requester reaches DART1 stream 0. In particular, it does not prove the RID/SID translation, real IOVA translation/fault containment, clocks, per-port reset ownership or anything about an enumerated `14e4:43a3` PCIe endpoint.

The controller-wide Apple A9 PCIe root is shared between ports. Even though the original ADT names distinct DART0/1/2 devices, this does **not** demonstrate that resetting the root or switching its clocks cannot disturb the storage and modem. Likewise, an experimental [patch 0016](../experimental/patches/0016-n71-s8000-all-stream-dart-reset-interlock-offline.patch) deliberately blocks the unqualified all-stream reset; **it does not provide a safe functional per-stream reset**.

The current iPhone 6s is still running the previously tested RAM Linux with native wireless `cfg80211/brcmfmac` software and genuine Apple C5 firmware available in RAM, via a **Dell USB uplink**. PCIe endpoints, IOMMU groups and native WLAN interface are still absent in the latest physical test.

## How to reproduce without disclosing proprietary data

The public tool can be run only with an independently owner-authorized, locally available original Apple ADT:

```bash
cd ~/Documenti/iphone6s-linux-cyberdeck-public
python3 tools/n71_original_apple_adt_iommu_parent_graph_gate.py \
  ~/Documenti/cyberdeck-a9-linux/private-firmware/runtime-n71/runtime-apple-adt.bin
```

Output consists exclusively of fixed PASS/NO status strings; never the input binary or original handle numbers. The private ADT, IORegistry, firmware, board calibration and raw register data remain on the Dell.

## Engineering next step

Use this **verified logical graph** to keep the future A9 root, storage and modem identities distinct. The next hardware qualification must establish **actual physical requester→DART1 stream routing** and prove that a **port1-only clock, power and reset** operation cannot affect port0 or port2. Only after source-level and independently reviewed ownership evidence may a separate supervised RAM-only hardware experiment be considered.

**No DART1 pre-MMIO block was bypassed, no kernel image was replaced, no DFU was performed, and no iPhone NAND/PCIe/DMA/MMIO operation occurred during this audit.**
