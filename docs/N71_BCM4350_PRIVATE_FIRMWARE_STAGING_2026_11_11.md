# N71/S8000 Wi-Fi-first milestone — original BCM4350 firmware staged privately

**Date:** 2026-11-11. Goal: native station-mode BCM4350 Wi-Fi on the iPhone 6s N71/S8000, independently joining the same authorized WLAN as the Dell. USB networking is not acceptable as a substitute.

## Completed work

The owner's previously SHA-256-verified private iOS 15.8.8 (19H422) IPSW contains both Apple Broadcom wireless firmware source families:

- usr/share/firmware/wifi/C-4350__s-C2
- usr/share/firmware/wifi/C-4350__s-C5

Both were actually extracted from the private APFS image: 17 files in each family, including the original albarossa.trx (firmware), albarossa.clmb (country/location data), albarossa.txcb (transmit capability data), and 14 original module-profile text files.

A separate **PRIVATE** staging tree now contains two distinct Linux-ready candidate sets, C2/brcm and C5/brcm, with these three baseline filenames in each:

- brcmfmac4350c2-pcie.apple,albarossa.bin
- brcmfmac4350c2-pcie.apple,albarossa.clm_blob
- brcmfmac4350c2-pcie.apple,albarossa.txcap_blob

This proposed prefix comes from the original kernel source Broadcom PCIe firmware mapping for chip 0x4350. The source Linux kernel supports BCM4350 PCIe ID 14e4:43a3. The actual device WLAN PCIe endpoint revision is **NOT yet enumerated**. The C2/C5 match, firmware request basename, real board profile, and per-device SysCfg calibration **remain conditional**; do not load one revision blindly.

Each original profile file is preserved under a separate, private original-profiles subdirectory for its own revision, not auto-selected or mixed. Copy integrity was checked by SHA-256 and private file permissions are 0600. No Apple firmware, per-device NVRAM, calibration, Bluetooth firmware, or private original code is distributed via GitHub.

## Safe reproducibility tool

Public source: tools/n71_stage_bcm4350_firmware.py. It accepts an operator-owned extracted private source directory and a new private destination **outside** the public Git checkout; stages both families separately and refuses malformed, symlinked, missing, oversized or unexpected files, existing destinations, and unsafe output locations.

Local usage:

    python3 tools/n71_stage_bcm4350_firmware.py --private-source /private/usr/share/firmware/wifi --private-destination /private/linux-ready

Tests: tests/test_n71_stage_bcm4350_firmware.py contains 13 synthetic-only cases for isolation, private permissions, absent/replaced variants, missing original profiles, path safety, zero/oversized files and absence of hardware/network side effects. No firmware bytes are embedded in the tests.

## PMIC WLAN power: offline ARM64 object built

The original N71 Apple ADT links WLAN REG_ON to D2255 PMIC GPIO10 (I2C address 0-0074). The Bluetooth enable is a different pin (GPIO8). The phone's current Linux boot exposes the real 0-0074 I2C device, but the optional gpio_apple_pmic module is not loaded; no PCIe function or Linux wlan PHY exists.

The existing Apple PMIC GPIO driver from the exact Linux source tree was **cross-compiled successfully** into an ARM64 relocatable kernel object using a NEW isolated build tree and a noninteractive olddefconfig, without disturbing the validated Linux build. Its probe uses parent regmap and registers a gpiochip without changing GPIO states; the existing driver can write outputs if later explicitly requested by a consumer.

The phone's current kernel has CONFIG_MODULE_UNLOAD=n. Therefore loading new experimental modules into this boot cannot be rolled back through rmmod. **No module was loaded and no GPIO10 power state was written.** The first physical status test should occur under a separate supervised RAM-only boot with reviewed pin controls and verified rollback while preserving existing LCD, Z2 touchscreen, USB rescue and NAND.

## Critical remaining hardware sequence

1. Confirm real AppleARMIODevice IODeviceMemory resource ordering, common S8000 register semantics, and safeguards against affecting storage port0 and modem port2.
2. Qualify the D2255 GPIO10 readback and optional reversible WLAN power enable in an attended RAM-only test; avoid raw unvalidated PMIC register writes.
3. Bring up only S8000 PCIe port1 using verified PHY/refclock, clocks, reset, link training and MSI.
4. Qualify the actual DART1 stream/context ID, IOVA translations, page tables, faults and DMA isolation; never bypass the IOMMU.
5. Enumerate genuine BCM4350, identify chip revision and board-matched calibration, then select the correct private firmware and NVRAM.
6. Use brcmfmac/cfg80211 with secure WLAN authentication and pass the existing on-device Wi-Fi-only acceptance test against the Dell's gateway and LAN address. The iPhone's own PHY must carry the packets.

**Result:** Original C2/C5 Apple Wi-Fi firmware extracted and privately staged; PMIC GPIO driver ARM64 object built offline. Physical PCIe/DART and native Wi-Fi association are NOT yet operational.
