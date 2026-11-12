# N71/S8000: physical fail-closed port1 guard module execution — PASS

**Date:** 12 November 2026
**Board:** owner-controlled physical iPhone 6s, Apple A9 Samsung S8000 / N71
**Evidence:** **physically executed on-device in RAM Linux**, not synthetic.
**Scope:** kernel module/platform `probe()` metadata validation with **mandatory `-EOPNOTSUPP`**, **not a functional PCIe controller or native Wi-Fi link**.

## Physical boot into corrected supervised RAM Linux

The owner physically re-entered DFU and PongoOS, then transferred the independently verified *corrected* private 100-µs supervisor RAM boot. Dell USB kernel journal showed:

- **15:36:44 CET:** physical DFU `05ac:1227`.
- **15:37:32 CET:** PongoOS `05ac:4141`.
- **15:37:46 CET:** **HoolockLinux USB `05ac:4142`** running on the actual phone, with CDC-NCM host-to-phone USB ping **2/2, zero losses**.

The privately staged boot file is **11,926,991 bytes** and SHA-256 **`490e65ae2857a6617268823698215c9bd6b920ab00830806f2914c81230c5fd3`**. This image differs from the previous physically booted guard image in *exactly one* N71 Device Tree research metadata property: `research,refclk-to-perst-delay-us` was corrected from **`0x100` = 256 microseconds** to **`0x64` = 100 microseconds**. All remaining boot bytes (m1n1, kernel, S8003 Device Tree, firmware, touchscreen auto-init, initramfs, module and launcher) are unchanged and previously verified. The previous [physical fail-closed 0x100 rejection report](N71_S8000_PORT1_GUARD_100US_FAILCLOSED_PHYSICAL_2026_11_12.md) remains valid historical evidence.

Read-only shell inspection on the physical phone independently confirmed the Device Tree property is now **`00 00 00 64`**, the touchscreen again reports **`COMPLETE:PROTOCOL_READY`**, the platform device is present, and the module was initially unloaded and no driver was bound.

## One and only one supervised guard insertion

Both the original [physical descriptor-only USB collector](../tools/n71_usb_port1_descriptor_only_collect.py) and [USB WLAN baseline collector](../tools/n71_usb_wlan_fieldtest_collect.py) passed before insertion. The owner-private ARM64 module and manual launcher on the running phone matched their pinned hashes:

- Guard `.ko` SHA-256: `40f2275047a3be6739b3d7760fb038033a818253f56cd9a495ad377013fe73d7`.
- Safety launcher SHA-256: `39e4a39b0e50c0eee0df2341161e4f937fe4c915d10c2b72966a4a45eae3a08b`.
- Actual kernel: `7.3.0-rc1-g68aadac820d0-dirty`.

After verifying zero PCIe endpoints, zero IOMMU groups, zero WLAN interfaces, no bound driver and `/proc/sys/kernel/modules_disabled=0`, the private, explicitly opt-in launcher was executed **once** in this new RAM Linux session:

```text
N71_GUARD_ONE_SHOT_ACCEPT=1 /usr/bin/n71_port1_guard_supervised.sh

N71_PORT1_GUARD_STATIC_METADATA_PREFLIGHT_PASS
N71_PORT1_GUARD_EXPLICIT_ONE_SHOT_RAM_MODULE_LOAD_BEGIN
N71_PORT1_GUARD_PHYSICAL_PLATFORM_PROBE_METADATA_PASS
N71_PORT1_GUARD_REJECTED_HARDWARE_ACTIVATION_AS_DESIGNED
N71_PORT1_GUARD_NO_PCI_ENDPOINT_IOMMU_OR_NATIVE_WLAN=YES
N71_PORT1_GUARD_KO_REMAINS_RAM_LOADED_UNTIL_NEXT_BOOT=YES
N71_PORT1_SUPERVISED_SCRIPT_RC=0
```

**Important precision:** A `probe()` function that successfully checks metadata then intentionally returns **`-EOPNOTSUPP`** has executed; it has **not bound** an active PCIe driver. Module initialization and platform-driver registration can succeed independently of a rejected platform probe.

A second, independent *read-only* on-phone shell session confirmed all of the following without trusting the launcher's output:

| Independent observable | Physical outcome |
|---|---|
| `/proc/modules` | `pcie_apple_s8000_guard` present |
| `/sys/module/pcie_apple_s8000_guard` | Present |
| `/sys/bus/platform/devices/602000000.pcie-port1-preflight/driver` | **Not bound** |
| Kernel ring buffer | Contains **port1/DART1 preflight passed; hardware BLOCKED** message |
| `/sys/bus/pci/devices` | **0** |
| `/sys/kernel/iommu_groups` | **0** |
| Native WLAN interfaces | **0** |
| Z2 touchscreen protocol init | `COMPLETE:PROTOCOL_READY` |
| HoolockLinux USB gadget | `05ac:4142`, stable |
| USB host-to-phone reachability | Two more pings received, zero packet loss |

No direct PCIe or DART1 registers were mapped, read or written by this driver. No PCIe host/root-complex training, PHY/clock/reset, DMA mappings, NAND/storage changes, modem reset or Wi-Fi RF operation occurred during the guard. The original fail-closed guard and the Apple A9 original MMIO resource metadata remain protected.

## What was proven — and what remains blocked

**Proven on actual Samsung N71 hardware:** independently reconstructed and byte-matched Linux kernel ABI; the owner-private AArch64 external module can be loaded by the matching kernel; its `platform_driver` registration invokes the Linux OF match and platform `probe()` with the new synthetic N71 port1 resources; the probe validates metadata and rejects hardware activation. Touch initialization and the USB Ethernet management channel survive.

**Not proven:** any BCM4350 PCIe endpoint enumeration, actual PCIe link training, physical requester-to-DART1 SID assignment, IOVA translation, DMA fault isolation, NAND-port0 and baseband-port2 independence under active root operations, hardware interrupt routing, actual Wi-Fi radio, association or DHCP. None of these should be inferred from a successful inert metadata probe.

**Module lifetime:** The physically booted kernel has `CONFIG_MODULE_UNLOAD=n`. This metadata-only guard module is now **loaded into this RAM session** and cannot be removed with `rmmod`; do not attempt to unload or force-remove it. A later physically attended RAM boot using the verified known-good image restores a session without the module. No iPhone flash or NAND restore is necessary.

## Next bounded engineering milestone

Research and validate the original A9 **shared PCIe root resource ownership** and *port1-only* PHY/REFCLK/PERST power sequence with original Apple evidence. Establish the real BCM4350 PCIe requester ↔ DART1 hardware SID and fault/IOVA isolation before writing a **separate, strictly gated** kernel driver that can interact with hardware. Preserve rescue boot, verified Z2 touch, USB management and storage/baseband safety. No kernel MMIO enablement is authorized by this metadata-only milestone.

**Privacy:** No owner-private original Apple ADT/kernelcache, proprietary firmware or calibration, executable module/boot image, unique device ID, USB MAC, personal paths, Wi-Fi credentials or raw identifying logs are published.
