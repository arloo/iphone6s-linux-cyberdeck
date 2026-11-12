# N71/S8000: native Broadcom PCIe Wi-Fi software and authentic BCM4350C5 firmware staged offline

**12 November 2026 | Hardware:** physically identified iPhone 6s N71, Samsung Apple A9 S8000.
**Scope:** two **strictly offline** preparations: a newly compiled ARM64 Linux kernel with the Broadcom PCIe Wi-Fi software stack, and firmware staged privately from the owner's original stock-iOS firmware. **The new kernel image has NOT been booted on the iPhone. Native Wi-Fi, PCIe enumeration and DMA are NOT working or qualified.**

## 1. A verified missing prerequisite in the real working kernel

The previously physically booted, known-good N71 Linux kernel, SHA-256:

```text
fbf9ec6754245d48922e6da8b82c90e6c985ea088ed8ab896397af8e3f9f7845
```

contains:

```text
# CONFIG_WIRELESS is not set
# CONFIG_WLAN is not set
# CONFIG_RFKILL is not set
CONFIG_PCI=y
CONFIG_PCIE_APPLE=y
CONFIG_APPLE_DART=y
CONFIG_BT=y
```

Even if a PCIe endpoint became visible, this kernel would not register a functioning native Wi-Fi network interface via `brcmfmac`; its generic wireless stack was **not built**. This was a software blocker independent of the unqualified physical S8000 PCIe controller and DART1.

## 2. Independent kernel build completed — hardware access still blocked

The owner-controlled Dell created a **separate copy** of the exact known-good A9 Kbuild output and used the same local kernel source worktree and cross toolchain. Only the independent output directory's Kconfig was modified and built. The original physical Linux `Image` was independently verified unchanged afterwards.

The following features are now **built-in** (`=y`) in the **new, unbooted** image:

```text
CONFIG_WIRELESS=y
CONFIG_WLAN=y
CONFIG_RFKILL=y
CONFIG_CFG80211=y
CONFIG_BRCMUTIL=y
CONFIG_BRCMFMAC=y
CONFIG_BRCMFMAC_PCIE=y
CONFIG_BRCMFMAC_PROTO_MSGBUF=y
CONFIG_PCI=y
CONFIG_FW_LOADER=y
CONFIG_BT=y
```

Broadcom SDIO/USB transports and NL80211 test mode were not enabled. The existing Apple PCIe and DART kernel configuration was retained, without adding a functional S8000 PCIe/DART1 hardware platform node. The experimental metadata-only research guard was not promoted into an active hardware driver.

The **new ARM64 kernel successfully compiled and linked**:

| Private local output | Verified result |
|---|---|
| Linux ARM64 `Image` | **19,833,344 bytes**, SHA-256 `563e1157ca2dcca91acc6eeef266062795b1db6078c8c109a14a0ad4068ff95d` |
| `Image.gz` | **8,191,035 bytes**, SHA-256 `8881a862d7bf4688ebfaceeddf39d4cb47afb8f1d5e21833481177b55cd82c30` |
| Original physically proven `Image` | Byte-for-byte **unchanged** |

The kernel Linux source independently contains `BRCM_PCIE_4350_DEVICE_ID=0x43a3`, a `brcmfmac` PCI table entry for Broadcom `14e4:43a3`, `BRCM_FW_ENTRY(BRCM_CC_4350_CHIP_ID,0x000000FF,4350C)`, the `brcmfmac4350c2-pcie` firmware template and the Broadcom PCIe `MSGBUF` protocol. Upstream background: <https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html>. That provides a matching **software driver**, not proof of S8000 host-controller compatibility, a correctly selected real chip revision or radio performance.

The [public offline firmware-driver and kernel-image fail-closed verifier](../tools/n71_s8000_brcmfmac_pcie_kernel_readiness_gate.py) requires original known-good kernel hash, differences in the actual new AArch64 `Image`, the full configuration chain, unchanged existing Bluetooth/DART/Apple PCIe options and the exact Broadcom PCIe firmware/device-ID source-table semantics. The companion [18 synthetic regression tests](../tests/test_n71_s8000_brcmfmac_pcie_kernel_readiness_gate.py) reject missing `WLAN`, missing `CFG80211` or `BRCMFMAC_PCIE`, unapproved transports, invalid driver IDs, wrong firmware lookup and a changed known-good kernel.

## 3. Original Apple iPhone 6s BCM4350C5 firmware found and verified

The Dell already holds the original iPhone 6s stock-iOS 15.8.8 restore IPSW, and a **previously extracted** proprietary N71 firmware directory:

```text
usr/share/firmware/wifi/C-4350__s-C5/
```

Crucially, the owner-captured **real stock-iOS N71 WLAN IORegistry** exposes the original `module-instance` as **`albarossa`**. This resolves the actual board-firmware name: `albarossa` **is the iPhone 6s/N71 module**, not an unrelated Apple device. Independent published Apple Device Tree radio inventories also identify iPhone8,1 / N71AP / 4350 / albarossa.

The **three original Apple C5 source files** were compared byte-for-byte to existing Linux-brcmfmac-compatible privately staged copies:

