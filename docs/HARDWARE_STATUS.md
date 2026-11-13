# Hardware state — iPhone 6s Samsung A9 (N71/S8000)

> **Latest physical check, 13 November 2026:** [Diagnostic-kernel boot, battery readings and full PERST-held port1 postflight](N71_BATTERY_BUILTIN_RAM_KERNEL_2026_11_13.md) PASS. Battery telemetry is available; the tested Dell USB setup shows net discharge. USB and touch registration remain present, Bluetooth build 0825 is UP/RUNNING without HCI errors, and all PCIe domains are OFF after cleanup. Earlier sections below are historical baselines; they do not describe the current touch, wireless Kconfig or battery-telemetry state.

> **Updated N71/S8000 touch evidence, 2026-11-11:** The [physical device calibration experiment](N71_CALIBRATION_ACK_DATA_LIVE_SUCCESS_2026_11_11.md) received real HBPP **ACK_DATA=0x4bc1** on its first poll, using five bounded SPI transfers in one message. USB and watchdog cleanup passed. **No touch EVDEV input or controller firmware start yet.** Older sections below describe previous stages, not the latest calibration status.


Captured from a working Linux boot on November 9, 2026.

## Verified runtime

- Model: `Apple iPhone 6s (Samsung)`
- Device Tree compatible: `apple,n71`, `apple,s8000`, `apple,arm-platform`
- Kernel: `Linux 7.3.0-rc1-g6831bc701a6c aarch64`
- Initramfs: RAM-resident BusyBox 1.38.0
- Framebuffer: `/dev/fb0`, geometry 750x1334, 32bpp; `stride=3000`; RGBA bitfields `8/16,8/8,8/0,0/0` (BGRX in little-endian byte order).
- Physical keys: `gpio-keys` on `/dev/input/event0`.
- USB gadget: `usb0` at `172.16.42.1`; host enumerates USB ID `05ac:4142`; 3/3 ICMP to the host.
- No `/proc/partitions` block entries were detected. No tested persistent filesystem.
- No usable Wi-Fi interface and no touch input node observed.

## Current kernel configuration

The configuration used to build the tested image includes:

```text
# CONFIG_INPUT_TOUCHSCREEN is not set
# CONFIG_WLAN is not set
CONFIG_SPI_APPLE=y
CONFIG_PCIE_APPLE=y
CONFIG_BT=y
CONFIG_BT_BCM=y
CONFIG_BT_HCIUART=y
CONFIG_BT_HCIUART_SERDEV=y
CONFIG_BT_HCIUART_H4=y
CONFIG_BT_HCIUART_BCM=y
CONFIG_FW_LOADER=y
```

Enabling a Kconfig switch alone does **not** provide missing pinctrl, regulator, transport, interrupts, calibration or device-specific driver code.

## Touchscreen — no on-device input yet; full offline build ready

- Only the `gpio-keys` input device is currently registered.
- No touch events, multitouch device or dedicated touch driver proven.
- Investigate existing Apple touch / Z2 work across HoolockLinux, postmarketOS and other Apple SoC ports.
- N71/S8000 touch is on SPI2. A private original N71 firmware payload (84,092 bytes) and private calibration (1,024 bytes) were recovered through an official Apple restore image and the running phone's read-only m1n1 runtime ADT.
- A separate kernel worktree compiled the A9 S5L SPI controller, Z2 touch driver, reference clock and power regulator changes from the Omarchy-iPhone6s touch-next work. The original booted kernel remains unchanged and the touchscreen is **not yet verified on-device**.

## Bluetooth — patchram loaded and passive LE reception verified

Board DTS `s800x-6s.dtsi` contains:

```dts
bluetooth0: bluetooth {
    compatible = "brcm,bcm4350-bt";
    shutdown-gpios = <&pmic_gpio 8 GPIO_ACTIVE_HIGH>;
    device-wakeup-gpios = <&pinctrl_ap 71 GPIO_ACTIVE_HIGH>;
    local-bd-address = [00 00 00 00 00 00];
};
```

Runtime logs confirm a real HCI UART response:

```text
Bluetooth: hci0: BCM: chip id 110
Bluetooth: hci0: BCM: features 0x2f
Bluetooth: hci0: BCM4350C5
Bluetooth: hci0: BCM4350C5 (003.006.007) build 0000
Bluetooth: hci0: BCM: firmware Patch file not found, tried:
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.hcd'
```

`/sys/class/bluetooth/hci0` exists and maps to the serial platform path. The logs above are the **initial pre-firmware baseline**. Later in the same RAM-only Linux session, we privately loaded an official, compatible USI/N71 Broadcom HCD patch through a scoped `hci_uart_bcm` serdev reprobe. The controller reported **firmware build 0825**, versus initial **build 0000**. A native ARM64 passive BLE scan received **25 advertising reports in 12 seconds**, with successful scan enable and disable commands. This verifies real BLE radio reception, **not** pairing, bonding, classic Bluetooth or audio. No proprietary HCD, addresses or scan payloads are included.

## Wi-Fi — not working

- `CONFIG_WLAN` currently disabled.
- No `wlan0` or other wireless interface, and no PCI device enumerated during the tested boot.
- N71 board research identifies the Broadcom BCM4350 Wi-Fi half on **S8000 PCIe port 1**, distinct from the Bluetooth UART.
- Current Apple PCIe host driver has no explicit S8000 binding and current S8000 Device Tree has no A9 PCIe root-complex node. Work must start with safe PCIe port-1 enablement, clock/reset, interrupts and DART/IOMMU before generic `brcmfmac` can bind. The internal iOS NVMe storage is on PCIe port 0 and must not be written.
- Separate “bus/device discovered,” “interface created,” “firmware loaded,” “scan completed,” and “association established.”

## Known limitations

No working touchscreen, no Wi-Fi connection and no Bluetooth pairing yet. Bluetooth **LE passive reception does work**. No persistent root filesystem, no confirmed battery reporting. Shell uses root Telnet over isolated USB network and must not be exposed to untrusted networks.
