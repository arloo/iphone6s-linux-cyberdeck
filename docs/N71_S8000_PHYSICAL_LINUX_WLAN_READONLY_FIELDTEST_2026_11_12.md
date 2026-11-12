# N71/S8000 native RAM-Linux WLAN readiness: physical read-only test

**Date:** November 12, 2026
**Device:** owner-controlled iPhone 6s, Apple N71, Samsung S8000
**Evidence level:** **physically observed on the phone**, not an emulator or synthetic fixture
**Test scope:** read-only existing Linux `/proc` and `/sys` metadata. **No Wi-Fi DMA, RF, DART MMIO, NAND or PCIe host initialization attempted.**

## Physical Linux boot evidence

The private, previously staged RAM-only diagnostic boot was loaded with PongoOS 2.6.3. The loader console confirmed an upload of **11,821,980 bytes**, exactly equal to the pinned locally verified private boot-image length. After the `bootm` handoff the loader printed `LIBUSB_ERROR_IO`, but this was **not evidence of a Linux boot failure**: the Dell subsequently enumerated the phone as `05ac:4142`, **HoolockLinux USB Device**, with Linux USB CDC NCM Ethernet and a USB serial interface.

The Dell's local point-to-point USB gadget link `172.16.42.2 -> 172.16.42.1` delivered **2/2 ICMP echoes** with zero packet loss immediately after boot. This is a **USB** connection; it is explicitly **not native Wi-Fi**.

The genuine on-device kernel was independently read through the Linux USB-only shell:

```text
LIVE_KERNEL=7.3.0-rc1-g68aadac820d0-dirty
BOARD=apple,n71
BOARD=apple,s8000
```

## Actual read-only on-device PCIe / IOMMU / WLAN test

The new diagnostic [`scripts/n71_wlan_readonly_fieldtest.sh`](../scripts/n71_wlan_readonly_fieldtest.sh), executed on the actual iPhone by the private RAM init hook, wrote a concise sanitized RAM-only log at `/run/n71_wlan_readonly_fieldtest.log`. The [strict USB collector](../tools/n71_usb_wlan_fieldtest_collect.py) returned `N71_WLAN_LINUX_RAM_ONLY_READONLY_FIELDTEST_PHYSICAL_PASS`, and a second read-only session independently read back the exact same values:

| On-device Linux observable | Physical result |
|---|---|
| Board compatible both `apple,n71` and `apple,s8000` | PASS |
| Linux `/sys/bus/pci` exists | YES |
| Enumerated `/sys/bus/pci/devices` entries | **0** |
| `/sys/kernel/iommu_groups` entries | **0** |
| Port1 platform-device name matches | **0** |
| DART1 platform-device name matches | **0** |
| WLAN-named network interfaces | **0** |
| Diagnostic performed MMIO, DMA, reset or radio commands | **NO** |

These observations are evidence about the **specific RAM kernel and Device Tree actually booted**. The preexisting touchscreen/LCD/USB RAM image is intentionally reused; the experimental N71 PCIe port1 and DART1 driver worktrees were **not linked into or activated by this boot**. Therefore zero PCIe/DART1 devices are consistent with the existing RAM image, and are **not evidence that the original Broadcom chip or physical link is defective**.

A second on-phone console read also confirmed the original touchscreen auto-initialization sequence:

```text
[n71-z2-auto] START
[n71-z2-auto] WAKE_OK
[n71-z2-auto] D9_FIRST_OK
[n71-z2-auto] D9_SECOND_OK
[n71-z2-auto] D9_SURFACE_OK
[n71-z2-auto] TYPE1_SETUP_OK
[n71-z2-auto] COMPLETE:PROTOCOL_READY
```

This confirms the **touch protocol initialization and status reporting** on this boot, not a newly performed multi-finger gesture acceptance test. Earlier separate physical multi-finger touch tests remain documented independently.

## Consequences for bringing native BCM4350 Wi-Fi up

1. **Practical Linux baseline established.** The kernel is running on physical N71, USB debugging and the read-only diagnostic work, and the test is repeatable after an attended RAM-only boot.
2. **No Linux PCIe port1 enumeration yet.** The actual boot image does not activate the experimental PCIe host or DART1. The BCM4350 is **not** enumerated under Linux and no native WLAN interface exists.
3. **Hardware enablement remains subject to evidence.** Original Apple ARM64 static verification supports the DART1 logical mapper0, original 4×4 TTBR register layout and TTBR/PTE **software field encodings**, but does **not prove physical PCIe requester-to-hardware SID, IOVA ownership, interrupt/fault isolation, cross-port effects or safe port1 power/clock/reset ordering**.
4. **The existing DART1 Linux experimental pre-MMIO block remains required.** Do not disable it or assert a functional PCIe/DMA path simply because the diagnostic now runs on the device.
5. **Next engineering work:** validate an isolated port1-only device-tree/host controller exposure that performs no unsafe MMIO and does not touch port0 NAND or port2 baseband; separately determine physical hardware requester/SID and fault behavior before allowing active DMA. Afterwards, stage a *new*, separately hashed supervised RAM-only experimental image, preserving the already proven touchscreen/LCD/USB rescue.

This record publishes only sanitized, user-authorized hardware-test results. No proprietary Apple kernel/firmware/calibration, raw console captures, private network credentials, USB MACs, unique device identifiers, or personal file paths are included.

**State at end of test:** actual iPhone still running RAM-only HoolockLinux as USB `05ac:4142`; no device reboot, NAND flashing or PCIe/DART MMIO changes during read-only verification.
