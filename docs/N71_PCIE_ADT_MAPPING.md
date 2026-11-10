# N71/S8000 PCIe topology from a private Apple Device Tree

**Date:** November 10, 2026. **Device family:** iPhone 6s / Samsung A9 (S8000), N71.

**Evidence:** The locally recovered, RAM-backed Apple Device Tree (ADT) was parsed offline using `tools/adt-pcie-map.py`. Only an allow-listed hardware topology summary is recorded here. No raw ADT, MAC, serial, calibration, NVRAM or proprietary firmware is included.

## Observed ADT nodes

| ADT path | Compatible | Interpretation |
| --- | --- | --- |
| `/device-tree/arm-io/apcie` | `apcie,s8000` | Apple A9 PCIe host (four ports declared) |
| `/device-tree/arm-io/apcie/pci-bridge0/s3e` | — | Port 0, storage-related endpoint; **do not access for experimentation** |
| `/device-tree/arm-io/apcie/pci-bridge1/wlan` | `wlan-pcie,bcm4350` | Port 1 Broadcom BCM4350 WLAN candidate |
| `/device-tree/arm-io/apcie/pci-bridge2/baseband-pcie` | — | Port 2 baseband |
| `/device-tree/arm-io/dart-apcie0` | `dart,s8000` | DART/IOMMU for port 0 |
| `/device-tree/arm-io/dart-apcie1` | `dart,s8000` | DART/IOMMU for WLAN port 1 |
| `/device-tree/arm-io/dart-apcie2` | `dart,s8000` | DART/IOMMU for baseband port 2 |
| `/device-tree/arm-io/uart4/wlan` | `wlan-pcie-uart,bcm4350` | Ancillary WLAN UART described by ADT; not proof of WLAN-over-UART |

Additional PCIe host descriptors (as decoded by the read-only parser): `#ports=4`, `bus-range=[0,8]`, interrupts `0xf4,0xf7,0xfa,0xfd`, clock gates `0x39..0x3e`, power gate `0x38`, MSI vector offset `0x100`. The host MMIO windows are rooted at `0x600000000`, `0x601000000`–`0x604004000`, and `0x610000000`. These are **hardware metadata**, not safe register-writing instructions.

The private ADT source was 163,840 bytes; 150,900 bytes were consumed by the structural parser, leaving trailing space in its storage region. No unknown properties were serialized in the report.

## What this establishes—and what it does not

- **Confirmed (metadata):** BCM4350 WLAN is associated with Apple PCIe bridge 1 on this S8000 ADT; its port-specific `dart-apcie1` is present.
- **Not yet confirmed (runtime):** PCIe root-complex enumeration, endpoint link training, interrupt delivery, DART mappings, firmware loading, station-mode Wi-Fi, or RF transmission.
- The currently booted HoolockLinux kernel enumerates **zero PCIe devices**; `CONFIG_PCIE_APPLE=y` does not by itself add S8000 support. It also lacks the WLAN stack.
- This is **Samsung S8000/N71 evidence**, not a claim about the TSMC A9/S8003 board.

## Controlled driver development plan

1. Diff the S8000 ADT PCIe/DART topology against existing Linux PCIe controller and Apple DART drivers. Document all binding differences before coding.
2. Implement an **offline-only**, separately reviewable DTS and controller-driver prototype for S8000. Preserve the known-good RAM boot bundle.
3. First hardware experiment must be explicitly gated to **PCIe port 1** and must not configure, reset, DMA-map or write to port 0/storage or port 2/baseband. Confirm safe isolation before any probing.
4. Obtain read-only link/ID evidence, then a functional PCIe device enumeration before enabling `brcmfmac`.
5. Use board-matched firmware/NVRAM privately, never publish per-device calibration, and test station mode against an authorized AP only.

**Safety:** A metadata map is not a permission to write MMIO. No PCIe hardware registers were modified during this ADT analysis.
