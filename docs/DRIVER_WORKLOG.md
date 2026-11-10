# Apple A9 hardware driver worklog

Updated November 9, 2026. Device: iPhone 6s **Samsung A9 / S8000 / N71**. Do not extrapolate these runtime observations to TSMC/S8003.

## 1. Bluetooth: HCI control plane already responds

Runtime kernel on the phone: `7.3.0-rc1-g6831bc701a6c`.

The Broadcom HCI UART driver enumerates `hci0`, and firmware-less kernel logs report:
```text
Bluetooth: hci0: BCM: chip id 110
Bluetooth: hci0: BCM4350C5
Bluetooth: hci0: BCM4350C5 (003.006.007) build 0000
Bluetooth: hci0: BCM: firmware Patch file not found, tried:
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.hcd'
```

An original static AArch64 tool `tools/hci-probe.c`, using the BlueZ HCI kernel ABI, successfully ran on the phone. Read-only HCI info returned:
```text
hci0 name=hci0 flags=0x00000005 type=3 acl_mtu=1021 sco_mtu=64
Features: bf fe cf fe db ff 7b 87
Stats: cmd_tx=76 evt_rx=76 err_rx=0 err_tx=0
```

The tool **does not print the controller's device-unique address**. This is evidence for working HCI control transport, **not** evidence of successful RF scanning, pairing or Bluetooth firmware initialization.

### Vendor firmware lead

The [Omarchy-iPhone6s Bluetooth research](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/drivers/bluetooth.md) documents BCM4350C5 firmware embedded in `/usr/sbin/BlueTool` within an official iPhone 6s IPSW, including distinct USI/Murata module profiles. Its extraction script is maintained upstream:
[extract-bt-firmware.py](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/tools/extract-bt-firmware.py).

**Do not upload any extracted HCD** or device-specific MAC/NVRAM. Do not assume the original researcher's USI module variant matches another N71. The extracted firmware must be checked against the local hardware variant and verified at runtime before reporting RF functionality.

## 2. Touch: A9 SPI/Z2 patches staged separately

