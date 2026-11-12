# N71/S8000: physical Linux port1 descriptor-only RAM boot — verified

**Date:** 12 November 2026
**Hardware:** physical owner-controlled iPhone 6s, Samsung Apple A9 S8000, N71
**Evidence:** **real physical Linux boot**, not synthetic or QEMU
**Important:** This is **not** a functional PCIe host, DART IOMMU, Broadcom BCM4350 Wi-Fi interface or wireless network connection.

## Actual on-device transition

From the owner's Dell Kubuntu host, PongoOS USB `05ac:4141` was physically detected before this test. The user transferred the owner-private, RAM-only, descriptor-only research image:

```text
private-touch-live-test/n71-s8000-port1-descriptor-only-next/
  m1n1-linux-n71-port1-descriptors-only.bin
```

**File size:** 11,822,390 bytes. **SHA-256:** `6f460870bbded3648ba9136afac45a428c55c4470185e5f0873b6c074605b986`.

This image was built from the **physically booted and confirmed** 11,821,980-byte predecessor. A binary comparison confirmed exactly **410 extra bytes** in the Samsung N71 Device Tree; all remaining boot image bytes, including the m1n1 bootloader, S8003 DTB, actual known-good Linux kernel image, original touchscreen resources, firmware/calibration and initramfs were **byte-identical** to the predecessor.

The physical Dell USB logs confirm:

- PongoOS `05ac:4141` was connected before the handoff.
- At **14:13:11 CET**, the iPhone re-enumerated as **HoolockLinux USB Device `05ac:4142`**, USB CDC NCM.
- The USB-gadget interface was assigned the same point-to-point subnet `172.16.42.2 → 172.16.42.1`; an immediate **2/2 ping with 0% packet loss** passed.
- The on-device Linux kernel again reported `7.3.0-rc1-g68aadac820d0-dirty`.

The on-device initramfs read-only WLAN baseline hook reported **1 platform-device node matching PCIe port1**, versus **0 on the preceding physical boot**, with no PCIe devices, no IOMMU groups and no native WLAN interfaces. The total number of platform devices observed went from **115 to 116**.

## Verified live OF and platform metadata

The synthetic N71 port1 node was read back from the real running phone's `/sys/firmware/devicetree/base/soc/pcie-port1-preflight@602000000`. The corresponding platform device is present under `/sys/bus/platform/devices`.

| On-device property | Physical result |
|---|---|
| Device Tree OF node exists | **YES** |
| Compatible | `apple,s8000-pcie-research-blocked` |
| Status | `okay` |
| Resource names | `port1-reg-a`, `port1-reg-b`, `dart1-reg` |
| Port1 window A (physical base / size) | `0x602000000 / 0x4000` |
| Port1 window B (physical base / size) | `0x602004000 / 0x4000` |
| DART1 window (physical base / size) | `0x602008000 / 0x4000` |
| `research,hardware-activation-blocked` | **present** |
| Matching platform devices | **1** |
| Hardware driver bound to platform device | **NO** |
| Enumerated PCIe devices | **0** |
| IOMMU groups | **0** |
| Native WLAN network interfaces | **0** |
| Z2 touchscreen automatic protocol initialization | `COMPLETE:PROTOCOL_READY` |

These exact three register descriptors were independently established from the owner's original Apple runtime ADT, captured from the actual iPhone on two separate occasions. No native PCIe host controller is bound to them.

The new [read-only live USB descriptor collector](../tools/n71_usb_port1_descriptor_only_collect.py) validated the actual OF compatible, status, exact 48-byte big-endian `reg` property, resource ordering, mandatory hardware-block flag, platform device, absence of bound driver, PCIe/IOMMU/WLAN counts and touchscreen protocol-ready log. It returned:

```text
N71_S8000_PORT1_DESCRIPTOR_ONLY_LIVE_PHYSICAL_PASS
N71_PORT1_DEVICE_TREE_OF_NODE_AND_PLATFORM_DEVICE=YES
N71_PORT1_THREE_EXACT_MMIO_WINDOW_DESCRIPTORS=YES
N71_PORT1_HARDWARE_ACTIVATION_BLOCKED_FLAG=YES
N71_PORT1_NO_DRIVER_BOUND=YES
N71_PORT1_NO_PCI_DEVICES_NO_IOMMU_GROUPS_NO_WLAN=YES
N71_Z2_TOUCH_INITIALIZATION_PROTOCOL_READY=YES
PCIE_DMA_DART_MMIO_RF_ACTIONS_EXECUTED_BY_THIS_PROBE=NO
NATIVE_WIFI_ASSOCIATION_AND_DHCP_PROVEN=NO
HARDWARE_BCM4350_REQUESTER_TO_DART_SID_PROVEN=NO
```

The legacy [USB WLAN metadata baseline collector](../tools/n71_usb_wlan_fieldtest_collect.py) independently returned the same counts, including `N71_FIELDTEST_N71_PCIE_PORT1_PLATFORM_NODES_MATCHED=1`.

There is an existing separately compiled experimental `pcie-apple-s8000-guard.c` *source file* in a private research worktree. **That driver is not part of this booted kernel**, and the synthetic platform device has **no bound driver**. Its mere presence in `/sys` cannot access a physical register.

## Safety and engineering conclusions

- **Proved on hardware:** The previously working Linux kernel and touch initialization survive the additional N71 DTB node. Linux parses and exposes the physical port1/DART1 resource *descriptors* correctly. The USB-based host debugging channel remains functional.
- **Still blocked:** No physical PCIe root-port access or link training was attempted; no BCM4350 enumeration, PCIe BAR assignment, IOMMU DMA mapping, wireless interface, Wi-Fi association or DHCP. The actual PCIe requester-to-DART SID, IOVA ownership, fault isolation and shared root power/reset impacts remain **unproven**.
- **Protection:** No device MMIO mapping or read/write, no DART translation modification, no PCIe PHY/clock/reset operation, no internal NAND read/write during this test, and no baseband modification. The platform descriptor is inert without a driver. USB gadget Ethernet must **never** be mistaken for native Wi-Fi.
- **Touch:** `COMPLETE:PROTOCOL_READY` is a physically observed automatic touch-controller initialization sequence; it is **not** a new multitouch gesture test. Earlier separately confirmed multi-finger touch results remain independent.

The collector and [21 fail-closed synthetic regression tests](../tests/test_n71_usb_port1_descriptor_only_collect.py) ensure this exact descriptor-only milestone fails if the research block flag is absent, if any resource changes, or if a real PCIe endpoint, bound hardware driver, IOMMU group or native WLAN interface appears unexpectedly.

**Next milestone:** separately verify the experimental port1 *driver metadata* preflight and original Apple A9 shared-root sequencing. Do not remove the DART1 pre-MMIO guard or enable BCM4350 PCIe DMA until there is direct trustworthy evidence for the hardware requester/SID and cross-port isolation. Keep both the known-good previous RAM boot image and this descriptor-only image available for safe comparison.

**Privacy:** No original Apple kernelcache/ADT binary, private touchscreen firmware/calibration, USB MAC, hardware unique ID, raw terminal output, personal file path or wireless credentials are published.

**State at observation:** The iPhone was still running the new descriptor-only RAM Linux as `05ac:4142` with no reboot after the inspection.
