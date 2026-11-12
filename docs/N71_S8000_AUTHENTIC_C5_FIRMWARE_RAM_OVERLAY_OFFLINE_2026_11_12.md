# N71/S8000: authentic Apple BCM4350C5 firmware embedded in an unbooted RAM-only Linux Wi-Fi preparation image

**12 November 2026 | Target:** owner's iPhone 6s N71/Samsung Apple A9.
**Result:** An additional **private, unbooted** Linux RAM boot image now embeds the genuine iPhone 6s `albarossa` BCM4350C5 Wi-Fi firmware components and fourteen original stock NVRAM alternatives, in addition to the already compiled built-in Linux Broadcom PCIe wireless stack. All original touchscreen, USB and passive PCIe guard RAM-rootfs entries, bootloader, Apple Device Trees and compressed Linux kernel were independently confirmed unchanged by the firmware addition.

**No physical PCIe/MMIO access, DART1 DMA, hardware reset, original iOS NAND change, DFU or RF activation was performed. This is not a working native Wi-Fi link.**

## Why this stage exists

The real, physically booted original RAM Linux has `CONFIG_WIRELESS=n`, making a native Broadcom WLAN interface impossible even if the PCIe controller were enumerated. The [previous stage](N71_S8000_BRCMFMAC_PCIE_KERNEL_AND_ALBAROSSA_C5_FIRMWARE_OFFLINE_2026_11_12.md) built a new ARM64 Linux kernel with `CFG80211=y`, `BRCMFMAC=y`, `BRCMFMAC_PCIE=y` and `BRCMFMAC_PROTO_MSGBUF=y`, then verified the Broadcom PCI device ID `14e4:43a3` and the driver firmware-name mapping.

However, that new software-only RAM image did not contain the firmware files. The next **offline** image adds them, preserving the previous image as an exact recovery reference. The original stock iOS 15.7.9 snapshot independently identifies the radio module as `albarossa`, and the locally held original iOS 15.8.8 restore firmware contains the genuine `C-4350__s-C5` `albarossa` binaries.

## Genuine original iPhone 6s firmware: precise private overlay

The firmware files are private, located only on the owner's Dell under a restricted `0700` directory and with `0600` file permissions. The owner-private builder takes the **previously staged and independently authenticated** original Apple source: no Internet download or third-party firmware substitution.

Exactly these files are added to the Linux initramfs at `/lib/firmware/brcm`:

| Type | New private Linux firmware image inventory | Count |
|---|---|---:|
| Original Apple `albarossa.trx` | `brcmfmac4350c2-pcie.apple,albarossa.bin` | 1 |
| Original Apple `albarossa.clmb` | `brcmfmac4350c2-pcie.apple,albarossa.clm_blob` | 1 |
| Original Apple `albarossa.txcb` | `brcmfmac4350c2-pcie.apple,albarossa.txcap_blob` | 1 |
| Stock C5 `P-albarossa_M-BLMA_V-...__m-....txt` variants | `brcmfmac4350c2-pcie.apple,albarossa-BLMA-<vendor>-<version>.txt` | 14 |

The 14 NVRAM alternatives are **stock template variants, not fourteen selected configurations**. The actual physical device's OTP module/vendor/version and antenna SKU have **not** been read from a verified safe platform endpoint and **none** of the profiles was selected or applied. The `brcmfmac` driver chooses firmware board-names using real OTP and device metadata when available. No serial number, real MAC, SysCfg, device-unique calibration, Wi-Fi passwords or original iPhone data were inserted into the image or committed.

This firmware inventory is intended for future correct `brcmfmac` lookup after the independent S8000 PCIe host + DART1 DMA safety work has passed. It does **not** authorize activating the BCM4350 now.

## Exact unbooted image provenance and non-destructive checks

**Previous unbooted ARM64 Wi-Fi software-only candidate:**

```text
Size: 12,283,074 bytes
SHA-256: 73a5beeba0793305c0fdace4f2fdf6fd844595a6030e18b7620b92a9dce144d7
```

**New, separate, private firmware-containing RAM candidate:**

```text
Size: 12,668,970 bytes
SHA-256: 5740307928ede4c731b8a69ee6a83d865c6bc18441b4abc7cd090e7d9565f25f
```

The new binary was constructed **without** modifying any original boot file, physical iPhone partition, iOS firmware, USB network configuration, kernel module on the device or remote Dell system route:

- The entire original **m1n1 loader and both Apple Device Trees** match the previous known-source candidate byte-for-byte.
- The **ARM64 Linux `Image.gz`** is byte-for-byte identical to the newly compiled, unbooted Broadcom PCIe-capable kernel (SHA-256 for the decompressed Image `563e1157ca2dcca91acc6eeef266062795b1db6078c8c109a14a0ad4068ff95d`).
- Original gzipped CPIO RAM rootfs was decompressed **only in Dell memory**. The complete original **23 CPIO entries**, including touchscreen Z2 initializer, USB gadget and passive fail-closed controller guard, preserve their original archive record and file contents. The exact original CPIO trailer and zero padding are also preserved.
- Exactly **one directory plus 17 authenticated private C5 firmware files** were inserted immediately before the archive trailer, yielding **41 CPIO members**. No original file contents or metadata were rewritten. The new initramfs was recompressed deterministically and its output re-verified.
- A second **independent GNU `cpio -it --quiet` parser** successfully parsed the entire new archive and checked **41 entries**, including exactly 17 firmware files and 14 `.txt` profiles; the ARM64 kernel image's architectural magic and original kernel hash were independently verified.
- The original known-good physically running kernel and the original **software-only** boot candidate both remain unchanged and available on the owner's Dell.

A new [strict offline private RAM image overlay verifier](../tools/n71_s8000_private_c5_ram_overlay_gate.py) independently validates the pinned old/new boot hashes, same loader/DTBs/compressed ARM64 kernel, exact original 23-member CPIO prefix and original trailer, exactly 18 new members and byte-identical private C5 firmware items. It **does not** need to publish original binaries. Companion [16 adversarial synthetic regression tests](../tests/test_n71_s8000_private_c5_ram_overlay_gate.py) cover malformed CPIO, unknown firmware, exact original-file preservation, wrong firmware bytes, missing OTP variants, injected extra CPIO entries and inappropriate hardware claims. No tests load the image on the phone.

Local Dell reproduction with locally held (nonpublic) owner binaries:

```bash
python3 tools/n71_s8000_private_c5_ram_overlay_gate.py \
  /private/previous-wifi-software-only-ram.bin \
  /private/new-c5-firmware-included-ram.bin \
  /private/original-c5-linux-brcm-firmware-stage
```

Actual pass result:

```text
N71_S8000_PRIVATE_C5_RAM_IMAGE_OVERLAY_OFFLINE_PASS
N71_M1N1_BOTH_DEVICE_TREES_AND_NEW_BRCM_PCIE_ARM64_KERNEL_IDENTICAL=YES
N71_ALL_23_ORIGINAL_TOUCH_USB_GUARD_CPIO_MEMBERS_AND_METADATA_IDENTICAL=YES
N71_3_ORIGINAL_APPLE_C5_FIRMWARE_COMPONENTS_INCLUDED_IN_RAM=YES
N71_ALL_14_GENUINE_STOCK_APPLE_C5_NVRAM_PROFILES_INCLUDED_IN_RAM=YES
N71_REAL_DEVICE_OTP_PROFILE_SELECTED=NO
N71_NATIVE_PCIE_DART_DMA_AND_BRCM4350_WIFI_ENABLED=NO
N71_NEW_PRIVATE_WLAN_FIRMWARE_IMAGE_HAS_NOT_BEEN_BOOTED=YES
N71_PRIVATE_BINARIES_CALIBRATION_AND_USER_IDENTIFIERS_EXPORTED=NO
```

## Next supervised physical milestone

The **actual iPhone** remains running the previous hardware-inert RAM Linux with the USB gadget `05ac:4142`, live USB Internet access through the restricted Dell Wi-Fi gateway, initialized touchscreen and a loaded passive PCIe guard. No hardware DART1 registers, IRQ, PCIe PHY, radio or flash were touched.

Once the owner is physically available to perform DFU on their own device, a **separate, supervised RAM-only boot** may test this new kernel's ability to start, preserve USB/touch functionality, report built-in `cfg80211` and `brcmfmac`, and enumerate the 17 private firmware files on the Linux RAM rootfs. As the Device Tree deliberately does **not** enable S8000 PCIe port1 or DART1, that is a **safe software-readiness smoke test**, **not** a Wi-Fi association test. A failed boot must fall back to the previous physically verified image; no NAND write or radio-controller experiment should be attempted as a workaround.

Native BCM4350 Wi-Fi still requires proven physical PCIe requester→DART1 SID routing, isolated IOVA/fault containment, shared NAND/modem root-controller safety, REFCLK/PERST/PHY control with bounded polling and rollback, proper onboard firmware OTP selection, and associated Wi-Fi userspace (`iw`, `wpa_supplicant`) before connecting independently to a network.

**Privacy:** This public repository contains only source, synthetic tests and source-derived engineering facts. Original Apple/IPSW firmware, all 14 actual private NVRAM templates, device calibration, personal identifiers, private RAM boot files and specific user workstation paths stay on the owner's local computer.
