# N71/S8000 BCM4350C5 'albarossa': open-source upstream porting audit

**Date:** 2026-11-13. **Target:** owner-owned physical iPhone 6s, `apple,n71` / `apple,s8000` Samsung A9, genuine BCM4350C5 `albarossa` Wi-Fi module, PCIe port1 and its private DART1. **Scope:** public GitHub / upstream Linux code review, SOURCE ONLY, no executing third-party scripts, no on-device MMIO, no DMA and no iOS NAND operations.

## Executive result

**The upstream Linux BCM4350 PCIe FULLMAC host driver exists already** (`brcmfmac`, expected PCIe vendor/device `14e4:43a3`) and the actual owner's RAM Linux has physically booted with `CONFIG_CFG80211=y`, `BRCMFMAC=y`, `BRCMFMAC_PCIE=y`, `MSGBUF=y`, with all 17 original private firmware/NVRAM files validated on-phone byte-for-byte. A registered PCIe ID or firmware template DOES NOT prove the device was actually enumerated: the last physical Linux boot still reported **zero PCI devices, zero IOMMU groups and zero WLAN interfaces**.

The most useful new public upstream source is **OrchardLinux/orchard**. Its public firmware, DART and Apple PCIe code includes non-trivial candidate patches for BCM4350 OTP reads, WLAN power sequencing, S5L8960X DART fail-closed stream setup, and an A9 **S8003** PCIe device tree. However, **Orchard itself explicitly marks N71/S8000 Wi-Fi as 'missing'**, with no bring-up on that exact board. This is a porting foundation and a potential source of collaborators, **NOT** an available/validated N71 Wi-Fi driver.

## Exact search identity for maintainers