| Original iOS C5 source | Private Linux firmware filename | Bytewise match |
|---|---|---|
| `albarossa.trx` | `brcmfmac4350c2-pcie.apple,albarossa.bin` | PASS |
| `albarossa.clmb` | `brcmfmac4350c2-pcie.apple,albarossa.clm_blob` | PASS |
| `albarossa.txcb` | `brcmfmac4350c2-pcie.apple,albarossa.txcap_blob` | PASS |

Here, `4350c2` is the Linux firmware **family naming convention** used by its source mapping. The corresponding genuine Apple firmware package directory is `C-4350__s-C5`; this is not a direction to mix unrelated board files.

There are also **14 authentic Apple stock NVRAM profile alternatives** named for the `BLMA` module family, across module vendor/version variations. Their presence does **not** establish which one matches the physical unit's OTP.

A new dedicated **owner-private** directory now holds exactly **17 files**: the three verified C5 firmware blobs and all fourteen profile alternatives, each renamed to the Linux `brcmfmac4350c2-pcie.apple,albarossa-BLMA-<vendor>-<version>.txt` convention and copied with exact source-byte verification. Directory access is restricted to the owner. Nothing was installed on the phone, and neither firmware nor per-device private SysCfg, MAC, WCAL, Bluetooth calibration or OTP fields were uploaded.

The [public original-iOS-to-private-Linux firmware verification tool](../tools/n71_s8000_albarossa_c5_firmware_provenance_gate.py) checks the original stock-iOS `module-instance`, the exact three binary copies, all 14 expected profile variants, correct board-prefix conversion and unchanged bytes. The [16 synthetic fail-closed tests](../tests/test_n71_s8000_albarossa_c5_firmware_provenance_gate.py) reject mismatched firmware, incorrect board, missing/extra profiles and malformed source names. Only fixed status flags are emitted; no original firmware/profile or user identity data is exposed.

## 4. New separate RAM-only candidate prepared, but **NOT** physically booted

A strictly local builder constructed a new owner-private RAM boot file by replacing only the Linux `Image.gz` member inside the last **physically verified** 100-µs-supervised baseline. It verified the old pinned boot SHA and raw known-good kernel SHA.

```text
m1n1-linux-n71-wlan-software-builtin-inert-port1.bin
```

- **12,283,074 bytes**.
- **SHA-256:** `73a5beeba0793305c0fdace4f2fdf6fd844595a6030e18b7620b92a9dce144d7`.
- Exactly **one boot-image section changed**: compressed ARM64 Linux kernel.
- Byte-identical: original m1n1 loader, **both Apple Device Trees**, the inert port1/DART1 synthetic descriptor and mandatory hardware-block flag, the complete original RAM filesystem, USB gadget, Z2 touch initializer and manual passive module.
- The 17 private firmware files remain in the **separate Dell-only firmware stage**. They have **not** yet been added to the RAM image or supplied to the iPhone.
- No physical DFU, boot of the new candidate, original iOS NAND/flash write, MMIO read/write, DART DMA, PCIe clock/PHY/reset action or Broadcom RF association was performed.

The real iPhone **continues running the prior known-good RAM Linux** (USB gadget `05ac:4142`) and its previously loaded, intentionally hardware-blocking A9 platform research guard. USB Internet access through the existing restricted Dell Wi-Fi proxy continues to be a **USB transport**, not native Wi-Fi.

## 5. Real blockers still open

**P0 — hardware:** Independent safety verification of controller-wide PCIe power/clock/reset ownership, port0 NAND and port2 modem isolation, full link bring-up with finite polling and safe rollback. Establish **real PCIe transaction requester to DART1 stream/SID**, IOVA aperture and fault containment. The Apple original WLAN logical mapper `reg=0` is software-proven through packed TCR lane0, but its actual physical requester routing remains unproven. Do not bypass the pre-MMIO DART guard or replay the entire shared-root tuning bank.

**P1 — platform:** Build an A9/N71-specific Device Tree with a properly bounded, independently validated native PCIe controller and DART1 binding. The current synthetic port1 node is **only an inert metadata proof**.

**P2 — radio firmware and userspace:** Read the real module OTP type/vendor/version and choose the matching **one** of 14 C5 NVRAM profiles; validate and retain device-specific Wi-Fi address/calibration only in a private, owner-controlled location, never the public repository. Supply verified radio firmware to the future RAM Linux filesystem. Add ARM64 wireless userspace (`iw`, `wpa_supplicant` and network DHCP tools); on the currently running RAM Linux, `iw` and `wpa_supplicant` are absent.

**P3 — acceptance:** Successful, truly native `wlan*` interface from physical BCM4350 PCIe device, correct regulatory calibration, safe connection to an authorized Wi-Fi network, DHCP and data transfer independent of Dell USB. Bluetooth HCI/patchram validation is separate. **No claim of full Linux cyberdeck functionality is yet warranted.**

Hardware work is substantially better understood and the **software plus original firmware prerequisite is now independently prepared**, but the above critical physical safety and functional tests are not complete.
