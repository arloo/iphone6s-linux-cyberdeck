# Hardware status — reviewed 2026-11-16

Physical target: **iPhone 6s N71, Samsung A9 / S8000**. Kernel: `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`. All observations concern RAM Linux; no persistent OS installation or NAND write is claimed.

| Subsystem | Physical evidence | Current qualification |
|---|---|---|
| Boot | checkm8/PongoOS/m1n1 chain and Linux USB re-enumeration | PASS |
| Framebuffer | 750 × 1334, 32 bpp; CYBERDECK UI rendered | PASS |
| USB | NCM networking and recovery shell | PASS; unauthenticated Telnet hardening open |
| Touch | Automatic firmware/calibration setup, real single-contact and simultaneous two-finger EVDEV events | PASS for tested contacts; endurance/edge/latency open |
| Wi-Fi | Real PCIe BCM4350C5 `14e4:43a3` on brcmfmac, translated SID0 DMA, Linux MSI message 8 / AIC 264 | PASS for native network operation |
| Wi-Fi traffic | WPA2 authentication, DHCP, WLAN default route, DNS, Internet, 1 MiB transfer with verified SHA-256 | PASS at 2412 MHz; 5 GHz not tested |
| Wi-Fi lifecycle | Managed runtime load/unbind/unload, seven power domains restored | PASS; automatic reboot restoration not tested |
| Bluetooth UART/HCI | Genuine BCM4350C5 patchram build 0825, zero transport errors | PASS |
| Bluetooth LE | 12 devices discovered | PASS for discovery; no LE GATT application claim |
| Bluetooth BR/EDR | Dell discovery, Paired and Bonded state, 256 × 256-byte exact echo | PASS for controlled pairing and encrypted L2CAP transport |
| Radio coexistence | Wi-Fi remained WPA_COMPLETED and Internet traffic worked during Bluetooth transfer | PASS for the short concurrent trial; no endurance claim |
| Bluetooth HID | No keyboard/mouse available | NOT TESTED; deferred until a peripheral is available |
| Bluetooth audio | No playback/profile test | NOT TESTED |
| Battery | Gauge telemetry; guarded 300 mA USB input lease; charging observed | PASS for monitored charging; lease is finite (3600 s) |
| Storage/baseband | Outside experiments | No persistent storage or telephony support claim |
| Suspend/resume | No qualification | NOT TESTED |
| New-boot connectivity | Current-session idempotence and four-daemon recovery PASS; private integrated candidate built | New boot NOT TESTED |
| N71m / S8003 | No compatible hardware | NOT TESTED across all subsystems |

Bluetooth security level 2 requires encryption; it does not prove MITM-authenticated pairing. The optional BlueZ privacy-setting request was rejected; controller address privacy remains unqualified. Pairing keys are private RAM state and have not been proven to survive a new boot.

Evidence: [Wi-Fi](N71_NATIVE_WIFI_PHYSICAL_PASS_2026_11_16.json), [Bluetooth](N71_BLUETOOTH_PHYSICAL_PASS_2026_11_16.json), [Bluetooth runtime](N71_BLUETOOTH_RUNTIME_2026_11_16.md), [touch](N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md), [engineering assessment](PROJECT_STATE_2026_11_16.md). The [older hardware snapshot](history/HARDWARE_STATUS_BEFORE_2026_11_16_REFRESH.md) is historical only.

## Current-session UI and recovery follow-up

The native shell dashboard/PTY/keyboard is running with reviewed framebuffer readback and a passed native synthetic-key/real-PTY selftest. Human typing acceptance remains open. Current-session service recovery passed, including private Bluetooth bond reload and a verified 4 MiB WLAN transfer. Display brightness is 1023/2047; schedutil and WLAN power save remain active. See [detailed evidence and limits](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md).