The tested kernel config has `CONFIG_INPUT_TOUCHSCREEN=n`. Six GPL-licensed research patches from [Omarchy-iPhone6s](https://github.com/modpunk/Omarchy-iPhone6s/tree/main/patches/touch) were successfully **adapted offline** onto a separate worktree based on our known-good kernel source `154668a0c30e`. The sixth patch's `s800x-6s.dtsi` hunk required manual integration because our source already contains PMIC/Bluetooth/battery additions; the two N71-specific DTS hunks applied as provided.

Test build configuration:
```text
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_TOUCHSCREEN_APPLE_Z2=y
CONFIG_SPI_APPLE_S5L=y
CONFIG_SPI_APPLE=y
```

The upstream board DTS intentionally sets the touch child `status = "disabled"` because correct analog power, firmware loading and per-device calibration hand-off are not yet ready. **Compiling a driver is not a working touch interface.** The [upstream N71 touch worklog](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/drivers/touch.md) reports partial coarse/quadrant-position response from later unmerged firmware/protocol experiments, with unresolved high-resolution coordinates. No blind firmware-command fuzzing should be performed on a device lacking a reliable rollback/recovery path.

## 3. Wi-Fi: PCIe host controller is the initial blocker

The tested Linux image has `CONFIG_WLAN=n`, and the live N71 device exposed **no PCIe devices**. Other [N71 hardware mapping research](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/hardware.md) identifies the Wi-Fi component as a Broadcom BCM4350 behind **Apple A9 PCIe port 1**. This hardware layout is an upstream research finding; no actual PCIe endpoint appeared on our current Linux boot.

Enabling generic `brcmfmac` alone cannot provide working Wi-Fi if the S8000 PCIe controller, clocks, power domains, root complex and DART mapping do not enumerate properly. Prioritize a safe, read-only enumeration probe for PCIe port 1 **before** attempting firmware upload or WLAN association. Avoid PCIe/NVMe writes: the internal iOS storage may share the same root complex.

## Safe procedure and community contribution rules

- Work on separate kernel worktrees, retain the already-booting Linux image for recovery.
- Build and validate each patch set offline before attempting a new RAM-only boot.
- Test touch/BT/WLAN on their own subsystem, with controlled steps and sanitized logs.
- Do not publish Apple firmware, IPSW/APFS files, calibration, identifiers, passwords, private keys or raw physical memory.
- Do not mistake driver bind or interface creation for full peripheral functionality.

## 4. Bluetooth Patchram and passive BLE radio — verified on N71/S8000

**2026-11-09: firmware initialization and real RF reception succeeded.**

1. Verified an iPhone 6s `iPhone_4.7_15.8.8_19H422_Restore.ipsw` downloaded from an official Apple distribution host, extracted `usr/sbin/BlueTool` locally from the read-only APFS image, and used modpunk's original `extract-bt-firmware.py` to recover the **USI N71** `BCM4350C5` HCD. The private HCD is 80,991 bytes and was **not** uploaded to GitHub.
2. Transferred the exact file over the isolated USB link into the phone's `/lib/firmware/brcm/BCM4350C5.apple,n71.hcd` in tmpfs.
3. Merely toggling HCI down/up did **not** rerun the driver firmware setup. A volatile serdev unbind/rebind of **only** `serial0-0` through `/sys/bus/serial/drivers/hci_uart_bcm/{unbind,bind}` did.
4. The kernel log confirmed:
   ```text
   Bluetooth: hci0: BCM4350C5 'brcm/BCM4350C5.apple,n71.hcd' Patch
   Bluetooth: hci0: BCM4350 UART 37.4 MHz Albarossa USI Black Magick MCC
   Bluetooth: hci0: BCM4350C5 (003.006.007) build 0825
   ```
   Firmware **build 0000 -> build 0825** is a real on-device patchram confirmation.
5. Powered up `hci0` via the original `hci-probe up` ioctl tool. HCI stats were `cmd_tx=524`, `evt_rx=524`, `err_rx=0`, `err_tx=0`.
6. Compiled `tools/ble-probe.c` to a static ARM64 binary and ran a **passive 12-second LE scan** on the phone. LE Set Scan Parameters (`0x200b`), Set Scan Enable (`0x200c`), and Disable (`0x200c`) each completed with `status=0`. The controller returned **25 advertising reports** from its RF environment. The tool deliberately redacts all MAC addresses and advertising payloads.

**Verified outcome:** firmware patchram loading, HCI controller power-up, and BLE advertisement reception under native Linux. **Not yet verified:** Bluetooth pairing, bonding, reconnection, BR/EDR profiles, or audio. The controller initially reports a shared Broadcom fallback address; do not reuse that address for pairing. The device's proper address or a locally administered temporary address must be configured privately through the management interface.

This is a **volatile, RAM-only test**. Never commit the Apple firmware, full logs containing identifiers, or per-device radio calibration. Reprobe affects only the Bluetooth UART interface and is not necessary for the running USB shell. The Bluetooth HCD must match the local **USI module**, not a guessed Murata replacement.

### Passive BLE validation, from the phone shell (after locally loading compatible firmware)

```sh
hci-probe info
hci-probe up
ble-probe 12
```

Expected success is one or more `advertising reports`; zero reports is inconclusive when no advertising peripherals are within range. The scan is passive, sends no connection or pairing requests, and shuts down the scanning state after the test. The binary itself contains no firmware or device addresses.

## 5. Device-specific touch prerequisites — recovered privately, not published

**2026-11-09: verified on the user's N71/S8000 device.**

- Official iPhone 6s iOS restore image yielded the original `N71.mtprops` touch package. The [Omarchy-iPhone6s extractor](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/tools/touch/extract-n71-touch-fw.py) validated both firmware images and generated an **84,092-byte** Z2/HBPP touch firmware payload (`apple/mtfw-n71.bin`). This is private Apple firmware; it is **not** included in this repository.
- The running iPhone's m1n1-provided **read-only** Apple Device Tree (`/dev/mtd1ro`, 160 KiB) contains a filled `multi-touch-calibration` property. The [upstream read-only parser](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/tools/touch/adt-touch-cal.py) confirmed **1,024 bytes of device-unique calibration**. Raw ADT and the calibration fragment remain private and are excluded from Git.
- The six foundational A9 SPI/Z2 touch patches were applied to a separate HoolockLinux kernel worktree with one small Device Tree rebase; an AArch64 `Image.gz` and N71 DTB compiled successfully. No device boot with this test image has yet occurred.
- The additional eight patches from [Omarchy-iPhone6s PR #19](https://github.com/modpunk/Omarchy-iPhone6s/pull/19), covering touch clock, power switching, firmware upload and N71 protocol refinements, have also applied cleanly to that isolated worktree. A further AArch64 kernel build completed successfully with the Apple touch reference clock and the PMU regulator framework enabled. This is an offline build success only; the new image has not been booted on the iPhone.
- The touchscreen device-tree node remains **disabled by default**. The touch boot path requires safe power sequencing, clock, firmware and private calibration injection. No speculative firmware-command fuzzing has been attempted.

**Safety note:** `/dev/mtd1ro` is the m1n1 read-only memory-backed runtime Apple Device Tree, not an instruction to read or write the iPhone NAND. No `/dev/mtd*` write, NFC, SEP or internal storage operation was performed. Only sanitized findings belong in this public worklog.

## 6. November 10: second native Linux session and BLE retest

After the confirmed palen1x/PongoOS RAM-only boot, the host enumerated the Apple HoolockLinux USB gadget at `05ac:4142`, brought up `172.16.42.2/24`, and opened the BusyBox shell at `172.16.42.1:23`. Runtime `uname -r` matched `7.3.0-rc1-g6831bc701a6c`.

The known-good board-matched Broadcom USI patchram and compatible Apple PMIC GPIO module were copied privately over isolated USB to the phone's volatile filesystem. On-disk SHA-256 verification matched the previously validated artifacts. Loading `gpio-apple-pmic.ko` caused `hci0` to enumerate and the firmware load reported BCM4350C5 **build 0825**.

A new **10-second passive BLE scan** returned **17 advertising reports**, with HCI command statuses `0`, and zero recorded HCI RX/TX errors. Addresses and advertising payloads were suppressed. Scanning was then disabled. This independently reconfirms BLE receive functionality after a fresh Linux boot. Pairing, identity management, Bluetooth Classic and audio remain untested.

The Linux USB shell stayed connected, and **no persistent phone storage was written**. The temporary HTTP transfer server was bound only to the isolated USB interface and terminated after use. See [USB boot recovery](BOOT_USB_RECOVERY.md), [ADT/PCIe mapping](N71_PCIE_ADT_MAPPING.md) and [touch ACK review](TOUCH_ACK_REVIEW.md).
