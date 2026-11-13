# Physical iPhone 6s: N71/S8000 Linux Wi-Fi-software + original C5 firmware RAM boot PASS

**2026-11-13 (Europe/Rome), physical owner device: iPhone 6s N71/Samsung A9 S8000.**
**Milestone:** First physical RAM-only boot of the independently compiled AArch64 Linux kernel with `cfg80211` and Broadcom `brcmfmac` built-in, alongside all 17 privately staged genuine Apple BCM4350C5 `albarossa` firmware components. This is a **Wi-Fi software and firmware readiness milestone, not native WLAN enumeration or connection**.

## Proven physical boot chain

The owner's Dell Kubuntu host initially observed the real iPhone as iOS USB `05ac:12a8` on 13 November 2026 at 08:52 CET. The owner performed the DFU transition and ran the previously reviewed `palera1n`/PongoOS helper. The physical USB sequence reached:

- DFU recognized by the loader, checkm8 stage triggered.
- PongoOS USB `05ac:4141` confirmed at 08:57:24 CET.
- The owner manually executed `sudo bash scripts/n71-wifi-c5-pongo-ram-smoke.sh send`, which first enforced the exact private image length and SHA-256, then uploaded the RAM payload.
- Original Pongo terminal exit status `255` **does not by itself establish a boot failure**. The launcher independently confirmed `Uploaded 12668970 bytes` and USB reenumeration `05ac:4142`. The separate Linux USB shell/read-only smoke test then **succeeded on the physical phone**.

The **owner-private, not publicly distributed** image was exactly:

```text
m1n1-linux-n71-builtin-brcmfmac-c5-private-fw-inert-pcie.bin
size = 12668970 bytes
SHA256 = 5740307928ede4c731b8a69ee6a83d865c6bc18441b4abc7cd090e7d9565f25f
```

Its previously audited source-image diff preserved the original m1n1 bootloader, two N71/S8003 Device Trees, mandatory port1/DART1 hardware block, and original Z2 touch and USB rootfs service bytes. The only intended changes relative to the prior original RAM image were a newly built WLAN-capable ARM64 kernel plus 17 genuine owner-private C5 firmware files in the RAM filesystem. See [independently reproduced offline overlay audit](N71_S8000_AUTHENTIC_C5_FIRMWARE_RAM_OVERLAY_OFFLINE_2026_11_12.md).

## Real on-device acceptance

The Dell owner authorized read-only checks over the USB gadget IP `172.16.42.1`. Observed USB gadget: `05ac:4142`. Three USB ICMP probes succeeded with **0% loss**, approximately **2.23 ms average** latency.

The existing private, strictly read-only bounded phone collector `scripts/n71-usb-c5-ram-linux-readonly-smoke.py` returned:

```text
N71_S8000_BRCM4350C5_FIRMWARE_RAM_LINUX_SOFTWARE_SMOKE_PASS
N71_CFG80211_KERNEL_SYS_MODULE_PRESENT=YES
N71_BRCMFMAC_KERNEL_SYS_MODULE_PRESENT=YES
N71_ORIGINAL_APPLE_C5_FW_ALL_17_COMPONENTS_PRESENT_RAM_ONLY=YES
N71_ORIGINAL_14_STOCK_BLMA_GENERIC_PROFILE_VARIANTS_PRESENT=YES
N71_PHYSICAL_TOUCH_AND_USB_GADGET_INIT_READY=YES
N71_PCIe_DART1_HARDWARE_BLOCK_RETAINED=YES
N71_BCM4350_PCIE_ENDPOINTS_IOMMU_NATIVE_WLAN_ALL_ZERO=YES
N71_ACTUAL_BRCM4350_NATIVE_WIFI_LINK_AND_DHCP_PROVEN=NO
N71_PRIVATE_OTP_MAC_CALIBRATION_AND_FW_CONTENT_DISCLOSED=NO
```

An **additional independent physical read-only check** computed `sha256sum` of each of the **17 on-phone RAM firmware files** over the USB shell and compared privately to the 17 original firmware files on the Dell. **17/17 exact cryptographic matches PASS**, including three `bin/clm_blob/txcap_blob` common C5 components and fourteen stock generic NVRAM BLMA variants. No raw firmware, private hashes, OTP, serial, MAC, Wi-Fi key or calibration were printed in the public evidence.

The phone's Linux kernel release was checked read-only with `uname -r` as `7.3.0-rc1-g68aadac820d0-dirty`. Source/Kconfig private building and source-level Broadcom table verification additionally established `CFG80211=y`, `BRCMFMAC=y`, `BRCMFMAC_PCIE=y`, matching the published software readiness report. **The release string alone would not differentiate old/new images**; the real `cfg80211` and `brcmfmac` sysmodule presence plus all 17 RAM files distinguish the new boot.

The new phone Linux successfully performed a separate **public HTTPS URL probe via the Dell USB-only proxy**, reporting `HTTP/1.1 200 OK`, `X-N71-Uplink: dell-wifi-over-usb` and `wget` exit code 0. **This is a USB transport with Dell Wi-Fi Internet uplink, not on-device BCM4350 RF.** The Dell upstream fetch uses TLS; the USB-side HTTP proxy does not provide end-to-end device TLS for this BusyBox path.

The Z2 touchscreen test establishes **automatic protocol initialization / PROTOCOL_READY**. It is not a fresh pixel-accurate multitouch gesture/latency evaluation in this new boot.

## Safety boundaries and remaining work

- **Physical PCIe endpoints:** 0.
- **IOMMU groups:** 0.
- **Native WLAN network interfaces:** 0.
- **Real BCM4350 hardware PCIe enumeration/link:** **NOT** demonstrated.
- **Physical BCM4350 requester → DART1 SID, protected IOVA and fault isolation:** **NOT** demonstrated.
- **Hardware root port1 MMIO/PHY/clock/reset, storage port0 and baseband port2 independence:** **NOT** qualified.
- **Per-device OTP vendor/version and correct selection of one of the 14 stock NVRAM profiles:** not established; no guessing, no private calibration in public.
- **BLE / Bluetooth HCI:** independent research line, not newly tested by this boot.
- **iOS NAND flash/storage:** no erase, firmware flash or persistent iOS modification in this RAM boot test.

The existing A9 port1 device tree remains **hardware-inert**: reusing the original Apple global `apcie-common-tunables` values or copying modern Apple RID→SID controller writes into A9 is forbidden without independent isolation and recovery evidence. Future Linux PCIe work requires qualified controller-specific operations, explicit finite polling, DART1 fault containment and no impact to storage and baseband.

## Reproduce safely

The owner-specific, non-public scripts and binary are kept locally, not committed. On the Dell **after** a separately owner-supervised PongoOS boot, the already checked launcher is:

```bash
cd ~/Documenti/cyberdeck-a9-linux
bash scripts/n71-wifi-c5-pongo-ram-smoke.sh status
# Owner only, ONLY when the phone is already in PongoOS:
# sudo bash scripts/n71-wifi-c5-pongo-ram-smoke.sh send
python3 scripts/n71-usb-c5-ram-linux-readonly-smoke.py
```

Do **not** repeat the loader or module load now: the new kernel has already booted, and another Pongo upload is unnecessary. Leave the real device in current safe Linux for further read-only inspection and host-side driver research. Previous physically proven owner-private RAM payload and iOS recovery remain available.

**Source scope:** physical and private owner test on 2026-11-13, original C5 offline signature/evidence from 2026-11-12. All code and notes are in English; sensitive firmware, owner hardware identities and unpublished calibration remain private.
