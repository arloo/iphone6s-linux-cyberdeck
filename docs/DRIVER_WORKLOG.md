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
