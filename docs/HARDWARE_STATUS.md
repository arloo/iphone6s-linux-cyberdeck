# Hardware state — iPhone 6s Samsung A9 (N71/S8000)

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

## Touchscreen — not working

- Only the `gpio-keys` input device is currently registered.
- No touch events, multitouch device or dedicated touch driver proven.
- Investigate existing Apple touch / Z2 work across HoolockLinux, postmarketOS and other Apple SoC ports.
- Determine the exact N71 interface and controller; **do not assume** another Apple's touchscreen wiring and firmware apply unchanged.

## Bluetooth — partial, promising

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

`/sys/class/bluetooth/hci0` exists and maps to the serial platform path. **HCI command responses and missing firmware do not yet establish working radio or pairing.** No proprietary HCD is included.

## Wi-Fi — not working

- `CONFIG_WLAN` currently disabled.
- No `wlan0` or other wireless interface, and no PCI device enumerated during the tested boot.
- Investigate the N71-specific transport (do not assume that Bluetooth UART also serves Wi-Fi), Device Tree node, chip power/clock, firmware and permitted per-device calibration handling.
- Separate “bus/device discovered,” “interface created,” “firmware loaded,” “scan completed,” and “association established.”

## Known limitations

No touchscreen, verified Wi-Fi connection or Bluetooth pairing; no persistent root filesystem, no confirmed battery reporting. Shell uses root Telnet over isolated USB network and must not be exposed to untrusted networks.
