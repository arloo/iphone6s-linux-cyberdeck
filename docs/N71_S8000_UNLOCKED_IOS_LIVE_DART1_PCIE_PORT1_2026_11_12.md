# N71/S8000: live unlocked stock-iOS DART1 mapper and native BCM4350 PCIe link corroboration

**Date:** 2026-11-12. **Device:** owner-controlled iPhone 6s N71, Samsung A9/S8000, connected by USB to the Dell. **Capture:** read-only `idevicediagnostics ioregentry` on an owner-unlocked device running original iOS 15.7.9. **Result:** original Apple DART1, mapper and WLAN port1 metadata matched directly against two privately retained original N71 Apple Device Tree files. **This is a read-only iOS hardware/status verification, not a Linux Wi-Fi test.**

## Live proof obtained only after the owner unlocked iOS

The original USB pairing was already valid, but the Apple Diagnostics Relay service previously rejected access with `Password protected`. After the owner explicitly unlocked the phone, the exact same read-only command successfully captured Apple IORegistry entries into a **private `0700` folder** under the Dell research tree, with individual private files mode **`0600`**.

| Actual live iOS entry | Authenticated observed facts | Cross-check |
|---|---|---|
| `dart-apcie1` | Original Apple DART1 node present; 16-byte `reg` | Byte-for-byte matches original N71 ADT |
| `mapper-apcie1` | Original child mapper present; `reg` is 32-bit logical index **0** | Byte-for-byte matches original N71 ADT |
| `pci-bridge1` | `IOPCIConfigured=true`, `IOPCIResourced=true`, port index **1** | Original 4-byte `apcie-port` property matches |
| `pci-bridge1` | `IOPCIExpressLinkStatus=0x1011` | Standard PCIe Link Status: speed code **1** (Gen1, 2.5 GT/s), width **1**, training bit **0**, slot-clock bit **1** |
| `pci-bridge1` | Original `function-clkreq` (16 bytes) | Byte-for-byte matches N71 ADT |
| `pci-bridge1` | Original `function-dart_force_active` (8 bytes) | Byte-for-byte matches N71 ADT; meaning of opaque callback metadata not inferred |
| `pci-bridge1` | Original `t-refclk-to-perst` (4 bytes) is **100** | Byte-for-byte matches original N71 ADT. **Time units and actual sequencing not proven.** |
| `AppleS5L8960XDART` (IOService class) | `IOClass=AppleS5L8960XDART`, `IONameMatched=dart,s5l8960x`, `IOMatchedAtBoot=true`, `IOProviderClass=AppleARMIODevice` | Confirms original DART driver attached under iOS; does not expose stream-page tables or DMA transaction IDs |

A total of **six** property values for three original Apple Device Tree nodes are matched byte-for-byte against the owner-unlocked stock-iOS snapshots: bridge1 has 4 compared fields; mapper1 has 1; dart1 has 1. These six are independent of the previous 83 original PCIe/PHY tuning records proven against iOS earlier.

**Important distinction:** the live iOS `pci-bridge1` service also exposes a dynamically synthesized `reg` field of a different format. The static original Apple Device Tree does not expose the same property at the same path. We do **not** claim that this runtime `reg` matches a nonexistent static original `reg`.

The matching Apple mapper `reg=0` now has both authentic **live iOS registry** and [original Apple driver software](N71_ORIGINAL_APPLE_DART1_MAPPER_TCR_LANE_2026_11_12.md) backing: the original driver forwards that logical index to packed DART TCR byte lane 0. **This does not establish hardware request routing, the PCIe requester ID, DART1 TTBR/IOVA content, live fault handling, physical DMA isolation or safe reset.**

## New public fail-closed original/live verifier

The standalone `tools/n71_s8000_live_dart1_pcie_link_gate.py` accepts only the privately held original N71 ADT and five private owner-controlled stock iOS snapshots. It first runs the existing strict N71 S8000 hardware/unique DART1 consumer census, then confirms the real six byte-for-byte properties and the original Apple DART service match. It additionally requires configured and resourced PCIe port1, stable original Apple iOS Gen1 x1 link, mapper index0 and port index1.

For safety it fails closed if a different SoC/port, extra DART mapper consumer, malformed ADT/IORegistry, changed `CLKREQ`/`t-refclk-to-perst` or DART callback metadata, changed link training/width/speed/clock bit, or unexpected DART driver is supplied. It prints only safe original SoC facts and aggregate counts. No raw Apple IORegistry, identifiers, board calibration, kernelcache executable, source file paths or private WLAN metadata are copied to GitHub.

Reproduce on the authorized private Dell (after original owner permission):

```bash
python3 tools/n71_s8000_live_dart1_pcie_link_gate.py \
  /private/original-n71-apple-adt.bin \
  /private/live_pci-bridge1.plist \
  /private/live_mapper-apcie1.plist \
  /private/live_dart-apcie1.plist \
  /private/dart_AppleS5L8960XDART_class.plist

python3 -m unittest discover -s tests \
  -p test_n71_s8000_live_dart1_pcie_link_gate.py -v
```

The `tests/test_n71_s8000_live_dart1_pcie_link_gate.py` suite adds **33 synthetic positive/adversarial and privacy tests**. The verifier has already succeeded against **both** distinct local Apple N71 ADT files and the **actual fresh unlocked-iOS live service snapshots**.

## Next dependency toward true Linux Wi-Fi

Original stock-iOS hardware evidence now demonstrates the endpoint can maintain a stable Gen1 x1 link through Apple PCIe port1 and that the Apple DART driver attaches to the device. With this control-state baseline, the next correct engineering operation is to implement and independently verify a **strictly port1-scoped** S8000 Linux bring-up path and actual safe per-stream DART DMA setup, while keeping the original working RAM-only touchscreen/LCD/USB recovery boot unchanged.

Physical requirements **not cleared:** complete PCIe clock/refclock/PHY/PERST/MSI/endpoint power sequence and root-shared status bit4 cross-port effects; PCIe requester-to-DART1 physical SID mapping; safe TTBR/IOVA and bounded fault/rollback handling; and actual Linux BCM4350 enumeration and direct on-phone WLAN association to the authorized Dell network. M1/T8103 register offsets are not a substitute for original A9 semantics.

The existing separate, fail-closed Linux S8000 PCIe **research-guard** source was also compiled and verified as an AArch64 ELF64 relocatable object in the Dell's *private isolated Linux build output*. Its probe remains deliberately blocked, no MMIO or PCIe driver bring-up is performed, and it is not inserted into the known-good RAM Linux image. The existing working touch/LCD/USB rescue image SHA-256 was rechecked unchanged. This build is a cross-compilation checkpoint, not a functioning host-controller driver.

**No hardware write, root-controller MMIO, DART DMA, iOS reboot, DFU, NAND access, kernel module load, radio reconfiguration or Linux boot was performed in this milestone.** Only read-only iOS diagnostics and offline software tests.
