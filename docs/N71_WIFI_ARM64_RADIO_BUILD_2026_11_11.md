# N71/S8000 Wi-Fi-first: repeatable ARM64 radio objects

Date: 2026-11-11. Objective: the iPhone 6s N71/S8000 must connect using its own onboard BCM4350 PCIe radio to the same authorized WLAN as the Dell. USB network forwarding never counts as native Wi-Fi.

## Completed offline compilation

The known-good Linux framebuffer/Z2 multitouch kernel configuration originally disabled WIRELESS and WLAN. This explains why enabling CFG80211 and BRCMFMAC alone was silently rejected by Kconfig.

A fresh private, out-of-tree build derived from the known-good kernel configuration now has:

- CONFIG_WIRELESS=y; CONFIG_WLAN=y; CONFIG_NETDEVICES=y
- CONFIG_CFG80211=m; CONFIG_BRCMUTIL=m; CONFIG_BRCMFMAC=m
- CONFIG_BRCMFMAC_PCIE=y; BRCMFMAC_USB=n; BRCMFMAC_SDIO=n
- CONFIG_APPLE_DART=y and CONFIG_GPIO_APPLE_PMIC=m retained.

All four aggregate driver components compiled as relocatable ELF64 AArch64 objects: drivers/gpio/gpio-apple-pmic.o, net/wireless/cfg80211.o, drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.o and drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.o. No modules or firmware were installed on the phone. These objects are not yet linked .ko files or a newly bootable kernel.

The public script scripts/build_n71_wifi_objects_offline.sh takes three arguments: a pinned Apple Linux tree, the private known-good .config and a fresh private output path. It checks the target, enables Kconfig menu dependencies, builds the four objects and confirms AArch64 format; it refuses source-tree destinations, existing outputs and incompatible configs. Tests/test_n71_wifi_arm64_offline_build.py contains 13 synthetic fail-closed safety tests.

## Other prepared components

The private original N71 iOS 15.8.8 IPSW has supplied separate Apple BCM4350 C2 and C5 Albarossa firmware/profile sets, already extracted and staged exclusively outside Git. Which set matches the actual endpoint and per-device calibration is still unknown until PCIe enumeration.

D2255 PMIC GPIO10 is the N71 WLAN REG_ON line, distinct from Bluetooth GPIO8. The PMIC driver compiled but no GPIO10 read/write was carried out. The current RAM Linux kernel has CONFIG_MODULE_UNLOAD=n, making unreviewed module tests on that boot irreversible without reboot.

## Actual blocker

The Dell host lost the iPhone 05ac:4142 USB gadget at 2026-11-11 19:13:45 CET. Subsequent read-only checks found no Apple enumeration or ICMP response at 172.16.42.1. We cannot assume the phone remains online; no reset, DFU reflash, PCIe MMIO, DMA or NAND operation has been performed.

Native Wi-Fi remains dependent on verified AppleARMIODevice physical resource ordering, safe S8000 port1-only refclock/reset/link training, DART1 SID/IOVA/DMA isolation, real BCM4350 enumeration, matching firmware/NVRAM and genuine WLAN authentication. The mainline Apple PCIe driver targets other Apple SoC families and its register offsets are not interchangeable with S8000.

Outcome: genuine offline ARM64 radio-stack compilation completed. The onboard S8000 PCIe WLAN PHY has NOT yet been enumerated or connected.


## Reproduction post-check

A second, fresh out-of-tree private build successfully compiled all four original Linux source objects as AArch64 ELF. The first verification attempt was tripped by an Italian host locale (readelf used the translated label 'Macchina' rather than 'Machine'); the public build script was fixed to force LC_ALL=C during architecture validation. The four actually produced objects were then checked using the corrected locale-independent predicate and all passed. No Apple firmware data is included in the public script or tests.
