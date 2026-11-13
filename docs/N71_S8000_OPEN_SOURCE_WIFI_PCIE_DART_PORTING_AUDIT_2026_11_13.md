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


## Follow-up: full S8003 **host-driver** patch series found (critical, 2026-11-13)

A second pass over the entire Orchard source tree found an actual **S8003** Apple H8P/H9P **PCIe controller implementation** beyond just the S8003 DT/binding. This significantly improves our source blueprint, but it is **not** an already qualified **Samsung S8000** controller.

- [S8003 PCIe host driver](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0019-PCI-apple-h9p-Add-S8003-support.patch) maps S8003 root register selectors (port stride `0x80`), PHY/REFCLK/PERST# sequencing, finite 250ms/500ms control/link polling and bounded shutdown, and uses `apple,s8003-pcie`, *not* `apple,s8000-pcie`. Its own source notes a T8010-like `phy-ip` block, **absent from original S8000**. Some original software selector offsets resemble the owner-decoded S8000 root operations, but their PHY electrical meaning is NOT portable by assumption.
- [S8003 common/PHY/port tunables](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0020-PCI-apple-h9p-Apply-the-S8003-tunables.patch) are *S8003- and J71t-specific*. Do **not** replay on N71: the actual S8000 global common tunables have four port-specific selector aliases including protected NAND port0 and modem port2. Independent source/electrical qualification is mandatory.
- [S8003 storage-first ordering and bounded late port retry](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0024-PCI-apple-h9p-Bring-up-the-S8003-storage-port-first-.patch) explicitly explains the **IOMMU routing hazard**: its `iommu-map` ties bus1 to storage/DART0 and bus2 to port1/DART1. If storage disappears first, a later endpoint could move to bus1 and use the **wrong DART**. This is an essential **source-level safety design constraint** for any future S8000 port. We have NOT proven S8000 physical bus numbering, so do not import the S8003 map; implement a fail-closed bus-identity/stream ownership check before enabling any DMA.
- [S8003 NVMMU ordered initialization](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0025-PCI-apple-h9p-Initialize-the-S8003-NVMMU-in-iOS-s-or.patch) and [NVMMU invalidation/FIFO](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0021-PCI-apple-h9p-Follow-iOS-s-S8003-NVMMU-init-and-inva.patch) demonstrate why storage and global root control must remain separately protected; not authorization to touch NAND/NVMMU on the owner phone.
- S8003 interrupt and power-management patches [0022](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0022-PCI-apple-h9p-Leave-the-S8003-port-interrupts-alone.patch) and [0023](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/pci/0023-PCI-apple-h9p-Clear-the-S8003-PME_Turn_Off-request-w.patch) are possible architecture patterns, **not validated S8000 register sequences**.

### Read-only application-context check against the current private Linux source

On the Dell, the project source tree has its existing private touch and research-guard edits. A **non-mutating** `git apply --check` inspected five downloaded public patch texts:

| Patch | Result against current worktree | Required next step |
|---|---|---|
| DART `0005`, refuse bad DMA windows | **Context matches** | Isolated source worktree, compile and synthetic regressions |
| Broadcom OTP `0005`, read BCM4350 OTP | **Context matches** | Isolated source worktree, compile; never read OTP until PCIe safely enumerated |
| DART `0006`, iOS-order translation | **Does not apply directly** | Context/dependency review and manual rebase |
| DART `0007`, packed stream TCR lock | **Does not apply directly** | Context/dependency review and manual rebase |
| BCM4350 WLAN power `0016`, J81 | **Target source file absent** | Requires separate pwrctrl framework; not N71 GPIO-safe |

**No upstream patch was actually applied** to the owner's working Linux tree, compiled into the currently running phone, or executed on any hardware. The static feasibility check is not a functional test. All original Apple firmware/OTP/calibration remain private. The phone still runs the last verified RAM Linux with Wi-Fi software and unchanged inert port1.

**Priority update:** Reuse the S8003 implementation's **architecture, bounded state machine and error rollback design** as abstract engineering references, and prioritize S5L8960X DART hardening in a separate offline worktree. Implement the **S8000-only** root and PHY semantics with independent verification against original N71 evidence; prohibit global root tuning replay, NAND reset and requester-to-SID guesses.

## Evidence correction — 2026-11-13: Bluetooth chip id 110 is NOT PCIe Wi-Fi enumeration

A third-party research summary used [this project's issue #3](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/3) to claim that the BCM4350 Wi-Fi PCIe endpoint was publicly enumerated on an iPhone 6s N71/S8000. We verified that issue and its two comments directly through GitHub. **They contain no Wi-Fi PCIe enumeration log.**

- The log `Bluetooth: hci0: BCM: chip id 110` and `Bluetooth: hci0: BCM4350C5` is from the Bluetooth controller on Apple UART HCI, **not a PCIe config-space read**. HCI chip ID 110 is not the PCI vendor/device identifier.
- The actual Nov 9 physical N71 Bluetooth experiment did load owner-private Patchram build 0825 into RAM, with **25 passive BLE advertisements in 12 seconds**. This demonstrates HCI/BLE RF reception, not Bluetooth pairing and not Wi-Fi.
- The [upstream Linux Wireless brcmfmac PCIe device list](https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html) documents expected BCM4350 ID **14e4:43a3**, but source driver support and board firmware availability do **not** prove the endpoint has appeared on the N71 PCIe bus.
- A repeat **physical read-only smoke test** of the owner's currently running N71 RAM Linux with cfg80211/brcmfmac and 17 original C5 files still returns `N71_BCM4350_PCIE_ENDPOINTS_IOMMU_NATIVE_WLAN_ALL_ZERO=YES` and a retained pre-MMIO hardware activation block.
- [AppleBCMWLANCompanion](https://github.com/0xFireWolf/AppleBCMWLANCompanion) addresses Broadcom firmware on supported **macOS** configurations; it is not a demonstrated N71/S8000 Linux PCIe/DART1 port.
- [Orchard N71 support status](https://github.com/OrchardLinux/orchard/blob/main/devices/n71/device.toml) says `wifi = "missing"`. Its existing S8003 host driver uses a T8010-like `phy-ip` region that the Samsung S8000 does not expose.

**Proof still required:** actual safe S8000 PCIe config-space vendor/device 14e4:43a3 with stable port1 bus numbering; correct physical PCIe requester-to-DART1 SID, IOVA fault containment and protected NAND/baseband ports; then brcmfmac firmware startup, authenticated wireless association, DHCP and traffic. **Never interpret `chip id 110` as that PCIe proof.**

This corrects the **specific cited claims** only; it does not assert that no unpublished work elsewhere could exist. No on-device hardware writes or Apple firmware disclosure were involved.
