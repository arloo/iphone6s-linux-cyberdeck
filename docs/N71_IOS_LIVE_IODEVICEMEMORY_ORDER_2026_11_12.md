# N71/S8000 LIVE PCIe IODeviceMemory ordering: physical evidence

**12 November 2026 — direct, read-only iPhone 6s N71 observation.** The device is in ordinary iOS 15.7.9 (19H365), paired over USB with the Dell. No Linux boot, hardware register write or phone reset was attempted.

## Original physical controller-resource order, independently confirmed

After the user unlocked the device, targeted 'idevicediagnostics ioregentry apcie' produced a complete PCIe-root IORegistry entry, whereas full IORegistry plane queries had yielded empty dictionaries.

The original live AppleARMIODevice provider exposes an 11-element IODeviceMemory array. Every array element contains a single address/length pair. **All 11 physical addresses and lengths match, in identical order, both the live original reg tuples and the independently saved private S8000 N71 Apple Device Tree.** This directly resolves the earlier uncertainty about AppleARMIODevice resource ordering on the actual handset.

| Index | Live physical base | Length | Hardware classification |
|---|---|---|---|
| 0 | 0x610000000 | 0x1000000 | PCIe configuration |
| 1 | 0x601000000 | 0x4000 | Storage port0 — protected |
| 2 | 0x601004000 | 0x4000 | Storage port0 — protected |
| 3 | 0x602000000 | 0x4000 | WLAN port1 — unqualified |
| 4 | 0x602004000 | 0x4000 | WLAN port1 — unqualified |
| 5 | 0x603000000 | 0x4000 | Baseband port2 — protected |
| 6 | 0x603004000 | 0x4000 | Baseband port2 — protected |
| 7 | 0x604000000 | 0x4000 | Unknown port3 — protected |
| 8 | 0x604004000 | 0x4000 | Unknown port3 — protected |
| **9** | **0x600000000** | **0x8000** | **Common PCIe root** |
| **10** | **0x600008000** | **0x4000** | **Additional PCIe root resource** |

The previously verified original S8000 ARM64 root methods select resource indices **0, 9, 10** when the host has four ports. Their physical bases are now confirmed by live iOS IODeviceMemory, instead of relying on presumed ADT order.

## Additional live PCIe and BCM4350 evidence

- The live pci-bridge1 entry reports IOPCIConfigured=true, IOPCIResourced=true, and IOPCIExpressLinkStatus=0x1011. This is a captured status word, **not** permission to claim link active or safe Linux initialization.
- The live AppleBCMWLANCore entry reports ChipSet=4350 and FirmwareLoaded=true; the AppleBCMWLANBusInterfacePCIe class is registered. This confirms Broadcom chipset family and iOS firmware-load status, but does **not** select the correct private Linux C2/C5 board firmware.
- The live Wi-Fi diagnostic response reported Active=NO at capture time. That alone does not establish a radio fault.
- The Broadcom bus entry contains original device-specific OTP/calibration. All original IORegistry plists and OTP remain in the private Dell research directory with restrictive file permissions, and are not exported.

## Verified live BCM4350 firmware request: C5, not C2

A separate live, read-only AppleBCMWLANCore IORegistry entry exposes ChipSet 4350, FirmwareLoaded true, PlatformConfigFileName in the albarossa family and precisely four requested file categories: Firmware, NVRAM, Regulatory, and TxCap. All four live request strings belong to **C-4350__s-C5**; none references C2.

The private original Apple iOS 15.8.8 firmware extraction contains exactly one matching C5 file for each of the four requested basename/type pairs. This was confirmed against the real live iOS 15.7.9 file requests, without reading or disclosing private Apple firmware, NVRAM content or chip OTP.

Public privacy-safe verification tool: tools/n71_ios_bcm4350_c5_gate.py. It checks the live private IORegistry chipset, firmware-loaded status, albarossa family, four C5-only request paths and presence of exactly one same-type file in the private extracted Apple C5 bundle. The tool does not inspect the contents of Apple firmware/OTP/calibration files, display paths or access hardware. Eighteen fully synthetic tests in tests/test_n71_ios_bcm4350_c5_gate.py cover C2 rejection, mismatched chipset, missing/duplicate C5 assets, wrong platform, malicious paths, unsupported filenames and no data export.

This decisively identifies the **requested iOS radio firmware variant** as C5, so C5 should be the primary private candidate for eventual Linux testing. It does NOT prove Linux brcmfmac can parse or boot the original Apple file format, does not prove board calibration can be reused, and is not permission to energize the WLAN GPIO, PCIe bus or DART1.

## Fail-closed public reproduction

The new tools/n71_ios_iodevicememory_order_gate.py accepts only a locally supplied private original iOS ioregentry apcie plist and private N71 ADT. It verifies the ADT hardware family, four ports, all eleven reg tuples and, critically, exact INDEX-ORDER equality of all 11 IODeviceMemory ranges. It returns only known hardware addresses and sanitized PASS/BLOCKED status.

Example using PRIVATE input files, never checked into Git:

    python3 tools/n71_ios_iodevicememory_order_gate.py /private/entry_apcie.plist /private/n71-adt.bin

Twenty-four fully synthetic tests in tests/test_n71_ios_iodevicememory_order_gate.py cover positive matching, shuffled-order rejection, wrong range sizes, invalid structures, silicon/port mismatch, corrupt ADT, input limits, no hardware effects and private-property nonexport. No Apple firmware, original iOS registry dump, keys, identifiers, SSID, MAC, board OTP or Wi-Fi calibration are published.

Apple describes indexed IODeviceMemory ranges in its IOService API:
https://developer.apple.com/documentation/kernel/ioservice/1809999-getdevicememorywithindex

## Still blocked before native Linux WLAN

1. Verify meaning, allowed values and cross-port effects of original S8000 PCIe common-root bit transitions, especially the global control/status at index9-relative offset 0x2C. Knowing the physical base **does not make arbitrary MMIO reads/writes safe**.
2. Isolate port1 PHY/refclock/PERST/clock/MSI/link without affecting port0 storage, port2 modem or global shared hardware.
3. Verify DART1 real stream ID, IOVA/page table/fault isolation and safe DMA. The original DART driver has a dangerous multi-stream reset sequence.
4. Only then supervise a separate RAM-only Linux boot with known-good LCD, Z2 touch and USB fallback, enumerate onboard BCM4350, choose genuine board-matched private firmware and establish radio association to the Dell's authorized Wi-Fi network.

**No PCIe MMIO write, DART DMA, PMIC action, DFU/reset, Apple NAND access or Linux Wi-Fi association was performed in this phase.**