| Field | Grounded engineering description |
|---|---|
| Physical handset | iPhone 6s, `iPhone8,1`, `N71` / `N71AP` |
| SoC | Apple A9 **Samsung S8000**, not TSMC S8003/N71m |
| Original iOS WLAN module | Broadcom **BCM4350C5**, Apple `module-instance = albarossa` (independently verified from owner's original iOS IORegistry) |
| Linux device match | `brcmfmac`, BCM4350 PCIe `14e4:43a3` **expected by the driver**; NOT physically read from a running endpoint yet |
| Software firmware family | `brcmfmac4350c2-pcie.apple,albarossa` (`.bin`, `.clm_blob`, `.txcap_blob`) |
| Original Apple source firmware directory | `C-4350__s-C5/albarossa.*`, three genuine C5 blobs plus fourteen private `BLMA` NVRAM OTP profile candidates |
| Original Apple device topology | `apcie/pci-bridge1/wlan` -> DART1 dedicated logical `mapper-apcie1` lane 0 |
| DART1 original window | `0x602008000 / 0x4000` (owner-original ADT; same as Orchard's S8003 DART1 base, **address match alone not a SID proof**) |
| Native Linux Wi-Fi blocker | Missing **S8000-specific PCIe host controller/root-power/PHY/reset/link driver**, actual bus requester->DART1 stream SID and fault-isolated DMA mapping, plus module-specific OTP selection and radio/userspace validation |

## Ranked public sources and what can *actually* be reused

### 1. Orchard N71 board identity and negative support baseline — strongest platform reference

- Repository: <https://github.com/OrchardLinux/orchard>
- Exact [N71 board descriptor](https://github.com/OrchardLinux/orchard/blob/main/devices/n71/device.toml) specifies `apple,n71`, CPID `0x8000`, iPhone8,1 and explicitly `wifi = "missing"`; its own comments say the N71 bring-up is **not performed** in Orchard.
- [Orchard compatibility matrix](https://github.com/OrchardLinux/orchard/blob/main/docs/compatibility.md): experimental N71, separate S8003 N71m and T700x/T8010.
- Only use as a **reference**, not a working N71 build.

### 2. S8003 PCIe root complex and DART1 device-tree candidates — promising but **NOT S8000-compatible yet**

- [Orchard S8003 Apple PCIe binding](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0018-dt-bindings-pci-apple-t8010-pcie-Add-S8003.patch)
- [Orchard S8003 PCIe/DART0/DART1 DTS](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/devices/s8000/0002-arm64-dts-apple-s8003-Add-the-PCIe-root-complex-and-.patch)
- Source explicitly states: **S8003's PCIe root uses a T8010-like `phy-ip` block**; **S8000's PCIe root does not have `phy-ip`, so is intentionally NOT described by the S8003 DTS patch**. The binding also requires a different power-up/link-training sequence than T8010.
- S8003 DART1 base `0x602008000` and source `iommu-map = <0x200 &pcie0_dart1 0 ... 1>` propose SID/index 0 for S8003 port1. On N71 S8000 the owner-original ADT independently proves the **logical** WLAN mapper index0 -> S5L8960X packed TCR lane0, but **physical PCIe transaction requester->stream0, IOVA/TTBR/fault safety remain UNPROVEN**.
- **Never** copy `apple,s8003-pcie`, `phy-ip`, power domains, PERST GPIO, global reset or the above IOMMU mapping to `apple,s8000` without cross-port source/hardware validation. Owner's original Apple shared-root tuning has nonzero RMW records at offsets that coincide with selector ID2 on port0 NAND, port1 WLAN, port2 modem and port3.

### 3. Apple S5L8960X DART hardening — worth porting *offline before* any real DMA experiment

- [Refuse misaligned A9 DMA windows](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0005-iommu-apple-dart-Refuse-S5L8960X-DMA-windows-that-ar.patch).
- [Order stream translation as original iOS; block DMA on TLB/TTBR failures](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0006-iommu-apple-dart-Set-up-S5L8960X-translation-in-iOS-.patch).
- [Serialize packed per-stream TCR updates](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/iommu/0007-iommu-apple-dart-Serialize-S5L8960X-stream-control-u.patch).
- Static comparison with the owner's currently built A9 kernel source: `dma_min` exists, but `flush_error`, `tcr_lock`, `apple_dart_s5l8960x_setup_translation` and `apple_dart_domain_block` are **absent**. Thus these upstream patches contain specific missing defensive work and should be reviewed against the current kernel version, then adapted and compiler-tested **in a separate worktree only**.
- Hard caveat: a successful DART driver build does **not** establish a correct physical PCIe requester SID or permission to enable translation on the phone.

### 4. Broadcom BCM4350 OTP + board-NVRAM selection — the actual 14-profile selection lead

- [Read BCM4350 OTP](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/wifi/0005-wifi-brcmfmac-pcie-Read-the-BCM4350-OTP.patch).
- [Select Apple NVRAM based on OTP](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/wifi/0002-wifi-brcmfmac-Select-Apple-NVRAM-by-OTP-when-there-i.patch).
- Those patches provide an explicit technical route to choosing the real physical device's `BLMA` module vendor/version among the existing **fourteen generic genuine stock NVRAM profiles**. No guessing vendor/version and no publishing per-device OTP, MAC/WCAL calibration. OTP access is meaningful only once the PCIe endpoint and DMA safety are independently established.

### 5. BCM4350 power sequence — **relevant chip but different Apple board**

- [BCM4350 power-management patch](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0016-PCI-pwrctrl-apple-wifi-Add-BCM4350-power-sequence.patch) explicitly documents **iPad Air 2 / J81**, REG_ON, 100 ms stabilization and DEVICE_WAKE asserted.
- This is a useful model for driver structure, rollback after failed enable, and debug questions. **It is not proof that the N71 uses the same GPIOs, regulators, wake polarity, timing or shared root ownership**. Do not apply it physically to the S8000.

### 6. Other useful projects, with strict scope limitations

- [HoolockLinux](https://github.com/HoolockLinux) — owner project's boot/kernel baseline; hardware descriptions and m1n1/Pongo.
- [Linux upstream brcmfmac PCIe](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c) and [official Linux Wireless BCM4350 PCIe ID](https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html) — BCM4350 FullMAC driver; already compiled and booted in owner kernel, not an A9 PCIe host driver.
- [Mainline Apple PCIe](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c) — later T8103/M1-style root registers; not interchangeable with Samsung A9/S8000 without original-source verification.
- [Project Sandcastle](https://github.com/corellium/projectsandcastle) and [official support status](https://projectsandcastle.org/status) — valuable historical Pongo, firmware, tools and Apple hardware bringup, but supported beta builds there target iPhone 7+ rather than our A9 N71.
- [MacBook12 BCM4350 firmware research](https://github.com/WiltonH/macbook12-wifi-driver) — evidence of `14e4:43a3` on Intel Mac with OTP/NVRAM quirks; do NOT run its automatic installer or copy its regulatory/calibration profiles onto an N71.
- [Reported Nov 2 2026 iPhone 6s Omarchy Wi-Fi success](https://omarchyarchive.com/posts/hg64rymkfs-omarchy-iphone-6s-edition/) attributed to `@hg64rymkfs`: unverified community report; no matching publicly inspected source patch or independent N71/S8000 PCIe/PHY/DART link-test evidence. Treat as a lead for asking for source, **not** a confirmed drop-in fix.

## High-value questions for the original open-source contributors

When seeking help, provide the **non-identifying** board signature `apple,n71/apple,s8000`, original iOS WLAN module `albarossa`, verified DART1 window, current Linux kernel and protected port1 descriptor status, and [this sanitized project's evidence](N71_S8000_PHYSICAL_WIFI_C5_SOFTWARE_RAM_BOOT_2026_11_13.md). Ask specifically:

1. Has a **Samsung S8000 / N71** root controller without `phy-ip` been implemented and physically tested with port1 while protecting storage port0 and baseband port2? If so, please link to source/commit rather than a binary ROM.
2. Is the **actual physical Broadcom PCIe requester** wired to DART1 **stream0**, and how was the hardware SID and fail-closed IOVA / TLB fault containment demonstrated on S8000 (not S8003)?
3. Which original S8000 shared-root clock/PHY/REFCLK/PERST/CLKREQ and `device_wake` operations are **per-port versus global**, and what finite polling/recovery sequence avoids resetting the NAND controller?
4. Are there S8000-specific patches for Apple A9's original `AppleS8000PCIe` controller, or reliable Linux traces demonstrating enumeration of Broadcom PCIe `14e4:43a3` on N71?
5. Can their `brcmfmac` BCM4350 OTP parsing select stock `albarossa` BLMA vendor/version without exposing per-device serial, MAC or calibration fields?

Do **not** post any private firmware, authentic Apple ADT blobs, user MAC, ECID, UUID, iOS partition backups, raw kernelcache or personal paths in community threads. Use only sanitized reports and source references.

## Actual next development sequence (no premature hardware activation)

- **Now:** quarantine downloaded public Orchard patch texts in a private host-side `research/public-upstream/` folder; review architecture and compatibility. No code from third parties was executed.
- **Next offline:** stage an independently built DART correctness branch (window-alignment validation, per-stream TCR lock, original-iOS ordered TTBR setup, TLB failure fail-closed), with synthetic unit tests and no new DT enablement. Keep the live iPhone's RAM Linux and USB network unchanged.
- **Later, only after separate hardware qualification:** implement S8000-specific PCIe root driver/DT with bounded polling, protected port ownership and known rollback, then determine actual requester SID, enumerate the BCM4350, use OTP to select the correct private stock firmware NVRAM and perform native `wlan*` association on an authorized SSID independent of USB.
- **Success criterion:** physical BCM4350 `14e4:43a3` enumerates, correct stream fault isolation proven, native WLAN appears, authorized network association/DHCP succeeds, and storage/modem remain unaffected. A functioning USB Internet proxy is **not** that success.

**2026-11-13 live phone state:** known-good new ARM64 wireless-software kernel and genuine C5 firmware booted in RAM, USB `05ac:4142` reachable, Z2 touch protocol ready, no PCIe endpoints, IOMMU groups or native Wi-Fi. It remains untouched during this source investigation.
